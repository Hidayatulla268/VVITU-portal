import json
import logging
import datetime as dt
from functools import wraps

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib import messages
from django.db import transaction
from django.db.models import Q, Count
from django.utils import timezone
from django.conf import settings
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST

logger = logging.getLogger(__name__)

from accounts.models import User, Student, Faculty, Achievement, FacultyLeaveRequest, generate_secure_temp_password
from core.models import (
    Branch, Year, Section, Subject, Timetable, Attendance, Exam, Result,
    Notification, ResultRelease, FacultyAttendance, ClassTransfer, ClassDiary,
    SubjectTopicPlan, ExamSchedule, ensure_sections_for_all_branches,
    AcademicCalendar
)

from admin_dashboard.views import _send_result_emails
from core.sms_utils import send_result_notifications, send_result_sms_to_parent
from core.syllabus_utils import get_subject_syllabus_progress, check_and_dispatch_syllabus_reminders

# ─────────────────────────────────────────────
# DECORATOR
# ─────────────────────────────────────────────
def hod_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or request.user.role != 'hod':
            messages.error(request, "Access denied. HODs only.")
            return redirect('accounts:login')
        try:
            request.faculty = request.user.faculty_profile
            request.department = request.faculty.department
            if not request.department:
                messages.error(request, "HOD has no department assigned. Please contact the administrator.")
                return redirect('accounts:profile')
        except Faculty.DoesNotExist:
            from django.contrib.auth import logout
            logout(request)
            messages.error(request, "HOD Faculty Profile not found. Please contact administrator.")
            return redirect('accounts:login')
        return view_func(request, *args, **kwargs)
    return wrapper

# ─────────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────────
@hod_required
def dashboard(request):
    dept = request.department
    
    # Department stats
    student_count = Student.objects.filter(branch=dept, is_active=True).count()
    faculty_count = Faculty.objects.filter(department=dept, is_active=True).count()
    subject_count = Subject.objects.filter(branch=dept, is_deleted=False).count()
    section_count = Section.objects.filter(branch=dept).count()
    
    # Attendance today
    today = timezone.localdate()
    att_today = Attendance.objects.filter(student__branch=dept, date=today)
    present_today = att_today.filter(status='P').count()
    absent_today = att_today.filter(status='A').count()
    
    # Department notices
    notices = Notification.objects.filter(is_active=True, is_deleted=False).filter(
        Q(target_branch=dept) | Q(target_all=True)
    ).order_by('-created_at')[:5]
    
    # Pending achievements in the department
    pending_achievements = Achievement.objects.filter(
        is_verified=False
    ).filter(
        Q(user__student_profile__branch=dept) | Q(user__faculty_profile__department=dept)
    ).select_related('user').order_by('-created_at')

    # Pending leave requests in department (excluding HOD's own leave)
    pending_leave_count = FacultyLeaveRequest.objects.filter(
        faculty__department=dept, status='pending'
    ).exclude(faculty=request.faculty).count()
    
    # HOD's personal teaching schedule & faculty data
    day_name = today.strftime('%A')
    from django.db.models import Case, When, Value, IntegerField
    day_order = Case(
        When(day__iexact='Monday', then=Value(1)),
        When(day__iexact='Tuesday', then=Value(2)),
        When(day__iexact='Wednesday', then=Value(3)),
        When(day__iexact='Thursday', then=Value(4)),
        When(day__iexact='Friday', then=Value(5)),
        When(day__iexact='Saturday', then=Value(6)),
        When(day__iexact='Sunday', then=Value(7)),
        default=Value(8),
        output_field=IntegerField()
    )

    my_timetable_today = (
        Timetable.objects
        .filter(faculty=request.faculty, day__iexact=day_name.strip())
        .select_related('section', 'subject')
        .order_by('period')
    )
    my_weekly_timetable = (
        Timetable.objects
        .filter(faculty=request.faculty)
        .select_related('section', 'subject')
        .annotate(day_sort=day_order)
        .order_by('day_sort', 'period')
    )
    my_subjects = (
        Subject.objects
        .filter(faculty=request.faculty, is_deleted=False)
        .select_related('branch', 'year')
    )
    my_transferred_today = (
        ClassTransfer.objects
        .filter(substitute_faculty=request.faculty, date=today)
        .select_related('timetable_entry__section', 'timetable_entry__subject', 'original_faculty__user')
    )
    my_transferred_given_today = (
        ClassTransfer.objects
        .filter(original_faculty=request.faculty, date=today)
        .select_related('timetable_entry__section', 'timetable_entry__subject', 'substitute_faculty__user')
    )
    my_counselled_count = Student.objects.filter(counsellor=request.faculty, user__is_deleted=False).count()
    my_leaves_taken = request.faculty.get_monthly_leaves_taken(today.year, today.month)
    my_leaves_remaining = request.faculty.get_monthly_leaves_remaining(today.year, today.month)
    my_monthly_limit = float(request.faculty.monthly_leave_limit or 2.0)
    my_leave_limit_reached = request.faculty.is_leave_limit_reached(today.year, today.month)
    
    # Detention & Readmissions
    from accounts.models import StudentLeaveRequest, StudentReadmissionRequest
    detained_count = Student.objects.filter(
        branch=dept, is_active=True
    ).filter(
        Q(academic_status__in=['DETAINED_ATTENDANCE', 'DETAINED_CREDITS']) | Q(is_detained=True)
    ).count()

    pending_readmission_count = StudentReadmissionRequest.objects.filter(
        student__branch=dept, hod_status='pending'
    ).count()

    pending_student_leave_count = StudentLeaveRequest.objects.filter(
        student__branch=dept, status='pending'
    ).count()

    recent_readmissions = StudentReadmissionRequest.objects.filter(
        student__branch=dept
    ).select_related('student__user', 'target_junior_year', 'target_junior_section').order_by('-created_at')[:4]

    recent_student_leaves = StudentLeaveRequest.objects.filter(
        student__branch=dept
    ).select_related('student__user').order_by('-created_at')[:4]

    # Faculty Attendance today
    fac_att_qs = FacultyAttendance.objects.filter(faculty__department=dept, date=today)
    faculty_present_count = fac_att_qs.filter(status='P').count()
    faculty_leave_count = fac_att_qs.filter(status__in=['L', 'OD']).count()

    # Year-wise Breakdown Analytics
    year_stats = []
    for yr_num in [1, 2, 3, 4]:
        yr_obj = Year.objects.filter(year=yr_num).first()
        if yr_obj:
            yr_students = Student.objects.filter(branch=dept, year=yr_obj, is_active=True)
            yr_count = yr_students.count()
            yr_detained = yr_students.filter(
                Q(academic_status__in=['DETAINED_ATTENDANCE', 'DETAINED_CREDITS']) | Q(is_detained=True)
            ).count()
            year_stats.append({
                'year_num': yr_num,
                'year_name': f"{yr_num}{'st' if yr_num==1 else 'nd' if yr_num==2 else 'rd' if yr_num==3 else 'th'} Year",
                'student_count': yr_count,
                'detained_count': yr_detained,
                'regular_count': max(0, yr_count - yr_detained),
            })

    # Class Diary Today
    diary_today_count = ClassDiary.objects.filter(subject__branch=dept, date=today).count()

    # Faculty Class Attendance & Conduction Audit (Today)
    class_audit_data = get_department_class_attendance_audit_data(dept, today)

    context = {
        'student_count': student_count,
        'faculty_count': faculty_count,
        'subject_count': subject_count,
        'section_count': section_count,
        'present_today': present_today,
        'absent_today': absent_today,
        'detained_count': detained_count,
        'pending_readmission_count': pending_readmission_count,
        'pending_student_leave_count': pending_student_leave_count,
        'recent_readmissions': recent_readmissions,
        'recent_student_leaves': recent_student_leaves,
        'faculty_present_count': faculty_present_count,
        'faculty_leave_count': faculty_leave_count,
        'year_stats': year_stats,
        'diary_today_count': diary_today_count,
        'class_audit_data': class_audit_data,
        'notices': notices,
        'pending_achievements': pending_achievements,
        'pending_leave_count': pending_leave_count,
        'department': dept,
        # HOD as Faculty variables
        'my_timetable_today': my_timetable_today,
        'my_weekly_timetable': my_weekly_timetable,
        'my_subjects': my_subjects,
        'my_transferred_today': my_transferred_today,
        'my_transferred_given_today': my_transferred_given_today,
        'my_counselled_count': my_counselled_count,
        'my_leaves_taken': my_leaves_taken,
        'my_leaves_remaining': my_leaves_remaining,
        'my_monthly_limit': my_monthly_limit,
        'my_leave_limit_reached': my_leave_limit_reached,
        'today': today,
        'day_name': day_name,
    }
    return render(request, 'hod/dashboard.html', context)




# ─────────────────────────────────────────────
# NOTICE BOARD / NOTIFICATION CIRCULATION
# ─────────────────────────────────────────────
@hod_required
def create_notice(request):
    dept = request.department
    sections = Section.objects.filter(branch=dept)
    
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        message = request.POST.get('message', '').strip()
        circulation = request.POST.get('circulation', 'branch')  # college, branch, class
        section_id = request.POST.get('section', '')
        
        if not title or not message:
            messages.error(request, "Title and message are required.")
            return redirect('hod:create_notice')
            
        notif = Notification(
            title=title,
            message=message,
            notif_type=Notification.TYPE_ANNOUNCEMENT,
            created_by=request.user,
        )
        
        if circulation == 'college':
            notif.target_all = True
        elif circulation == 'branch':
            notif.target_all = False
            notif.target_branch = dept
        elif circulation == 'class' and section_id:
            notif.target_all = False
            notif.target_branch = dept
            notif.target_role = 'student'
            # Store target section link
            try:
                sec = Section.objects.get(id=section_id, branch=dept)
                notif.target_section = sec
            except Section.DoesNotExist:
                pass
                
        notif.save()
        messages.success(request, "Notice circulated successfully.")
        return redirect('hod:dashboard')
        
    return render(request, 'hod/create_notice.html', {'sections': sections, 'department': dept})

# ─────────────────────────────────────────────
# SUBJECT & FACULTY MAPPING
# ─────────────────────────────────────────────
@hod_required
def subject_mapping(request):
    dept = request.department
    subjects = Subject.objects.filter(branch=dept, is_deleted=False).select_related('faculty__user', 'year')
    faculties = Faculty.objects.filter(department=dept, is_active=True).select_related('user')
    
    if request.method == 'POST':
        subj_id = request.POST.get('subject_id')
        fac_id = request.POST.get('faculty_id') or None
        
        subj = get_object_or_404(Subject, id=subj_id, branch=dept)
        if fac_id:
            fac = get_object_or_404(Faculty, id=fac_id, department=dept)
            subj.faculty = fac
        else:
            subj.faculty = None
        subj.save()
        messages.success(request, f"Faculty assigned to {subj.code} successfully.")
        return redirect('hod:subject_mapping')
        
    return render(request, 'hod/subject_mapping.html', {
        'subjects': subjects,
        'faculties': faculties,
    })

# ─────────────────────────────────────────────
# ASSIGN CLASS TEACHER / COUNSELLOR
# ─────────────────────────────────────────────
@hod_required
def assign_teacher(request):
    dept = request.department
    sections = Section.objects.filter(branch=dept).select_related('year')
    faculties = Faculty.objects.filter(department=dept, is_active=True).select_related('user')
    students = Student.objects.filter(branch=dept, is_active=True).select_related('user', 'section', 'class_teacher', 'counsellor')
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'class_teacher':
            section_id = request.POST.get('section')
            faculty_id = request.POST.get('faculty') or None
            
            sec = get_object_or_404(Section, id=section_id, branch=dept)
            fac = get_object_or_404(Faculty, id=faculty_id, department=dept) if faculty_id else None
            
            # Batch update student class teachers in this section
            updated = Student.objects.filter(section=sec).update(class_teacher=fac)
            messages.success(request, f"Class Teacher assigned to {updated} students in {sec}.")
            
        elif action == 'counsellor':
            student_id = request.POST.get('student')
            faculty_id = request.POST.get('faculty') or None
            
            stu = get_object_or_404(Student, id=student_id, branch=dept)
            fac = get_object_or_404(Faculty, id=faculty_id, department=dept) if faculty_id else None
            
            stu.counsellor = fac
            stu.save()
            messages.success(request, f"Counsellor assigned to {stu.roll_number} successfully.")
            
        return redirect('hod:assign_teacher')
        
    return render(request, 'hod/assign_teacher.html', {
        'sections': sections,
        'faculties': faculties,
        'students': students,
    })

# ─────────────────────────────────────────────
# TIMETABLE MANAGEMENT
# ─────────────────────────────────────────────
from django.http import HttpResponse, JsonResponse
from core.models import (
    Branch, Year, Section, Subject, Timetable, Attendance, Exam, Result,
    Notification, ResultRelease, FacultyAttendance, ClassTransfer, ClassDiary,
    SubjectTopicPlan, ExamSchedule, SectionTimetableMetadata, ensure_sections_for_all_branches
)
from core.timetable_service import (
    get_section_timetable_context, get_faculty_timetable_context,
    sync_class_timetable_from_data, sync_faculty_timetable_from_data,
    extract_timetable_with_ai, generate_official_timetable_pdf,
    check_faculty_schedule_clash,
    STANDARD_PERIOD_TIMINGS, DAY_LIST, PERIOD_LIST
)

@hod_required
def manage_timetable(request):
    """
    Department-scoped timetable dashboard for HOD.
    Lists department sections, department faculty timetables, and allows Photo/PDF upload.
    """
    ensure_sections_for_all_branches()
    dept = request.department
    sections = Section.objects.filter(branch=dept).select_related('year', 'branch')
    faculties = Faculty.objects.filter(department=dept, is_active=True).select_related('user')
    
    # Check if a specific faculty is selected for preview
    selected_faculty_id = request.GET.get('faculty_id')
    selected_faculty_ctx = None
    if selected_faculty_id:
        fac = get_object_or_404(Faculty, id=selected_faculty_id, department=dept)
        selected_faculty_ctx = get_faculty_timetable_context(fac)

    return render(request, 'hod/manage_timetable.html', {
        'sections': sections,
        'faculties': faculties,
        'selected_faculty_ctx': selected_faculty_ctx,
        'can_upload': True,
        'department': dept,
    })

@hod_required
def edit_timetable(request, section_id):
    """
    Allows HOD to view, edit, modify periods, and update metadata for a department section
    in the official VVIT Timetable layout. Handles schedule conflicts with interactive resolution.
    """
    dept = request.department
    section = get_object_or_404(Section, id=section_id, branch=dept)
    subjects = Subject.objects.filter(branch=dept, year=section.year, is_deleted=False)
    faculties = Faculty.objects.filter(department=dept, is_active=True).select_related('user')
    
    # Metadata for this section
    metadata, _ = SectionTimetableMetadata.objects.get_or_create(
        section=section,
        defaults={
            'academic_year': '2026-27',
            'room_number': 'C-402',
            'program_name': f"[Program: {dept.name} – {dept.code}]",
        }
    )

    if request.method == 'POST':
        action = request.POST.get('action', '')

        # 1. Update Official Metadata (Room, Academic Year, Effective Date, Class Teacher, Signatures)
        if action == 'update_metadata':
            metadata.academic_year = request.POST.get('academic_year', '2026-27').strip()
            metadata.room_number = request.POST.get('room_number', 'C-402').strip()
            metadata.program_name = request.POST.get('program_name', '').strip() or f"[Program: {dept.name} – {dept.code}]"
            metadata.timetable_incharge = request.POST.get('timetable_incharge', 'Timetable I/C').strip()
            metadata.hod_name = request.POST.get('hod_name', 'HOD').strip()
            metadata.dean_academics_name = request.POST.get('dean_academics_name', 'Dean, Academics').strip()
            metadata.principal_name = request.POST.get('principal_name', 'Principal').strip()

            eff_date_str = request.POST.get('with_effect_from', '')
            if eff_date_str:
                try:
                    metadata.with_effect_from = dt.date.fromisoformat(eff_date_str)
                except Exception:
                    pass

            ct_id = request.POST.get('class_teacher')
            if ct_id:
                ct_fac = Faculty.objects.filter(id=ct_id, department=dept).first()
                if ct_fac:
                    metadata.class_teacher = ct_fac
                    metadata.class_teacher_name = ct_fac.user.get_full_name()
                    # Update all students in this section
                    Student.objects.filter(section=section).update(class_teacher=ct_fac)
            else:
                ct_name_input = request.POST.get('class_teacher_name', '').strip()
                if ct_name_input:
                    metadata.class_teacher_name = ct_name_input

            metadata.save()
            messages.success(request, "Official timetable metadata & signatures updated.")
            return redirect('hod:edit_timetable', section_id=section_id)

        # 2. Add / Update / Delete Timetable Slot
        day = request.POST.get('day', '').strip().capitalize()
        period = request.POST.get('period')
        subject_id = request.POST.get('subject')
        faculty_id = request.POST.get('faculty')
        delete_slot = request.POST.get('delete')
        co_faculty_str = request.POST.get('co_faculty_display', '').strip()
        resolution = request.POST.get('resolution', '').strip()
        
        try:
            period = int(period)
        except (ValueError, TypeError):
            messages.error(request, "Invalid period number.")
            return redirect('hod:edit_timetable', section_id=section_id)
            
        if delete_slot:
            Timetable.objects.filter(section=section, day=day, period=period).delete()
            messages.success(request, f"Timetable slot for {day} Period {period} deleted.")
        else:
            subj = get_object_or_404(Subject, id=subject_id, branch=dept)
            fac = None
            if faculty_id:
                fac = get_object_or_404(Faculty, id=faculty_id, department=dept)
            
            start_time = request.POST.get('start_time') or None
            end_time = request.POST.get('end_time') or None
            room_number = request.POST.get('room_number', '').strip() or metadata.room_number or 'C-402'

            # Fallback to standard VVIT period timings if not specified
            if not start_time and period in STANDARD_PERIOD_TIMINGS:
                start_time = STANDARD_PERIOD_TIMINGS[period]['start']
            if not end_time and period in STANDARD_PERIOD_TIMINGS:
                end_time = STANDARD_PERIOD_TIMINGS[period]['end']

            # Check if faculty has a clash in another section
            clash_info = check_faculty_schedule_clash(fac, day, period, exclude_section=section)

            if clash_info:
                if resolution == 'replace_past':
                    # Fix this period and unassign/remove from the past conflicting slot
                    conflicting_slot = Timetable.objects.filter(id=clash_info['timetable_id']).first()
                    if conflicting_slot:
                        conflicting_slot.faculty = None
                        conflicting_slot.save(update_fields=['faculty'])

                    Timetable.objects.update_or_create(
                        section=section, day=day, period=period,
                        defaults={
                            'subject': subj,
                            'faculty': fac,
                            'co_faculty_display': co_faculty_str or None,
                            'room_number': room_number,
                            'start_time': start_time,
                            'end_time': end_time,
                        }
                    )

                    # Send notification to the faculty
                    if fac and fac.user:
                        try:
                            Notification.objects.create(
                                title="Timetable Schedule Reassigned",
                                message=(
                                    f"Your schedule on {day}, Period {period} has been reassigned by HOD. "
                                    f"You have been unassigned from {clash_info['section_name']} ({clash_info['subject_name']}) "
                                    f"and assigned to {section} ({subj.name})."
                                ),
                                notif_type=Notification.TYPE_SYSTEM,
                                priority=Notification.PRIORITY_HIGH,
                                target_all=False,
                                target_user=fac.user,
                                created_by=request.user
                            )
                        except Exception as ne:
                            logger.error(f"Error sending timetable reassignment notification: {ne}")

                    messages.warning(
                        request,
                        f"Schedule conflict resolved: {fac.user.get_full_name()} assigned to {section} ({day} P{period}) "
                        f"and unassigned from previous slot in {clash_info['section_name']}."
                    )
                    return redirect('hod:edit_timetable', section_id=section_id)

                elif resolution == 'keep_past':
                    # Fix only the past period (preserve past slot, save this slot with faculty=None / TBA)
                    Timetable.objects.update_or_create(
                        section=section, day=day, period=period,
                        defaults={
                            'subject': subj,
                            'faculty': None,
                            'co_faculty_display': co_faculty_str or None,
                            'room_number': room_number,
                            'start_time': start_time,
                            'end_time': end_time,
                        }
                    )
                    messages.info(
                        request,
                        f"Slot saved for {day} Period {period} ({subj.code}) with faculty TBA. "
                        f"Past assignment for {fac.user.get_full_name() if fac else 'Faculty'} in {clash_info['section_name']} was preserved."
                    )
                    return redirect('hod:edit_timetable', section_id=section_id)

                else:
                    # Conflict without resolution: prevent duplicate slot and alert HOD
                    messages.error(
                        request,
                        f"Schedule Clash Detected! {fac.user.get_full_name()} is already assigned to {clash_info['section_name']} "
                        f"({clash_info['subject_name']}) on {day}, Period {period}. Please resolve using 'Fix That Period (Remove Past)' or 'Fix Only Past Period'."
                    )
                    return redirect('hod:edit_timetable', section_id=section_id)
            
            Timetable.objects.update_or_create(
                section=section, day=day, period=period,
                defaults={
                    'subject': subj,
                    'faculty': fac,
                    'co_faculty_display': co_faculty_str or None,
                    'room_number': room_number,
                    'start_time': start_time,
                    'end_time': end_time,
                }
            )
            messages.success(request, f"Slot updated: {day} Period {period} -> {subj.code} ({fac.user.get_full_name() if fac else 'TBA'}).")
            
        return redirect('hod:edit_timetable', section_id=section_id)

    # Build full official VVIT timetable context
    ctx = get_section_timetable_context(section)
    ctx.update({
        'subjects': subjects,
        'faculties': faculties,
        'can_edit': True,
        'can_upload': True,
        'pdf_export_url': f"/hod/timetable/export-pdf/{section.id}/",
    })
    return render(request, 'hod/edit_timetable.html', ctx)


@hod_required
def ajax_check_timetable_clash(request):
    """
    Real-time AJAX endpoint for HOD to check if a faculty member has a timetable conflict on (day, period).
    """
    faculty_id = request.GET.get('faculty_id') or request.POST.get('faculty_id')
    day = request.GET.get('day') or request.POST.get('day')
    period = request.GET.get('period') or request.POST.get('period')
    current_section_id = request.GET.get('section_id') or request.POST.get('section_id')

    if not faculty_id or not day or not period:
        return JsonResponse({'has_clash': False, 'clash': None})

    try:
        faculty = Faculty.objects.select_related('user').filter(id=faculty_id, is_active=True).first()
        if not faculty:
            return JsonResponse({'has_clash': False, 'clash': None})

        section = Section.objects.filter(id=current_section_id).first() if current_section_id else None
        clash = check_faculty_schedule_clash(faculty, day, period, exclude_section=section)

        if clash:
            return JsonResponse({
                'has_clash': True,
                'clash': clash
            })
    except Exception as e:
        logger.error(f"Error checking timetable clash: {e}", exc_info=True)

    return JsonResponse({'has_clash': False, 'clash': None})


@hod_required
def upload_timetable_api(request):
    """
    AJAX API endpoint for HOD to:
      1. Parse Photo / PDF timetable via AI / OCR
      2. Commit and synchronize verified timetable into DB
    Enforces departmental boundary.
    """
    dept = request.department

    if request.method == 'POST':
        # Check if JSON payload (commit) or Multipart (parse)
        if request.content_type and 'application/json' in request.content_type:
            try:
                body = json.loads(request.body.decode('utf-8'))
            except Exception as e:
                logger.error(f"Timetable JSON decode error: {e}", exc_info=True)
                return JsonResponse({'success': False, 'error': f'Invalid JSON body: {str(e)}'}, status=400)

            action = body.get('action')
            sec_id = body.get('section_id')
            data = body.get('data')

            if action == 'commit':
                section = get_object_or_404(Section, id=sec_id, branch=dept)
                res = sync_class_timetable_from_data(section, data, user=request.user)
                return JsonResponse(res)

        else: # File upload
            action = request.POST.get('action')
            sec_id = request.POST.get('section_id')
            uploaded_file = request.FILES.get('file')

            if not uploaded_file:
                return JsonResponse({'success': False, 'error': 'No file uploaded.'}, status=400)

            if action == 'parse':
                from core.file_validators import validate_document_upload
                from django.core.exceptions import ValidationError
                try:
                    validate_document_upload(uploaded_file, allowed_extensions={'.png', '.jpg', '.jpeg', '.pdf'}, max_size_mb=5)
                except ValidationError as ve:
                    return JsonResponse({'success': False, 'error': str(ve.message if hasattr(ve, 'message') else ve)}, status=400)

                section = get_object_or_404(Section, id=sec_id, branch=dept)
                content_type = uploaded_file.content_type
                file_bytes = uploaded_file.read()

                parsed = extract_timetable_with_ai(file_bytes, content_type)
                return JsonResponse({
                    'success': True,
                    'parsed': parsed,
                    'filename': uploaded_file.name,
                })

    return JsonResponse({'success': False, 'error': 'Invalid request method.'}, status=405)


@hod_required
def export_timetable_pdf(request, section_id):
    """
    Exports official VVIT Timetable as A4 Landscape PDF for a department section.
    """
    dept = request.department
    section = get_object_or_404(Section, id=section_id, branch=dept)
    pdf_bytes = generate_official_timetable_pdf(section)
    
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="VVIT_Timetable_{section.branch.code}_{section.year.year}_{section.name}.pdf"'
    return response


@hod_required
def faculty_timetable_view(request, faculty_id):
    """
    Displays the weekly timetable and assigned classes for a department faculty member.
    """
    dept = request.department
    faculty = get_object_or_404(Faculty, id=faculty_id, department=dept)
    ctx = get_faculty_timetable_context(faculty)
    ctx['department'] = dept
    return render(request, 'hod/faculty_timetable_view.html', ctx)


# ─────────────────────────────────────────────
# FACULTY ATTENDANCE MANAGEMENT
# ─────────────────────────────────────────────
@hod_required
def faculty_attendance(request):
    """
    Allows HOD to view and mark attendance for department faculty.
    Supports Month-wise filtering (`month_year`) and Custom Date Range filtering (`date_from`, `date_to`).
    """
    dept = request.department
    today = timezone.localdate()

    month_year = request.GET.get('month_year', '')
    date_from  = request.GET.get('date_from', '')
    date_to    = request.GET.get('date_to', '')
    selected_date_str = request.GET.get('date', today.isoformat())

    try:
        selected_date = dt.datetime.strptime(selected_date_str, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        selected_date = today

    department_faculty = Faculty.objects.filter(department=dept, is_active=True, user__is_deleted=False).select_related('user').order_by('employee_id')

    # Fetch approved leave applications for the selected mark date in this department
    approved_leaves = {
        lr.faculty_id: lr
        for lr in FacultyLeaveRequest.objects.filter(
            faculty__department=dept,
            status='approved',
            start_date__lte=selected_date,
            end_date__gte=selected_date
        ).select_related('faculty')
    }

    # Save attendance POST
    if request.method == 'POST':
        date_param = request.POST.get('date', today.isoformat())
        try:
            post_date = dt.datetime.strptime(date_param, '%Y-%m-%d').date()
        except ValueError:
            post_date = today

        existing_date_records = {
            att.faculty_id: att for att in FacultyAttendance.objects.filter(faculty__department=dept, date=post_date)
        }
        post_approved_leaves = {
            lr.faculty_id: lr
            for lr in FacultyLeaveRequest.objects.filter(
                faculty__department=dept,
                status='approved',
                start_date__lte=post_date,
                end_date__gte=post_date
            )
        }

        saved_count = 0
        locked_count = 0
        now = timezone.now()

        for fac in department_faculty:
            rec = existing_date_records.get(fac.id)
            # Enforce 3-hour Absent Lockout Policy
            is_locked = False
            if rec and rec.is_absent_locked:
                is_locked = True
                status = 'A'
                absent_locked_until = rec.absent_locked_until
                locked_count += 1
            else:
                status = request.POST.get(f'status_{fac.id}')
                if not status:
                    status = 'L' if fac.id in post_approved_leaves else 'P'

                # Set 3-hour lockout when status is marked Absent ('A')
                if status == 'A':
                    absent_locked_until = rec.absent_locked_until if (rec and rec.absent_locked_until and rec.absent_locked_until > now) else (now + dt.timedelta(hours=3))
                else:
                    absent_locked_until = None

            remarks = request.POST.get(f'remarks_{fac.id}', '').strip()
            if not remarks and fac.id in post_approved_leaves and status == 'L':
                remarks = f"Approved {post_approved_leaves[fac.id].get_leave_type_display()}"

            if status not in ('P', 'A', 'L', 'HD'):
                status = 'P'

            FacultyAttendance.objects.update_or_create(
                faculty=fac,
                date=post_date,
                defaults={
                    'status': status,
                    'remarks': remarks,
                    'marked_by': request.user,
                    'absent_locked_until': absent_locked_until,
                }
            )
            saved_count += 1

        if locked_count > 0:
            messages.info(request, f"{locked_count} department faculty record(s) marked Absent within the last 3 hours remain locked from modification.")
        messages.success(request, f"Faculty attendance updated for {saved_count} staff members for {post_date.strftime('%d %b %Y')}.")
        return redirect(f"{request.path}?date={post_date.isoformat()}&month_year={month_year}&date_from={date_from}&date_to={date_to}")

    # Build attendance query for logs report
    records_qs = FacultyAttendance.objects.filter(faculty__department=dept).select_related('faculty__user', 'marked_by')

    if month_year:
        try:
            yr, mn = map(int, month_year.split('-'))
            records_qs = records_qs.filter(date__year=yr, date__month=mn)
        except ValueError:
            pass
    elif date_from or date_to:
        if date_from:
            records_qs = records_qs.filter(date__gte=date_from)
        if date_to:
            records_qs = records_qs.filter(date__lte=date_to)
    else:
        records_qs = records_qs.filter(date=selected_date)

    records = records_qs.order_by('-date', 'faculty__employee_id')

    # Current daily attendance status for each faculty for the selected mark date
    today_records = {
        att.faculty_id: att for att in FacultyAttendance.objects.filter(faculty__department=dept, date=selected_date)
    }

    # Detect 3-hour lockout for Absent records
    now = timezone.now()
    locked_absent_map = {}
    for fac_id, rec in today_records.items():
        if rec.is_absent_locked:
            remaining_secs = rec.absent_lock_remaining_seconds
            rem_hrs = int(remaining_secs // 3600)
            rem_mins = int((remaining_secs % 3600) // 60)
            rem_secs = int(remaining_secs % 60)
            unlock_dt = rec.absent_locked_until.astimezone(timezone.get_current_timezone())
            locked_absent_map[fac_id] = {
                'remaining_seconds': remaining_secs,
                'remaining_str': f"{rem_hrs}h {rem_mins}m {rem_secs}s" if rem_hrs > 0 else f"{rem_mins}m {rem_secs}s",
                'unlock_time': unlock_dt.strftime('%I:%M:%S %p'),
                'unlock_timestamp': int(rec.absent_locked_until.timestamp() * 1000),
            }

    # Accurately compute initial present/absent/leave/half-day matching what is displayed in the mark form
    total_present = sum(
        1 for fac in department_faculty
        if (fac.id in today_records and today_records[fac.id].status == 'P')
        or (fac.id not in today_records and fac.id not in approved_leaves)
    )
    total_absent  = sum(
        1 for fac in department_faculty
        if fac.id in today_records and today_records[fac.id].status == 'A'
    )
    total_leave   = sum(
        1 for fac in department_faculty
        if (fac.id in today_records and today_records[fac.id].status == 'L')
        or (fac.id not in today_records and fac.id in approved_leaves and not approved_leaves[fac.id].is_half_day)
    )
    total_half_day = sum(
        1 for fac in department_faculty
        if (fac.id in today_records and today_records[fac.id].status == 'HD')
        or (fac.id not in today_records and fac.id in approved_leaves and approved_leaves[fac.id].is_half_day)
    )
    total_half_day_eq = round(total_half_day * 0.5, 1)

    context = {
        'department':         dept,
        'department_faculty': department_faculty,
        'selected_date':      selected_date.isoformat(),
        'today_records':      today_records,
        'approved_leaves':    approved_leaves,
        'locked_absent_map':  locked_absent_map,
        'records':            records,
        'month_year':         month_year,
        'date_from':          date_from,
        'date_to':            date_to,
        'total_present':      total_present,
        'total_absent':       total_absent,
        'total_leave':        total_leave,
        'total_half_day':     total_half_day,
        'total_half_day_eq':  total_half_day_eq,
    }
    return render(request, 'hod/faculty_attendance.html', context)

# ─────────────────────────────────────────────
# ACHIEVEMENTS VERIFICATION
# ─────────────────────────────────────────────
@hod_required
def verify_achievements(request):
    dept = request.department
    achievements = Achievement.objects.filter(
        Q(user__student_profile__branch=dept) | Q(user__faculty_profile__department=dept)
    ).select_related('user').order_by('is_verified', '-date_achieved')
    
    return render(request, 'hod/verify_achievements.html', {'achievements': achievements})

@hod_required
@require_POST
def verify_achievement_action(request, pk, action_type):
    dept = request.department
    ach = get_object_or_404(Achievement, id=pk)
    
    # Verify the user belongs to the HOD's department
    user_branch = None
    if ach.user.role == 'student':
        user_branch = ach.user.student_profile.branch
    elif ach.user.role in ['faculty', 'hod', 'lab_technician']:
        user_branch = ach.user.faculty_profile.department
        
    if user_branch != dept:
        messages.error(request, "Unauthorized to verify achievements outside your branch.")
        return redirect('hod:verify_achievements')
        
    if action_type == 'approve':
        ach.is_verified = True
        ach.verified_by = request.user
        ach.save()
        messages.success(request, f"Achievement '{ach.title}' approved.")
    elif action_type == 'reject':
        ach.delete()
        messages.success(request, "Achievement rejected and deleted.")
        
    return redirect('hod:verify_achievements')

# ─────────────────────────────────────────────
# STUDENT & FACULTY SCOPED CRUD
# ─────────────────────────────────────────────
@hod_required
def manage_students(request):
    dept = request.department
    qs = Student.objects.filter(branch=dept, user__is_deleted=False).select_related('user', 'year', 'section').order_by('roll_number')
    
    search = request.GET.get('q', '')
    if search:
        qs = qs.filter(
            Q(roll_number__icontains=search) | 
            Q(user__first_name__icontains=search) | 
            Q(user__last_name__icontains=search) |
            Q(branch__code__icontains=search) |
            Q(branch__name__icontains=search) |
            Q(section__name__icontains=search) |
            Q(year__year__icontains=search)
        )
        
    paginator = Paginator(qs, 25)
    page = paginator.get_page(request.GET.get('page', 1))
    return render(request, 'hod/manage_students.html', {'page': page, 'search': search, 'department': dept})

@hod_required
def add_student(request):
    dept = request.department
    years = Year.objects.all()
    sections = Section.objects.filter(branch=dept).select_related('year')
    faculties = Faculty.objects.filter(department=dept, is_active=True).select_related('user')
    
    if request.method == 'POST':
        p = request.POST
        username = p.get('username', '').strip().upper()
        
        first_name = p.get('first_name', '').strip()
        last_name  = p.get('last_name',  '').strip()

        if len(first_name) < 3:
            messages.error(request, "First name must be at least 3 characters long.")
            return redirect('hod:add_student')
        if len(last_name) < 1:
            messages.error(request, "Last name must be at least 1 character long.")
            return redirect('hod:add_student')
            
        if User.objects.filter(username=username).exists():
            messages.error(request, f"Student Roll Number '{username}' already exists.")
            return redirect('hod:add_student')
            
        email = p.get('email', '').strip()
        if not email:
            email = f"{username}@vvitu.net"

        temp_pwd = p.get('password', '').strip() or generate_secure_temp_password()
        user = User.objects.create_user(
            username=username,
            password=temp_pwd,
            first_name=first_name,
            last_name=last_name,
            email=email,
            role='student',
            phone=p.get('phone', ''),
        )
        
        fees_val = p.get('fees_pending')
        fees_pending_amount = 0.00
        if fees_val is not None and fees_val != '':
            try:
                fees_pending_amount = float(fees_val)
            except ValueError:
                pass

        Student.objects.create(
            user=user,
            roll_number=username,
            branch=dept,
            year_id=p.get('year'),
            section_id=p.get('section'),
            class_teacher_id=p.get('class_teacher') or None,
            counsellor_id=p.get('counsellor') or None,
            admission_year=p.get('admission_year', 2024),
            parent_name=p.get('parent_name', '').strip() or None,
            parent_occupation=p.get('parent_occupation', '').strip() or None,
            parent_mobile=p.get('parent_mobile', '').strip() or None,
            personal_mobile=p.get('personal_mobile', '').strip() or None,
            gender=p.get('gender', '').strip() or None,
            caste=p.get('caste', '').strip() or None,
            religion=p.get('religion', '').strip() or None,
            permanent_address=p.get('permanent_address', '').strip() or None,
            present_address=p.get('present_address', '').strip() or None,
            fees_pending=fees_pending_amount,
            fees_updated_at=timezone.now() if fees_pending_amount > 0 else None,
        )
        
        Notification.objects.create(
            title="Student Account Created by HOD",
            message=f"HOD {request.user.get_full_name() or request.user.username} created student {first_name} {last_name} ({username}) in department {dept.code}.",
            notif_type=Notification.TYPE_SYSTEM,
            priority=Notification.PRIORITY_HIGH,
            target_all=False,
            target_role='admin',
            created_by=request.user
        )
        
        messages.success(request, f"Student {username} created successfully.")
        return redirect('hod:manage_students')
        
    return render(request, 'hod/add_student.html', {
        'years': years,
        'sections': sections,
        'faculties': faculties,
        'department': dept,
    })

@hod_required
def edit_student(request, pk):
    dept = request.department
    student = get_object_or_404(Student, pk=pk, branch=dept)
    years = Year.objects.all()
    sections = Section.objects.filter(branch=dept).select_related('year')
    faculties = Faculty.objects.filter(department=dept, is_active=True).select_related('user')
    
    if request.method == 'POST':
        p = request.POST
        first_name = p.get('first_name', '').strip()
        last_name  = p.get('last_name',  '').strip()

        if len(first_name) < 3:
            messages.error(request, "First name must be at least 3 characters long.")
            return redirect('hod:edit_student', pk=pk)
        if len(last_name) < 1:
            messages.error(request, "Last name must be at least 1 character long.")
            return redirect('hod:edit_student', pk=pk)
            
        u = student.user
        u.first_name = first_name
        u.last_name = last_name
        u.phone = p.get('phone', u.phone)
        email = p.get('email', '').strip()
        u.email = email or f"{student.roll_number}@vvitu.net"

        password = p.get('password', '').strip()
        if password:
            if len(password) < 6:
                messages.error(request, "Password must be at least 6 characters long.")
                return redirect('hod:edit_student', pk=pk)
            u.set_password(password)
            student.is_first_login = False

        u.save()
        
        student.year_id = p.get('year', student.year_id)
        student.section_id = p.get('section', student.section_id)
        student.class_teacher_id = p.get('class_teacher') or None
        student.counsellor_id = p.get('counsellor') or None
        student.parent_name = p.get('parent_name', '').strip() or None
        student.parent_occupation = p.get('parent_occupation', '').strip() or None
        student.parent_mobile = p.get('parent_mobile', '').strip() or None
        student.personal_mobile = p.get('personal_mobile', '').strip() or None
        student.gender = p.get('gender', '').strip() or None
        student.caste = p.get('caste', '').strip() or None
        student.religion = p.get('religion', '').strip() or None
        student.permanent_address = p.get('permanent_address', '').strip() or None
        student.present_address = p.get('present_address', '').strip() or None

        fees_val = p.get('fees_pending')
        if fees_val is not None and fees_val != '':
            try:
                student.fees_pending = float(fees_val)
                student.fees_updated_at = timezone.now()
            except ValueError:
                pass

        student.save()
        
        Notification.objects.create(
            title="Student Account Updated by HOD",
            message=f"HOD {request.user.get_full_name() or request.user.username} updated student {first_name} {last_name} ({student.roll_number}) details.",
            notif_type=Notification.TYPE_SYSTEM,
            priority=Notification.PRIORITY_HIGH,
            target_all=False,
            target_role='admin',
            created_by=request.user
        )
        
        messages.success(request, f"Student {student.roll_number} updated.")
        return redirect('hod:manage_students')
        
    return render(request, 'hod/edit_student.html', {
        'student': student,
        'years': years,
        'sections': sections,
        'faculties': faculties,
    })

@hod_required
def delete_student(request, pk):
    dept = request.department
    student = get_object_or_404(Student, pk=pk, branch=dept)
    if request.method == 'POST':
        user = student.user
        user.is_active = False
        user.is_deleted = True
        user.deleted_by_name = f"{request.user.get_full_name() or request.user.username} ({request.user.role.upper()})"
        from django.utils import timezone
        user.deleted_at = timezone.now()
        user.save()
        
        Notification.objects.create(
            title="Student Account Deleted by HOD",
            message=f"HOD {request.user.get_full_name() or request.user.username} deleted student {student.roll_number}.",
            notif_type=Notification.TYPE_SYSTEM,
            priority=Notification.PRIORITY_HIGH,
            target_all=False,
            target_role='admin',
            created_by=request.user
        )
        
        messages.success(request, "Student profile soft-deleted successfully.")
    return redirect('hod:manage_students')


@hod_required
def manage_faculty(request):
    dept = request.department
    faculties = Faculty.objects.filter(department=dept, user__is_deleted=False).select_related('user').order_by('employee_id')
    return render(request, 'hod/manage_faculty.html', {'faculties': faculties, 'department': dept})

@hod_required
def add_faculty(request):
    dept = request.department
    if request.method == 'POST':
        p = request.POST
        emp_id = p.get('employee_id', '').strip().upper()
        first_name = p.get('first_name', '').strip()
        last_name  = p.get('last_name',  '').strip()

        if len(first_name) < 3:
            messages.error(request, "First name must be at least 3 characters long.")
            return redirect('hod:add_faculty')
        if len(last_name) < 1:
            messages.error(request, "Last name must be at least 1 character long.")
            return redirect('hod:add_faculty')
            
        if User.objects.filter(username=emp_id).exists():
            messages.error(request, f"Employee ID '{emp_id}' already exists.")
            return redirect('hod:add_faculty')
            
        email = p.get('email', '').strip()
        temp_pwd = p.get('password', '').strip() or generate_secure_temp_password()
        user = User.objects.create_user(
            username=emp_id,
            password=temp_pwd,
            first_name=first_name,
            last_name=last_name,
            email=email,
            role='faculty',
            phone=p.get('phone', ''),
        )
        
        Faculty.objects.create(
            user=user,
            employee_id=emp_id,
            department=dept,
            designation=p.get('designation', 'Assistant Professor'),
        )
        
        Notification.objects.create(
            title="Faculty Account Created by HOD",
            message=f"HOD {request.user.get_full_name() or request.user.username} created faculty member {first_name} {last_name} ({emp_id}).",
            notif_type=Notification.TYPE_SYSTEM,
            priority=Notification.PRIORITY_HIGH,
            target_all=False,
            target_role='admin',
            created_by=request.user
        )
        
        messages.success(request, f"Faculty {emp_id} created successfully! (Initial Password: {temp_pwd})")
        return redirect('hod:manage_faculty')
        
    return render(request, 'hod/add_faculty.html')

@hod_required
def edit_faculty(request, pk):
    dept = request.department
    fac = get_object_or_404(Faculty, pk=pk, department=dept)
    
    if request.method == 'POST':
        p = request.POST
        first_name = p.get('first_name', '').strip()
        last_name  = p.get('last_name',  '').strip()

        if len(first_name) < 3:
            messages.error(request, "First name must be at least 3 characters long.")
            return redirect('hod:edit_faculty', pk=pk)
        if len(last_name) < 1:
            messages.error(request, "Last name must be at least 1 character long.")
            return redirect('hod:edit_faculty', pk=pk)
            
        u = fac.user
        u.first_name = first_name
        u.last_name = last_name
        u.phone = p.get('phone', u.phone)
        u.email = p.get('email', '').strip()

        password = p.get('password', '').strip()
        if password:
            if len(password) < 6:
                messages.error(request, "Password must be at least 6 characters long.")
                return redirect('hod:edit_faculty', pk=pk)
            u.set_password(password)

        u.save()
        
        fac.designation = p.get('designation', fac.designation)
        fac.save()
        
        Notification.objects.create(
            title="Faculty Account Updated by HOD",
            message=f"HOD {request.user.get_full_name() or request.user.username} updated faculty member {first_name} {last_name} ({fac.employee_id}) details.",
            notif_type=Notification.TYPE_SYSTEM,
            priority=Notification.PRIORITY_HIGH,
            target_all=False,
            target_role='admin',
            created_by=request.user
        )
        
        messages.success(request, f"Faculty {fac.employee_id} updated.")
        return redirect('hod:manage_faculty')
        
    return render(request, 'hod/edit_faculty.html', {'fac': fac})

# ─────────────────────────────────────────────
# ATTENDANCE LIST & EDIT OVERRIDE
# ─────────────────────────────────────────────
@hod_required
def attendance_list(request):
    dept = request.department
    # Fetch sections in branch
    sections = Section.objects.filter(branch=dept)
    
    section_id = request.GET.get('section', '')
    date_str = request.GET.get('date', '')
    
    records = []
    selected_section = None
    selected_date = None
    
    if section_id and date_str:
        try:
            selected_section = Section.objects.get(id=section_id, branch=dept)
            selected_date = dt.datetime.strptime(date_str, '%Y-%m-%d').date()
            records = Attendance.objects.filter(
                student__section=selected_section,
                date=selected_date
            ).select_related('student__user', 'timetable_entry__subject', 'timetable_entry__faculty__user')
        except (ValueError, Section.DoesNotExist, Exception) as e:
            logger.warning(f"HOD attendance_list fetch failed for section={section_id}, date={date_str}: {e}")
            
    return render(request, 'hod/attendance_list.html', {
        'sections': sections,
        'records': records,
        'selected_section_id': section_id,
        'selected_date': date_str,
    })

@hod_required
def edit_attendance(request, pk):
    dept = request.department
    record = get_object_or_404(Attendance, pk=pk, student__branch=dept)
    
    if request.method == 'POST':
        status = request.POST.get('status')
        if status in ['P', 'A']:
            record.status = status
            record.save()
            messages.success(request, f"Attendance for {record.student.roll_number} updated to {record.get_status_display()}.")
            return redirect(f"/hod/attendance/?section={record.student.section.id}&date={record.date.strftime('%Y-%m-%d')}")
            
    return render(request, 'hod/edit_attendance.html', {'record': record})

@hod_required
def release_results(request):
    dept = request.department
    exams = (
        Exam.objects
        .filter(branch=dept)
        .select_related('year')
        .prefetch_related('release')
        .order_by('-date')
    )

    # Build a status dict {exam_id: ResultRelease}
    release_map = {}
    for exam in exams:
        try:
            release_map[exam.id] = exam.release
        except ResultRelease.DoesNotExist:
            release_map[exam.id] = None

    if request.method == 'POST':
        exam_id = request.POST.get('exam_id')
        action  = request.POST.get('action')   # 'release' or 'unrelease'

        # Ensure HOD can only release results for their branch's exams
        exam = get_object_or_404(Exam, pk=exam_id, branch=dept)

        release_obj, _ = ResultRelease.objects.get_or_create(exam=exam)

        if action == 'release':
            release_obj.released    = True
            release_obj.released_at = timezone.now()
            release_obj.released_by = request.user
            release_obj.save()

            # Create in-app Notification for students
            Notification.objects.create(
                title=f"Result Released: {exam.name}",
                message=f"Results for '{exam.name}' have been published by HOD {dept.code}. Log in to your student portal to view your grades and CGPA.",
                notif_type=Notification.TYPE_RESULT,
                priority=Notification.PRIORITY_URGENT,
                target_role='student',
                target_branch=dept,
                created_by=request.user
            )

            # Send emails & parent SMS if not already sent
            sms_sent_count = 0
            student_results = {}
            results_qs = Result.objects.filter(exam=exam).select_related('student__user', 'subject')
            for r in results_qs:
                if r.student_id not in student_results:
                    student_results[r.student_id] = {'student': r.student, 'results': []}
                student_results[r.student_id]['results'].append(r)

            for sid, data in student_results.items():
                from core.sms_utils import send_result_notifications
                if send_result_notifications(data['student'], exam, data['results']):
                    sms_sent_count += 1

            if not release_obj.email_sent:
                sent, failed = _send_result_emails(exam, request)
                release_obj.email_sent = True
                release_obj.save()
                messages.success(
                    request,
                    f"Results released for '{exam.name}'. Emails sent: {sent}, Parent SMS sent: {sms_sent_count}."
                )
            else:
                messages.success(request, f"Results released for '{exam.name}'. Parent SMS sent: {sms_sent_count}.")
                messages.success(request, f"Results released for '{exam.name}'.")

            Notification.objects.create(
                title="Results Released by HOD",
                message=f"HOD {request.user.get_full_name() or request.user.username} released results for exam {exam.name}.",
                notif_type=Notification.TYPE_SYSTEM,
                priority=Notification.PRIORITY_HIGH,
                target_all=False,
                target_role='admin',
                created_by=request.user
            )

        elif action == 'unrelease':
            release_obj.released = False
            release_obj.save()
            messages.warning(request, f"Results hidden for '{exam.name}'.")

            Notification.objects.create(
                title="Results Hidden by HOD",
                message=f"HOD {request.user.get_full_name() or request.user.username} hid results for exam {exam.name}.",
                notif_type=Notification.TYPE_SYSTEM,
                priority=Notification.PRIORITY_HIGH,
                target_all=False,
                target_role='admin',
                created_by=request.user
            )

        return redirect('hod:release_results')

    context = {
        'department':  dept,
        'exams':       exams,
        'release_map': release_map,
    }
    return render(request, 'hod/release_results.html', context)


# ─────────────────────────────────────────────
# SUBJECT CRUD
# ─────────────────────────────────────────────
@hod_required
def manage_subjects(request):
    dept = request.department
    years = Year.objects.all().order_by('year')
    qs = Subject.objects.filter(branch=dept, is_deleted=False).select_related('year', 'faculty__user').order_by('year', 'semester', 'name')
    
    search = request.GET.get('q', '').strip()
    year_filter = request.GET.get('year', '').strip()
    sem_filter = request.GET.get('sem', '').strip()
    type_filter = request.GET.get('type', '').strip()

    if search:
        qs = qs.filter(
            Q(name__icontains=search) | 
            Q(code__icontains=search) |
            Q(faculty__user__first_name__icontains=search) |
            Q(faculty__user__last_name__icontains=search)
        )
    if year_filter:
        qs = qs.filter(year_id=year_filter)
    if sem_filter:
        qs = qs.filter(semester=sem_filter)
    if type_filter == 'lab':
        qs = qs.filter(is_lab=True)
    elif type_filter == 'theory':
        qs = qs.filter(is_lab=False)
        
    paginator = Paginator(qs, 25)
    page = paginator.get_page(request.GET.get('page', 1))
    return render(request, 'hod/manage_subjects.html', {
        'page': page,
        'search': search,
        'year_filter': year_filter,
        'sem_filter': sem_filter,
        'type_filter': type_filter,
        'years': years,
        'department': dept,
    })



@hod_required
def add_subject(request):
    dept = request.department
    years = Year.objects.all()
    faculties = Faculty.objects.filter(department=dept, is_active=True).select_related('user')
    
    if request.method == 'POST':
        p = request.POST
        name = p.get('name', '').strip()
        code = p.get('code', '').strip().upper()
        year_id = p.get('year')
        semester = p.get('semester')
        faculty_id = p.get('faculty') or None
        credits_val = p.get('credits', '3')
        is_lab = p.get('is_lab') == 'true'
        
        if not name or not code or not year_id or not semester:
            messages.error(request, "Please fill in all required fields.")
            return redirect('hod:add_subject')
            
        if Subject.objects.filter(code=code).exists():
            messages.error(request, f"Subject code '{code}' already exists.")
            return redirect('hod:add_subject')
            
        try:
            credits_int = int(credits_val)
        except ValueError:
            credits_int = 3
            
        Subject.objects.create(
            name=name,
            code=code,
            branch=dept,
            year_id=year_id,
            semester=semester,
            faculty_id=faculty_id,
            credits=credits_int,
            is_lab=is_lab
        )
        
        Notification.objects.create(
            title="Subject Created by HOD",
            message=f"HOD {request.user.get_full_name() or request.user.username} created subject {name} ({code}) in department {dept.code}.",
            notif_type=Notification.TYPE_SYSTEM,
            priority=Notification.PRIORITY_HIGH,
            target_all=False,
            target_role='admin',
            created_by=request.user
        )
        
        messages.success(request, f"Subject '{name}' created successfully.")
        return redirect('hod:manage_subjects')
        
    return render(request, 'hod/add_subject.html', {
        'years': years,
        'faculties': faculties,
        'department': dept,
        'semester_choices': Subject.SEMESTER_CHOICES,
    })


@hod_required
def delete_subject(request, pk):
    dept = request.department
    subject = get_object_or_404(Subject, pk=pk, branch=dept)
    if request.method == 'POST':
        subject.is_deleted = True
        subject.deleted_by_name = f"{request.user.get_full_name() or request.user.username} ({request.user.role.upper()})"
        from django.utils import timezone
        subject.deleted_at = timezone.now()
        subject.save()
        
        Notification.objects.create(
            title="Subject Deleted by HOD",
            message=f"HOD {request.user.get_full_name() or request.user.username} soft-deleted subject {subject.name} ({subject.code}) in department {dept.code}.",
            notif_type=Notification.TYPE_SYSTEM,
            priority=Notification.PRIORITY_HIGH,
            target_all=False,
            target_role='admin',
            created_by=request.user
        )
        
        messages.success(request, "Subject soft-deleted successfully.")
    return redirect('hod:manage_subjects')


# ─────────────────────────────────────────────
# HOD LEAVE MANAGEMENT & APPLICATION
# ─────────────────────────────────────────────
@hod_required
def manage_leave_requests(request):
    dept = request.department
    status_filter = request.GET.get('status', '')
    
    if request.method == 'POST':
        leave_type = request.POST.get('leave_type')
        session = request.POST.get('session', 'full').strip()
        start_date_str = request.POST.get('start_date')
        end_date_str = request.POST.get('end_date')
        reason = request.POST.get('reason', '').strip()
        substitute_notes = request.POST.get('substitute_notes', '').strip()

        if leave_type == 'half_day_an':
            session = 'an'
        elif leave_type == 'half_day_fn':
            session = 'fn'

        if not end_date_str and start_date_str and session in ('an', 'fn'):
            end_date_str = start_date_str
        
        if not leave_type or not start_date_str or not end_date_str or not reason:
            messages.error(request, "Please fill in all required leave application fields.")
        else:
            try:
                start_date = dt.datetime.strptime(start_date_str, '%Y-%m-%d').date()
                end_date = dt.datetime.strptime(end_date_str, '%Y-%m-%d').date()
                
                if end_date < start_date:
                    messages.error(request, "End date cannot be earlier than start date.")
                else:
                    is_half = (session in ('an', 'fn')) or (leave_type in ('half_day_an', 'half_day_fn'))
                    req_days = 0.5 if is_half else float((end_date - start_date).days + 1)
                    
                    already_taken = request.faculty.get_monthly_leaves_taken(start_date.year, start_date.month)
                    monthly_limit = float(request.faculty.monthly_leave_limit or 2.0)
                    is_limit_exceeded = (already_taken + req_days) > monthly_limit

                    leave_req = FacultyLeaveRequest.objects.create(
                        faculty=request.faculty,
                        leave_type=leave_type,
                        session=session,
                        start_date=start_date,
                        end_date=end_date,
                        reason=reason,
                        substitute_notes=substitute_notes,
                        is_limit_exceeded=is_limit_exceeded,
                        status='pending'
                    )
                    
                    # Notify Admin about HOD leave request
                    try:
                        emergency_prefix = "⚠️ [EMERGENCY LEAVE - LIMIT EXCEEDED] " if is_limit_exceeded else ""
                        Notification.objects.create(
                            title=f"{emergency_prefix}HOD Leave Application — {request.faculty.full_name}",
                            message=(
                                f"{'⚠️ EMERGENCY LEAVE ' if is_limit_exceeded else ''}HOD {request.faculty.full_name} ({dept.code}) applied for {leave_req.get_leave_type_display()} "
                                f"from {start_date.strftime('%d-%b-%Y')} to {end_date.strftime('%d-%b-%Y')}. "
                                f"Admin approval is required."
                            ),
                            notif_type=Notification.TYPE_ANNOUNCEMENT,
                            priority=Notification.PRIORITY_HIGH,
                            target_all=False,
                            target_role='admin',
                            created_by=request.user
                        )
                    except Exception as notif_err:
                        logger.warning(f"Failed to create HOD leave notification for admin: {notif_err}")
                        
                    if is_limit_exceeded:
                        messages.warning(request, f"Your leave application has been submitted as an EMERGENCY LEAVE request (exceeds monthly limit of {monthly_limit} days). Pending Admin approval.")
                    else:
                        messages.success(request, "Your leave application has been submitted to College Administration for approval.")
                    return redirect('hod:manage_leave_requests')
            except ValueError:
                messages.error(request, "Invalid date format submitted.")
    
    # HOD's own leave applications
    my_leaves = FacultyLeaveRequest.objects.filter(
        faculty=request.faculty
    ).order_by('-created_at')
    
    # Department faculty leaves (excluding HOD's own leave request from actioning queue)
    dept_faculty_leaves = FacultyLeaveRequest.objects.filter(
        faculty__department=dept
    ).exclude(
        faculty=request.faculty
    ).select_related('faculty__user', 'action_by').order_by('-created_at')
    
    if status_filter in ['pending', 'approved', 'rejected']:
        dept_faculty_leaves = dept_faculty_leaves.filter(status=status_filter)
        
    pending_count = FacultyLeaveRequest.objects.filter(
        faculty__department=dept, 
        status='pending'
    ).exclude(faculty=request.faculty).count()

    now = timezone.now()
    hod_monthly_limit = float(request.faculty.monthly_leave_limit or 2.0)
    hod_leaves_used = request.faculty.get_monthly_leaves_taken(now.year, now.month)
    hod_leaves_remaining = request.faculty.get_monthly_leaves_remaining(now.year, now.month)
    hod_is_limit_reached = request.faculty.is_leave_limit_reached(now.year, now.month)
    
    return render(request, 'hod/leave_requests.html', {
        'department': dept,
        'leaves': dept_faculty_leaves,
        'my_leaves': my_leaves,
        'status_filter': status_filter,
        'pending_count': pending_count,
        'hod_monthly_limit': hod_monthly_limit,
        'hod_leaves_used': hod_leaves_used,
        'hod_leaves_remaining': hod_leaves_remaining,
        'hod_is_limit_reached': hod_is_limit_reached,
        'current_month_name': now.strftime('%B %Y'),
        'leave_type_choices': FacultyLeaveRequest.LEAVE_TYPE_CHOICES,
    })


@hod_required
def action_leave_request(request, pk, action):
    dept = request.department
    leave_req = get_object_or_404(FacultyLeaveRequest, pk=pk, faculty__department=dept)
    
    # Guard: HOD cannot approve or reject their own leave or another HOD's leave!
    if leave_req.faculty == request.faculty or leave_req.faculty.user.role == 'hod':
        messages.error(request, "HOD leave applications can only be approved or rejected by College Administration.")
        return redirect('hod:manage_leave_requests')
    
    if action not in ['approve', 'reject']:
        messages.error(request, "Invalid leave action.")
        return redirect('hod:manage_leave_requests')
        
    remarks = request.POST.get('remarks', '').strip() if request.method == 'POST' else ''
    
    new_status = 'approved' if action == 'approve' else 'rejected'
    leave_req.status = new_status
    leave_req.action_by = request.user
    leave_req.action_at = timezone.now()
    if remarks:
        leave_req.admin_remarks = remarks
    leave_req.save()

    # Automatically create/sync FacultyAttendance records for each day of the approved leave
    if new_status == 'approved':
        att_status = 'HD' if leave_req.is_half_day else 'L'
        curr_d = leave_req.start_date
        while curr_d <= leave_req.end_date:
            FacultyAttendance.objects.update_or_create(
                faculty=leave_req.faculty,
                date=curr_d,
                defaults={
                    'status': att_status,
                    'remarks': f"Approved {leave_req.get_leave_type_display()}",
                    'marked_by': request.user,
                }
            )
            curr_d += dt.timedelta(days=1)
    
    try:
        status_text = "Approved" if new_status == 'approved' else "Rejected"
        notif_msg = (
            f"Your leave request for {leave_req.get_leave_type_display()} "
            f"({leave_req.start_date.strftime('%d-%b-%Y')} to {leave_req.end_date.strftime('%d-%b-%Y')}) "
            f"has been {status_text} by HOD ({request.user.get_full_name() or request.user.username})."
        )
        if remarks:
            notif_msg += f" Remarks: {remarks}"
            
        Notification.objects.create(
            title=f"Leave Request {status_text}",
            message=notif_msg,
            notif_type=Notification.TYPE_ANNOUNCEMENT,
            priority=Notification.PRIORITY_HIGH,
            target_user=leave_req.faculty.user,
            target_role='faculty',
            target_all=False,
            created_by=request.user
        )
        
        # 1. Email Notification
        if leave_req.faculty.user.email:
            email_subject = f"[Leave Request {status_text}] VVITU Faculty Leave Status Update"
            email_body = f"""Dear {leave_req.faculty.full_name},

Your leave application request has been reviewed by your HOD.

Details:
- Leave Type: {leave_req.get_leave_type_display()}
- Duration: {leave_req.start_date.strftime('%d-%b-%Y')} to {leave_req.end_date.strftime('%d-%b-%Y')} ({leave_req.total_days} days)
- Status: {status_text.upper()}
- Action By: HOD ({request.user.get_full_name() or request.user.username})
- Remarks: {remarks if remarks else 'N/A'}

Please log in to the VVITU Portal to view your leave history.

Regards,
VVIT University Administration
"""
            send_mail(
                subject=email_subject,
                message=email_body,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@vvitu.ac.in'),
                recipient_list=[leave_req.faculty.user.email],
                fail_silently=True
            )
            
        # 2. SMS Notification
        from core.sms_utils import send_sms
        phone_num = leave_req.faculty.phone or getattr(leave_req.faculty.user, 'phone', '')
        if phone_num:
            sms_text = f"VVITU ALERT: Your {leave_req.get_leave_type_display()} leave request ({leave_req.start_date.strftime('%d/%m')} to {leave_req.end_date.strftime('%d/%m')}) has been {status_text} by HOD. Log in for details."
            send_sms(phone_num, sms_text)

    except Exception as dispatch_err:
        logger.warning(f"Failed to send leave action notification/SMS/email: {dispatch_err}")
        
    messages.success(request, f"Leave request for {leave_req.faculty.full_name} {new_status} successfully.")
    return redirect('hod:manage_leave_requests')


@hod_required
def cancel_leave_request(request, pk):
    leave_req = get_object_or_404(FacultyLeaveRequest, pk=pk, faculty=request.faculty, status='pending')
    leave_req.delete()
    messages.success(request, "Your leave application has been cancelled.")
    return redirect('hod:manage_leave_requests')


@hod_required
def upload_mid_marks(request):
    """
    Allows HOD to add and edit Mid Term 1 and Mid Term 2 marks for any subject
    and student in their department branch. Semester Final marks are strictly excluded.
    """
    from faculty.views import upload_marks
    return upload_marks(request)


@hod_required
def manage_fees(request):
    """
    Allows HOD to view, update, and manage student fee structures and payments for their branch.
    """
    from accounts.models import Student, StudentFee
    from core.models import Year
    from django.db.models import Q

    dept = request.department
    years = Year.objects.all()
    
    year_id = request.GET.get('year', '')
    status_filter = request.GET.get('status', '')
    search = request.GET.get('q', '').strip()

    students = Student.objects.filter(branch=dept, is_active=True, user__is_deleted=False).select_related('user', 'branch', 'section', 'year').order_by('roll_number')

    if year_id:
        students = students.filter(year_id=year_id)
    if search:
        students = students.filter(
            Q(roll_number__icontains=search) |
            Q(user__first_name__icontains=search) |
            Q(user__last_name__icontains=search) |
            Q(user__username__icontains=search) |
            Q(branch__code__icontains=search) |
            Q(branch__name__icontains=search)
        )

    sel_year = Year.objects.filter(id=year_id).first() if year_id else Year.objects.first()
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'update_single':
            stu_id = request.POST.get('student_id')
            stu = get_object_or_404(Student, id=stu_id, branch=dept)

            def parse_val(v, max_limit=10000000.0):
                if not v: return 0.0
                try:
                    val = float(str(v).strip())
                    if val < 0: return 0.0
                    if val > max_limit: return max_limit
                    return round(val, 2)
                except (ValueError, TypeError, OverflowError): return 0.0

            col = parse_val(request.POST.get('college_fee'))
            hos = parse_val(request.POST.get('hostel_fee'))
            bus = parse_val(request.POST.get('bus_fee'))
            nba = parse_val(request.POST.get('nba_fee'))
            exm = parse_val(request.POST.get('exam_fee'))
            bbk = parse_val(request.POST.get('book_bank_fee'))
            oth = parse_val(request.POST.get('other_fee'))
            paid = parse_val(request.POST.get('amount_paid'))
            remarks = request.POST.get('remarks', '').strip()
            due_date_str = request.POST.get('due_date', '').strip()
            due_date = due_date_str if due_date_str else None

            fee_year = stu.year or sel_year or Year.objects.first()
            fee_rec, created = StudentFee.objects.get_or_create(
                student=stu,
                academic_year=fee_year
            )
            try:
                fee_rec.college_fee = col
                fee_rec.hostel_fee = hos
                fee_rec.bus_fee = bus
                fee_rec.nba_fee = nba
                fee_rec.exam_fee = exm
                fee_rec.book_bank_fee = bbk
                fee_rec.other_fee = oth
                fee_rec.amount_paid = paid
                fee_rec.remarks = remarks
                fee_rec.due_date = due_date
                fee_rec.updated_by = request.user
                fee_rec.save()
                messages.success(request, f"Fee record updated successfully for {stu.roll_number}.")
            except Exception as err:
                logger.error(f"Error saving fee record for student {stu.roll_number}: {err}")
                messages.error(request, f"Could not update fees for {stu.roll_number}: Invalid or excessive fee amount entered.")

            return redirect(f"{request.path}?year={year_id}&q={search}&status={status_filter}")

        elif action == 'bulk_assign':
            def parse_val(v):
                if not v: return 0.0
                try: return float(str(v).strip())
                except (ValueError, TypeError): return 0.0

            col = parse_val(request.POST.get('college_fee'))
            nba = parse_val(request.POST.get('nba_fee'))
            exm = parse_val(request.POST.get('exam_fee'))
            bbk = parse_val(request.POST.get('book_bank_fee'))
            oth = parse_val(request.POST.get('other_fee'))

            count = 0
            for stu in students:
                fee_year = stu.year or sel_year or Year.objects.first()
                fee_rec, created = StudentFee.objects.get_or_create(
                    student=stu,
                    academic_year=fee_year
                )
                fee_rec.college_fee = col
                fee_rec.nba_fee = nba
                fee_rec.exam_fee = exm
                fee_rec.book_bank_fee = bbk
                fee_rec.other_fee = oth
                fee_rec.updated_by = request.user
                fee_rec.save()
                count += 1

            messages.success(request, f"Standard fee structure applied to {count} students in {dept.code}.")
            return redirect(f"{request.path}?year={year_id}")

    # Ensure every active student has a StudentFee record for their academic year
    for stu in students:
        fee_year = stu.year or sel_year or Year.objects.first()
        if fee_year:
            StudentFee.objects.get_or_create(student=stu, academic_year=fee_year)

    fee_records = StudentFee.objects.filter(student__in=students)
    if year_id:
        fee_records = fee_records.filter(academic_year_id=year_id)
    if status_filter:
        fee_records = fee_records.filter(status=status_filter)

    fee_dict = {f.student_id: f for f in fee_records}
    
    total_expected = sum(float(f.total_fee_amount) for f in fee_records)
    total_collected = sum(float(f.amount_paid) for f in fee_records)
    total_outstanding = sum(float(f.due_amount) for f in fee_records)

    return render(request, 'admin_dashboard/manage_fees.html', {
        'students': students,
        'fee_dict': fee_dict,
        'years': years,
        'department': dept,
        'sel_year': sel_year,
        'year_id': year_id,
        'search': search,
        'status_filter': status_filter,
        'total_expected': total_expected,
        'total_collected': total_collected,
        'total_outstanding': total_outstanding,
        'role': 'hod',
    })


@hod_required
def manage_class_transfers(request):
    """
    HOD View — Audit log of all class transfers, proxy assignments, and faculty class history in department.
    Allows HOD to search by faculty name, subject code, employee ID, and date range to see
    exact details of which faculty member conducted which class, at what date & time, for which section.
    """
    import datetime
    from core.transfer_utils import get_conducted_class_history

    dept = request.department
    today = timezone.localdate()

    # Search & Filter Parameters
    search_faculty = request.GET.get('search_faculty', '').strip()
    selected_fac_id = request.GET.get('faculty_id', '').strip()
    date_from_str = request.GET.get('date_from', '').strip()
    date_to_str = request.GET.get('date_to', '').strip()

    from core.transfer_utils import parse_flexible_date
    date_from = parse_flexible_date(date_from_str)
    date_to = parse_flexible_date(date_to_str)

    # Conducted Class History (Branch Scoped)
    conducted_history = get_conducted_class_history(
        branch=dept,
        faculty=selected_fac_id if selected_fac_id else None,
        search_query=search_faculty,
        date_from=date_from,
        date_to=date_to
    )

    # Department faculty list for search dropdown
    dept_faculty = Faculty.objects.filter(department=dept, is_active=True).select_related('user').order_by('user__first_name')
    day_name = today.strftime('%A')
    day_slots = Timetable.objects.filter(section__branch=dept, day__iexact=day_name).select_related('faculty__user', 'subject', 'section')

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'assign_proxy':
            timetable_id = request.POST.get('timetable_id')
            substitute_id = request.POST.get('substitute_id')
            reason = request.POST.get('reason', 'HOD Proxy Assignment')
            date_val_str = request.POST.get('date', '').strip()

            t_date = parse_flexible_date(date_val_str) or today

            slot = get_object_or_404(Timetable, id=timetable_id, section__branch=dept)
            substitute = get_object_or_404(Faculty, id=substitute_id, is_active=True)


            from core.transfer_utils import get_free_faculty_for_period
            from core.sms_utils import send_class_transfer_notification

            # Verify substitute is FREE
            free_fac = get_free_faculty_for_period(
                date=t_date,
                period=slot.period,
                department=dept,
                exclude_faculty=slot.faculty
            )

            if substitute not in free_fac:
                messages.error(
                    request,
                    f"Prof. {substitute.full_name} is NOT free during Period {slot.period} on {t_date.strftime('%d-%b-%Y')}."
                )
            else:
                transfer_obj, _ = ClassTransfer.objects.update_or_create(
                    timetable_entry=slot,
                    date=t_date,
                    defaults={
                        'original_faculty': slot.faculty,
                        'substitute_faculty': substitute,
                        'reason': reason or 'HOD Official Proxy Assignment',
                        'status': 'pending',
                        'rejection_reason': None,
                        'responded_at': None,
                        'assigned_by_role': 'hod',
                        'transfer_type': 'proxy',
                        'assigned_by': request.user,
                    }
                )

                send_class_transfer_notification(transfer_obj)
                messages.success(
                    request,
                    f"Official proxy request for Period {slot.period} ({slot.subject.code}) sent to Prof. {substitute.full_name}. Notification dispatched — class will officially transfer once accepted."
                )

        elif action == 'cancel_proxy':
            transfer_id = request.POST.get('transfer_id')
            if transfer_id:
                ct_to_cancel = ClassTransfer.objects.filter(
                    id=transfer_id
                ).filter(
                    Q(timetable_entry__section__branch=dept) | Q(original_faculty__department=dept) | Q(substitute_faculty__department=dept)
                ).first()
                if ct_to_cancel:
                    desc = f"Period {ct_to_cancel.timetable_entry.period} ({ct_to_cancel.timetable_entry.subject.code if ct_to_cancel.timetable_entry.subject else 'Class'}) on {ct_to_cancel.date.strftime('%d-%b-%Y')}"
                    ct_to_cancel.delete()
                    messages.success(request, f"Class transfer/proxy for {desc} was cancelled. Reverted to regular instructor.")
                else:
                    messages.error(request, "Class transfer record not found.")
            return redirect('hod:manage_class_transfers')

    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
    page = request.GET.get('page', 1)
    paginator = Paginator(conducted_history, 50)
    try:
        history_page = paginator.page(page)
    except PageNotAnInteger:
        history_page = paginator.page(1)
    except EmptyPage:
        history_page = paginator.page(paginator.num_pages)

    context = {
        'department': dept,
        'conducted_history': history_page,
        'history_page': history_page,
        'paginator': paginator,
        'total_records_count': len(conducted_history),
        'dept_faculty': dept_faculty,
        'day_slots': day_slots,
        'search_faculty': search_faculty,
        'selected_fac_id': selected_fac_id,
        'date_from': date_from_str,
        'date_to': date_to_str,
        'today': today,
    }
    return render(request, 'hod/manage_class_transfers.html', context)


@hod_required
def ajax_get_branch_timetable_slots(request):
    """
    Return JSON list of scheduled class slots for HOD's branch on a specific date/day_of_week.
    Each slot contains: id, period, timing, subject_code, subject_name, faculty_name, section_name.
    """
    from core.transfer_utils import parse_flexible_date
    date_str = request.GET.get('date')
    if not date_str:
        return JsonResponse({'error': 'date parameter required'}, status=400)

    req_date = parse_flexible_date(date_str)
    if not req_date:
        return JsonResponse({'error': 'Invalid date format'}, status=400)

    day_name = req_date.strftime('%A')
    dept = request.department


    slots = Timetable.objects.filter(
        section__branch=dept,
        day__iexact=day_name
    ).select_related('subject', 'faculty__user', 'section', 'section__year').order_by('period', 'section__name')

    period_timings = {
        1: "09:00 AM - 09:50 AM",
        2: "09:50 AM - 10:40 AM",
        3: "10:50 AM - 11:40 AM",
        4: "11:40 AM - 12:30 PM",
        5: "01:20 PM - 02:10 PM",
        6: "02:10 PM - 03:00 PM",
        7: "03:10 PM - 04:00 PM",
        8: "04:00 PM - 04:50 PM",
    }

    data = []
    for s in slots:
        start_t = s.start_time.strftime("%I:%M %p") if getattr(s, 'start_time', None) else None
        end_t   = s.end_time.strftime("%I:%M %p") if getattr(s, 'end_time', None) else None
        timing_str = f"{start_t} - {end_t}" if (start_t and end_t) else period_timings.get(s.period, f"Period {s.period}")

        data.append({
            'id': s.id,
            'period': s.period,
            'timing': timing_str,
            'subject_code': s.subject.code if s.subject else 'N/A',
            'subject_name': s.subject.name if s.subject else 'N/A',
            'original_faculty_id': s.faculty.id if s.faculty else None,
            'original_faculty_name': f"Prof. {s.faculty.full_name}" if s.faculty else "Unassigned",
            'section_name': f"Y{s.section.year.year} Sec {s.section.name}" if (s.section and s.section.year) else (s.section.name if s.section else ''),
        })

    return JsonResponse({'slots': data, 'day_name': day_name, 'date_str': req_date.strftime('%d-%b-%Y')})


@hod_required
def ajax_get_free_faculty(request):
    """
    Return JSON list of free faculty in HOD's branch for a specific (date, period).
    """
    from faculty.views import ajax_get_free_faculty as base_free_faculty
    return base_free_faculty(request)


# ─────────────────────────────────────────────
# HOD CLASS DIARY & SYLLABUS UNIT TRACKER
# ─────────────────────────────────────────────
@hod_required
def class_diary_coverage(request):
    """
    Allows HOD to track which faculty discussed which topics, and how many units have been completed.
    Strictly scoped to the HOD's department.
    """
    dept = request.department
    from core.transfer_utils import parse_flexible_date
    from core.models import ClassDiary

    # Filters
    search_query = request.GET.get('search', '').strip()
    faculty_id   = request.GET.get('faculty_id', '').strip()
    subject_id   = request.GET.get('subject_id', '').strip()
    section_id   = request.GET.get('section_id', '').strip()
    unit_filter  = request.GET.get('unit_number', '').strip()
    date_from_str= request.GET.get('date_from', '').strip()
    date_to_str  = request.GET.get('date_to', '').strip()

    # Scope all logs to HOD department
    base_qs = ClassDiary.objects.filter(
        Q(section__branch=dept) | Q(faculty__department=dept) | Q(subject__branch=dept)
    ).distinct().select_related('section__branch', 'section__year', 'subject', 'faculty__user')

    diary_qs = base_qs

    if search_query:
        diary_qs = diary_qs.filter(
            Q(topic_covered__icontains=search_query) |
            Q(discussion_summary__icontains=search_query) |
            Q(homework_assignment__icontains=search_query) |
            Q(faculty__user__first_name__icontains=search_query) |
            Q(faculty__user__last_name__icontains=search_query) |
            Q(subject__name__icontains=search_query) |
            Q(subject__code__icontains=search_query)
        )

    if faculty_id and faculty_id.isdigit():
        diary_qs = diary_qs.filter(faculty_id=int(faculty_id))

    if subject_id and subject_id.isdigit():
        diary_qs = diary_qs.filter(subject_id=int(subject_id))

    if section_id and section_id.isdigit():
        diary_qs = diary_qs.filter(section_id=int(section_id))

    if unit_filter and unit_filter.isdigit():
        diary_qs = diary_qs.filter(unit_number=int(unit_filter))

    date_from = parse_flexible_date(date_from_str)
    date_to   = parse_flexible_date(date_to_str)

    if date_from:
        diary_qs = diary_qs.filter(date__gte=date_from)
    if date_to:
        diary_qs = diary_qs.filter(date__lte=date_to)

    entries = diary_qs.order_by('-date', 'period')

    # Department faculty, subjects & sections for dropdown filters
    dept_faculty = Faculty.objects.filter(department=dept, is_active=True, user__is_deleted=False).select_related('user').order_by('user__first_name')
    dept_subjects = Subject.objects.filter(branch=dept, is_deleted=False).select_related('year').order_by('code')
    dept_sections = Section.objects.filter(branch=dept).select_related('year').order_by('year__year', 'name')

    # ── Syllabus / Unit Coverage Aggregation per Faculty & Subject ──
    coverage_stats = []
    timetables = Timetable.objects.filter(section__branch=dept).select_related('faculty__user', 'subject', 'section').distinct()
    pair_keys = set()

    for t in timetables:
        if not t.faculty:
            continue
        key = (t.faculty_id, t.subject_id, t.section_id)
        if key in pair_keys:
            continue
        pair_keys.add(key)

        fac = t.faculty
        subj = t.subject
        sec = t.section

        logs = base_qs.filter(faculty=fac, subject=subj, section=sec)
        total_logs = logs.count()
        covered_units = set(logs.values_list('unit_number', flat=True))

        standard_units_covered = [u for u in [1, 2, 3, 4, 5] if u in covered_units]
        unit_count = len(standard_units_covered)
        progress_pct = min(100, int((unit_count / 5.0) * 100))

        latest_log = logs.order_by('-date', '-period').first()

        # Detailed planned topic schedule analysis
        syllabus_data = get_subject_syllabus_progress(subj, faculty=fac, section=sec)

        coverage_stats.append({
            'faculty': fac,
            'subject': subj,
            'section': sec,
            'total_logs': total_logs,
            'covered_units': covered_units,
            'units_done_count': syllabus_data['units_completed_count'] or unit_count,
            'progress_pct': syllabus_data['completion_pct'] if syllabus_data['total_topics'] > 0 else progress_pct,
            'total_planned_topics': syllabus_data['total_topics'],
            'completed_planned_topics': syllabus_data['completed_topics'],
            'overdue_topics_count': syllabus_data['overdue_count'],
            'is_mid1_target_met': syllabus_data['is_mid1_target_met'],
            'mid1_deadline': syllabus_data['mid1_deadline'],
            'mid1_target_units': syllabus_data['mid1_target_units'],
            'status_label': syllabus_data['status_label'],
            'status_color': syllabus_data['status_color'],
            'latest_log': latest_log,
        })

    coverage_stats.sort(key=lambda x: (x['subject'].code, str(x['section'])))

    # Handle audit & dispatch reminders trigger
    if request.method == 'POST' and request.POST.get('action') == 'dispatch_reminders':
        sent = check_and_dispatch_syllabus_reminders(branch_id=dept.id, triggered_by=request.user)
        messages.success(request, f"Syllabus audit completed: {sent} reminder notification(s) sent to faculty with overdue topics.")
        return redirect('hod:class_diary_coverage')

    # Department KPIs
    total_dept_logs = base_qs.count()
    active_faculty_count = base_qs.values('faculty').distinct().count()
    active_subjects_count = base_qs.values('subject').distinct().count()
    avg_progress = int(sum(c['progress_pct'] for c in coverage_stats) / len(coverage_stats)) if coverage_stats else 0
    total_overdue_count = sum(c['overdue_topics_count'] for c in coverage_stats)
    delayed_mid1_count = sum(1 for c in coverage_stats if not c['is_mid1_target_met'] and c['mid1_deadline'] and timezone.localdate() > c['mid1_deadline'])

    context = {
        'entries': entries,
        'coverage_stats': coverage_stats,
        'dept': dept,
        'dept_faculty': dept_faculty,
        'dept_subjects': dept_subjects,
        'dept_sections': dept_sections,
        'total_dept_logs': total_dept_logs,
        'active_faculty_count': active_faculty_count,
        'active_subjects_count': active_subjects_count,
        'avg_progress': avg_progress,
        'total_overdue_count': total_overdue_count,
        'delayed_mid1_count': delayed_mid1_count,
        'search_query': search_query,
        'faculty_id': int(faculty_id) if faculty_id and faculty_id.isdigit() else '',
        'subject_id': int(subject_id) if subject_id and subject_id.isdigit() else '',
        'section_id': int(section_id) if section_id and section_id.isdigit() else '',
        'unit_number': int(unit_filter) if unit_filter and unit_filter.isdigit() else '',
        'unit_choices': ClassDiary.UNIT_CHOICES,
        'date_from': date_from_str,
        'date_to': date_to_str,
    }
    return render(request, 'hod/class_diary_coverage.html', context)


# ─────────────────────────────────────────────
# STUDENT COUNSELLING DOSSIER (HOD)
# ─────────────────────────────────────────────
@hod_required
def student_counselling_report(request, student_id):
    """
    View complete counselling dossier for any student in the HOD's department.
    """
    from core.counselling_utils import get_student_counselling_dossier
    from django.urls import reverse

    dept = request.department
    student = get_object_or_404(Student, id=student_id, is_active=True, user__is_deleted=False)

    if student.branch != dept and request.user.role != 'admin':
        messages.error(request, "You can only view student counselling reports within your department.")
        return redirect('hod:manage_students')

    dossier = get_student_counselling_dossier(student)
    context = {
        'dossier': dossier,
        'pdf_download_url': reverse('hod:download_student_counselling_report_pdf', args=[student.id]),
        'back_url': reverse('hod:manage_students'),
    }
    return render(request, 'reports/counselling_report.html', context)


@hod_required
def download_student_counselling_report_pdf(request, student_id):
    """
    Download official student counselling dossier PDF for HOD.
    """
    from core.counselling_utils import generate_counselling_report_pdf
    from django.http import HttpResponse

    dept = request.department
    student = get_object_or_404(Student, id=student_id, is_active=True, user__is_deleted=False)

    if student.branch != dept and request.user.role != 'admin':
        messages.error(request, "You can only download student counselling reports within your department.")
        return redirect('hod:manage_students')

    pdf_bytes = generate_counselling_report_pdf(student)
    filename = f"{student.roll_number}_Counselling_Dossier.pdf"
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


# ─────────────────────────────────────────────
# SUBJECT SYLLABUS & TOPIC SCHEDULE MANAGER (HOD)
# ─────────────────────────────────────────────
@hod_required
def manage_subject_syllabus(request, subject_id=None):
    """
    Allows HOD to view, create, edit, and manage the planned topic timetable for every subject
    in their department, set target completion dates, and audit milestone readiness.
    """
    dept = request.department
    today = timezone.localdate()
    from core.transfer_utils import parse_flexible_date

    subjects = Subject.objects.filter(branch=dept, is_deleted=False).select_related('year', 'faculty').order_by('year__year', 'semester', 'code')
    
    selected_subject = None
    if subject_id:
        selected_subject = Subject.objects.filter(id=subject_id, branch=dept, is_deleted=False).first()
        if not selected_subject:
            selected_subject = subjects.first()
    elif subjects.exists():
        selected_subject = subjects.first()

    if request.method == 'POST' and selected_subject:
        action = request.POST.get('action')

        if action == 'add_topic':
            unit_val = request.POST.get('unit_number', '1')
            unit_number = int(unit_val) if unit_val.isdigit() else 1
            topic_name = request.POST.get('topic_name', '').strip()
            target_date_str = request.POST.get('target_date', '').strip()
            target_milestone = request.POST.get('target_milestone', 'mid1')
            description = request.POST.get('description', '').strip()
            order_val = request.POST.get('order', '1')
            order = int(order_val) if order_val.isdigit() else 1

            target_date = parse_flexible_date(target_date_str) or today

            if not topic_name:
                messages.error(request, "Topic name is required.")
            else:
                SubjectTopicPlan.objects.create(
                    subject=selected_subject,
                    unit_number=unit_number,
                    topic_name=topic_name,
                    description=description,
                    target_date=target_date,
                    target_milestone=target_milestone,
                    order=order
                )
                messages.success(request, f"Topic '{topic_name}' added to Unit {unit_number} schedule.")
            return redirect('hod:manage_subject_syllabus_subject', subject_id=selected_subject.id)

        elif action == 'edit_topic':
            topic_id = request.POST.get('topic_id')
            topic = get_object_or_404(SubjectTopicPlan, id=topic_id, subject=selected_subject)
            unit_val = request.POST.get('unit_number', str(topic.unit_number))
            topic.unit_number = int(unit_val) if unit_val.isdigit() else topic.unit_number
            topic.topic_name = request.POST.get('topic_name', topic.topic_name).strip()
            target_date_str = request.POST.get('target_date', '').strip()
            if target_date_str:
                topic.target_date = parse_flexible_date(target_date_str) or topic.target_date
            topic.target_milestone = request.POST.get('target_milestone', topic.target_milestone)
            topic.description = request.POST.get('description', '').strip()
            order_val = request.POST.get('order', str(topic.order))
            topic.order = int(order_val) if order_val.isdigit() else topic.order
            
            # Allow HOD to set completion if desired
            is_comp = (request.POST.get('is_completed') == '1')
            topic.is_completed = is_comp
            if is_comp and not topic.completed_date:
                topic.completed_date = today
            elif not is_comp:
                topic.completed_date = None

            topic.save()
            messages.success(request, f"Topic '{topic.topic_name}' updated successfully.")
            return redirect('hod:manage_subject_syllabus_subject', subject_id=selected_subject.id)

        elif action == 'delete_topic':
            topic_id = request.POST.get('topic_id')
            topic = get_object_or_404(SubjectTopicPlan, id=topic_id, subject=selected_subject)
            t_name = topic.topic_name
            topic.delete()
            messages.success(request, f"Topic '{t_name}' deleted.")
            return redirect('hod:manage_subject_syllabus_subject', subject_id=selected_subject.id)

        elif action == 'bulk_add_topics':
            bulk_text = request.POST.get('bulk_topics', '').strip()
            unit_val = request.POST.get('bulk_unit_number', '1')
            unit_number = int(unit_val) if unit_val.isdigit() else 1
            target_date_str = request.POST.get('bulk_target_date', '').strip()
            target_milestone = request.POST.get('bulk_target_milestone', 'mid1')
            target_date = parse_flexible_date(target_date_str) or today

            created_count = 0
            if bulk_text:
                lines = [line.strip() for line in bulk_text.splitlines() if line.strip()]
                for idx, line in enumerate(lines, 1):
                    SubjectTopicPlan.objects.create(
                        subject=selected_subject,
                        unit_number=unit_number,
                        topic_name=line,
                        target_date=target_date,
                        target_milestone=target_milestone,
                        order=idx
                    )
                    created_count += 1
                messages.success(request, f"Successfully created {created_count} topics for Unit {unit_number}.")
            return redirect('hod:manage_subject_syllabus_subject', subject_id=selected_subject.id)

        elif action == 'send_reminders':
            sent = check_and_dispatch_syllabus_reminders(subject_id=selected_subject.id, branch_id=dept.id, triggered_by=request.user)
            messages.success(request, f"Syllabus reminders evaluated: {sent} notification(s) sent to faculty and HOD.")
            return redirect('hod:manage_subject_syllabus_subject', subject_id=selected_subject.id)

    # Progress & Topics by unit
    progress_data = None
    topics_by_unit = {}
    if selected_subject:
        progress_data = get_subject_syllabus_progress(selected_subject)
        all_topics = SubjectTopicPlan.objects.filter(subject=selected_subject).order_by('unit_number', 'order', 'target_date')
        for u in [1, 2, 3, 4, 5]:
            topics_by_unit[u] = [t for t in all_topics if t.unit_number == u]

    context = {
        'dept': dept,
        'subjects': subjects,
        'selected_subject': selected_subject,
        'progress_data': progress_data,
        'topics_by_unit': topics_by_unit,
        'unit_choices': ClassDiary.UNIT_CHOICES,
        'milestone_choices': SubjectTopicPlan.MILESTONE_CHOICES,
        'today': today,
    }
    return render(request, 'hod/manage_subject_syllabus.html', context)


# ─────────────────────────────────────────────
# EXAM TIMETABLE & SYLLABUS MILESTONE SCHEDULES (HOD)
# ─────────────────────────────────────────────
@hod_required
def manage_exam_schedules(request):
    """
    Allows HOD to view and set Exam Timetables and Syllabus Milestone targets
    (e.g., 2.5 units target before Mid-1 date) for their department.
    """
    dept = request.department
    today = timezone.localdate()
    from core.transfer_utils import parse_flexible_date

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'save_exam_schedule':
            schedule_id = request.POST.get('schedule_id')
            year_val = request.POST.get('year')
            semester = int(request.POST.get('semester', '1'))
            exam_type = request.POST.get('exam_type', 'mid1')
            title = request.POST.get('title', '').strip()
            start_date_str = request.POST.get('start_date', '').strip()
            end_date_str = request.POST.get('end_date', '').strip()
            target_units_val = request.POST.get('target_units', '2.5')
            target_comp_date_str = request.POST.get('target_completion_date', '').strip()

            start_date = parse_flexible_date(start_date_str) or today
            end_date = parse_flexible_date(end_date_str)
            target_completion_date = parse_flexible_date(target_comp_date_str) or start_date
            year_obj = None
            if year_val and year_val.isdigit():
                year_obj = Year.objects.filter(Q(year=int(year_val)) | Q(id=int(year_val))).first()
            if not year_obj:
                year_obj = Year.objects.first()

            target_units = float(target_units_val) if target_units_val else 2.5

            if not title:
                title = f"{dept.code} Y{year_obj.year} Sem-{semester} {dict(ExamSchedule.EXAM_TYPE_CHOICES).get(exam_type, 'Exam')}"

            if schedule_id and schedule_id.isdigit():
                sched = ExamSchedule.objects.filter(id=int(schedule_id)).filter(Q(branch=dept) | Q(branch__isnull=True)).first()
                if sched:
                    if sched.branch is None and request.user.role != 'admin':
                        sched.branch = dept
                    sched.year = year_obj
                    sched.semester = semester
                    sched.exam_type = exam_type
                    sched.title = title
                    sched.start_date = start_date
                    sched.end_date = end_date
                    sched.target_units = target_units
                    sched.target_completion_date = target_completion_date
                    sched.save()
                    messages.success(request, f"Exam Schedule '{title}' updated successfully.")
                else:
                    messages.error(request, "Exam schedule not found.")
            else:
                ExamSchedule.objects.create(
                    branch=dept,
                    year=year_obj,
                    semester=semester,
                    exam_type=exam_type,
                    title=title,
                    start_date=start_date,
                    end_date=end_date,
                    target_units=target_units,
                    target_completion_date=target_completion_date,
                    created_by=request.user
                )
                messages.success(request, f"Exam Schedule '{title}' created successfully.")
            return redirect('hod:manage_exam_schedules')

        elif action == 'delete_exam_schedule':
            schedule_id = request.POST.get('schedule_id')
            if schedule_id and schedule_id.isdigit():
                sched = ExamSchedule.objects.filter(id=int(schedule_id)).filter(Q(branch=dept) | Q(branch__isnull=True)).first()
                if sched:
                    if sched.branch is None:
                        messages.warning(request, "University-wide exam schedules created by College Administration can only be removed by Admin.")
                    else:
                        t = sched.title
                        sched.delete()
                        messages.success(request, f"Exam Schedule '{t}' deleted.")
                else:
                    messages.error(request, "Exam schedule not found.")
            return redirect('hod:manage_exam_schedules')

    schedules = ExamSchedule.objects.filter(
        Q(branch=dept) | Q(branch__isnull=True)
    ).select_related('branch', 'year').order_by('-start_date')

    years = Year.objects.all().order_by('year')

    context = {
        'dept': dept,
        'schedules': schedules,
        'years': years,
        'exam_types': ExamSchedule.EXAM_TYPE_CHOICES,
        'semester_choices': Subject.SEMESTER_CHOICES,
        'today': today,
    }
    return render(request, 'hod/manage_exam_schedules.html', context)


# ─────────────────────────────────────────────
# DETENTION & READMISSION MANAGEMENT
# ─────────────────────────────────────────────
@hod_required
def manage_detention_readmissions(request):
    """
    HOD review queue for detained students applying to repeat year with juniors.
    """
    from accounts.models import StudentReadmissionRequest

    dept = request.department

    requests_list = StudentReadmissionRequest.objects.filter(
        student__branch=dept
    ).select_related('student__user', 'target_junior_year', 'target_junior_section', 'previous_year').order_by('-created_at')

    # Also fetch currently detained students in department
    detained_students = Student.objects.filter(
        branch=dept,
        is_active=True
    ).filter(
        Q(academic_status__in=['DETAINED_ATTENDANCE', 'DETAINED_CREDITS']) | Q(is_detained=True)
    ).select_related('user', 'year', 'section')

    return render(request, 'hod/detention_readmissions.html', {
        'department': dept,
        'readmission_requests': requests_list,
        'detained_students': detained_students,
    })


@hod_required
@require_POST
def action_readmission_request(request, pk, action):
    """
    HOD recommends or rejects a student readmission request.
    """
    from accounts.models import StudentReadmissionRequest

    dept = request.department
    readmission_req = get_object_or_404(StudentReadmissionRequest, pk=pk, student__branch=dept)

    remarks = request.POST.get('remarks', '').strip()

    if action == 'recommend':
        readmission_req.hod_status = 'approved'
        readmission_req.hod_reviewed_by = request.faculty
        readmission_req.hod_reviewed_at = timezone.now()
        readmission_req.hod_remarks = remarks
        readmission_req.save()
        messages.success(request, f"Readmission request for {readmission_req.student.roll_number} recommended to College Administration for final approval.")
    elif action == 'reject':
        readmission_req.hod_status = 'rejected'
        readmission_req.hod_reviewed_by = request.faculty
        readmission_req.hod_reviewed_at = timezone.now()
        readmission_req.hod_remarks = remarks
        readmission_req.save()
        messages.warning(request, f"Readmission request for {readmission_req.student.roll_number} has been rejected by HOD.")
    else:
        messages.error(request, "Invalid action specified.")

    return redirect('hod:manage_detention_readmissions')


# ─────────────────────────────────────────────
# STUDENT OD & MEDICAL LEAVE APPROVAL
# ─────────────────────────────────────────────
@hod_required
def manage_student_leaves(request):
    """
    HOD view to review student OD and Medical leave applications.
    """
    from accounts.models import StudentLeaveRequest

    dept = request.department
    status_filter = request.GET.get('status', 'all')

    leaves_qs = StudentLeaveRequest.objects.filter(
        student__branch=dept
    ).select_related('student__user', 'reviewed_by__user').order_by('-created_at')

    if status_filter in ['pending', 'approved', 'rejected']:
        leaves_qs = leaves_qs.filter(status=status_filter)

    return render(request, 'hod/student_leaves.html', {
        'department': dept,
        'leaves': leaves_qs,
        'status_filter': status_filter,
    })


@hod_required
@require_POST
def action_student_leave(request, pk, action):
    """
    HOD approves or rejects student leave/OD request.
    Upon approval, marks attendance as 'L' for the date range.
    """
    from accounts.models import StudentLeaveRequest
    from core.models import Attendance

    dept = request.department
    leave_req = get_object_or_404(StudentLeaveRequest, pk=pk, student__branch=dept)

    remarks = request.POST.get('remarks', '').strip()

    if action == 'approve':
        leave_req.status = 'approved'
        leave_req.reviewed_by = request.faculty
        leave_req.reviewed_at = timezone.now()
        leave_req.review_remarks = remarks
        leave_req.save()

        # Update matching attendance records to 'L' (Leave)
        updated_count = Attendance.objects.filter(
            student=leave_req.student,
            date__range=(leave_req.start_date, leave_req.end_date)
        ).update(status='L')

        messages.success(request, f"Leave application for {leave_req.student.roll_number} approved. {updated_count} attendance records marked as Leave/OD.")
    elif action == 'reject':
        leave_req.status = 'rejected'
        leave_req.reviewed_by = request.faculty
        leave_req.reviewed_at = timezone.now()
        leave_req.review_remarks = remarks
        leave_req.save()
        messages.warning(request, f"Leave application for {leave_req.student.roll_number} rejected.")

    return redirect('hod:manage_student_leaves')


# ─────────────────────────────────────────────
# LOW ATTENDANCE ACTION CENTER
# ─────────────────────────────────────────────
@hod_required
def low_attendance_action_center(request):
    """
    HOD screening center for students with <75% and <65% attendance.
    Supports flag for Condonation and Attendance Detention.
    """
    dept = request.department

    year_filter = request.GET.get('year')
    sec_filter = request.GET.get('section')

    students_qs = Student.objects.filter(branch=dept, is_active=True).select_related('user', 'year', 'section')
    if year_filter:
        students_qs = students_qs.filter(year__year=year_filter)
    if sec_filter:
        students_qs = students_qs.filter(section_id=sec_filter)

    detention_list = []
    condonation_list = []
    regular_list = []

    for st in students_qs:
        pct = st.calculate_attendance_pct
        st_data = {
            'student': st,
            'pct': pct,
        }
        if pct < 65.0:
            detention_list.append(st_data)
        elif pct < 75.0:
            condonation_list.append(st_data)
        else:
            regular_list.append(st_data)


    # Action: Mark as Detained
    if request.method == 'POST' and request.POST.get('action') == 'mark_detention':
        student_id = request.POST.get('student_id')
        det_reason = request.POST.get('reason', 'Attendance shortage below 65%')
        st_obj = get_object_or_404(Student, id=student_id, branch=dept)
        st_obj.academic_status = 'DETAINED_ATTENDANCE'
        st_obj.is_detained = True
        st_obj.detention_reason = det_reason
        st_obj.save()
        messages.warning(request, f"Student {st_obj.roll_number} has been officially flagged as Detained (Attendance Shortage).")
        return redirect('hod:low_attendance_action_center')

    years = Year.objects.all().order_by('year')
    sections = Section.objects.filter(branch=dept).order_by('name')

    return render(request, 'hod/low_attendance_center.html', {
        'department': dept,
        'detention_list': detention_list,
        'condonation_list': condonation_list,
        'regular_list': regular_list,
        'years': years,
        'sections': sections,
        'selected_year': year_filter,
        'selected_section': sec_filter,
    })


# ─────────────────────────────────────────────
# FACULTY CLASS ATTENDANCE & CONDUCTION AUDIT
# ─────────────────────────────────────────────
def get_department_class_attendance_audit_data(dept, target_date, year_filter=None, sec_filter=None, fac_filter=None, status_filter=None):
    """
    Calculates period-by-period class conduction and student attendance marking
    status for every scheduled timetable slot in the department for a specific date.
    Accurately tracks peer class substitutions, HOD/Admin proxies, and direct faculty conduction.
    """
    day_name = target_date.strftime('%A').strip()
    slots_qs = list(Timetable.objects.filter(
        section__branch=dept,
        day__iexact=day_name
    ).select_related(
        'section', 'section__year', 'section__branch', 'subject', 'faculty__user'
    ).order_by('section__year__year', 'section__name', 'period'))

    slot_ids = {s.id for s in slots_qs}

    # Fetch Class Transfers / Proxies on target_date (accepted, completed, or pending)
    transfer_objs = list(ClassTransfer.objects.filter(
        date=target_date,
        status__in=['accepted', 'completed', 'pending']
    ).filter(
        Q(timetable_entry__section__branch=dept) |
        Q(original_faculty__department=dept) |
        Q(substitute_faculty__department=dept)
    ).select_related(
        'substitute_faculty__user', 'substitute_faculty__department',
        'original_faculty__user', 'original_faculty__department',
        'timetable_entry__section__branch', 'timetable_entry__section__year',
        'timetable_entry__section', 'timetable_entry__subject',
        'timetable_entry__faculty__user'
    ))

    transfers = {ct.timetable_entry_id: ct for ct in transfer_objs}
    extra_transferred_slots = [ct.timetable_entry for ct in transfer_objs if ct.timetable_entry and ct.timetable_entry_id not in slot_ids]
    all_slots_list = slots_qs + extra_transferred_slots

    # 1. Fetch attendance records on target_date for ALL relevant slots
    att_rows = list(Attendance.objects.filter(
        timetable_entry__in=all_slots_list,
        date=target_date
    ).values(
        'timetable_entry_id', 'status', 'marked_by_id',
        'last_modified'
    ))

    marked_by_fac_ids = {a['marked_by_id'] for a in att_rows if a['marked_by_id']}
    marked_by_fac_map = {
        f.id: f
        for f in Faculty.objects.filter(id__in=marked_by_ids if 'marked_by_ids' in locals() else marked_by_fac_ids).select_related('user', 'department')
    }

    att_by_slot = {}
    for att in att_rows:
        tid = att['timetable_entry_id']
        if tid not in att_by_slot:
            att_by_slot[tid] = []
        att_by_slot[tid].append(att)

    # 2. Fetch Class Diary logs on target_date for ALL relevant slots
    diaries = {
        cd.timetable_entry_id: cd
        for cd in ClassDiary.objects.filter(
            timetable_entry__in=all_slots_list,
            date=target_date
        )
    }

    # 3. Fetch Faculty Attendance (Biometric/Presence) on target_date
    fac_att_map = {
        fa.faculty_id: fa.status
        for fa in FacultyAttendance.objects.filter(date=target_date)
    }

    rows = []
    tot_scheduled = 0
    tot_marked = 0
    tot_unmarked = 0
    tot_transferred = 0
    tot_proxies = 0
    tot_substitutions = 0

    for slot in all_slots_list:
        att_records = att_by_slot.get(slot.id, [])
        is_marked = len(att_records) > 0
        first_rec = att_records[0] if att_records else None
        marked_by_fac = marked_by_fac_map.get(first_rec['marked_by_id']) if (first_rec and first_rec['marked_by_id']) else None

        transfer_obj = transfers.get(slot.id)
        orig_fac = transfer_obj.original_faculty if transfer_obj else slot.faculty
        effective_faculty = (transfer_obj.substitute_faculty if transfer_obj else marked_by_fac) or orig_fac

        is_transferred = (transfer_obj is not None) or (marked_by_fac and orig_fac and marked_by_fac.id != orig_fac.id)
        is_proxy = (transfer_obj.is_proxy if transfer_obj else False) or (marked_by_fac and orig_fac and marked_by_fac.id != orig_fac.id and not transfer_obj)
        is_substitution = (transfer_obj.is_substitution if transfer_obj else False) and not is_proxy

        if is_proxy:
            transfer_type_label = "Proxy"
            transfer_badge_class = "badge bg-warning text-dark"
        elif is_substitution:
            transfer_type_label = "Substituted Session"
            transfer_badge_class = "badge bg-info text-dark"
        else:
            transfer_type_label = ""
            transfer_badge_class = ""

        # Faculty filter handling
        if fac_filter and str(fac_filter).isdigit():
            target_fac_id = int(fac_filter)
            fac_match_ids = {
                getattr(orig_fac, 'id', None),
                getattr(effective_faculty, 'id', None),
                getattr(slot.faculty, 'id', None),
                getattr(marked_by_fac, 'id', None)
            }
            if target_fac_id not in fac_match_ids:
                continue

        # Year filter handling
        if year_filter and str(year_filter).isdigit():
            sec_year = getattr(slot.section, 'year', None)
            if not sec_year or sec_year.year != int(year_filter):
                continue

        # Section filter handling
        if sec_filter and str(sec_filter).isdigit():
            if slot.section_id != int(sec_filter):
                continue

        tot_scheduled += 1

        p_count = sum(1 for a in att_records if a['status'] == 'P')
        a_count = sum(1 for a in att_records if a['status'] == 'A')
        l_count = sum(1 for a in att_records if a['status'] == 'L')
        total_students = len(att_records)
        att_pct = round((p_count / total_students * 100), 1) if total_students > 0 else None

        diary_obj = diaries.get(slot.id)
        has_diary = diary_obj is not None

        # Faculty day attendance status
        fac_day_status = fac_att_map.get(slot.faculty_id, 'P') if slot.faculty else 'P'

        if is_marked:
            tot_marked += 1
            class_status = 'conducted_marked'
            status_label = 'Attendance Marked'
            status_badge = 'status-present'
        else:
            tot_unmarked += 1
            class_status = 'unmarked'
            status_label = 'Not Marked / Pending'
            status_badge = 'status-absent'

        if is_transferred:
            tot_transferred += 1
            if is_proxy:
                tot_proxies += 1
            else:
                tot_substitutions += 1

        marked_by_name = None
        marked_at_time = None
        if is_marked and first_rec:
            if marked_by_fac:
                marked_by_name = marked_by_fac.user.get_full_name()
            marked_at_time = first_rec['last_modified']

        row = {
            'slot': slot,
            'period': slot.period,
            'room': slot.room_number or 'Room 101',
            'section': slot.section,
            'year': getattr(slot.section, 'year', None),
            'subject': slot.subject,
            'assigned_faculty': slot.faculty,
            'effective_faculty': effective_faculty,
            'is_transferred': is_transferred,
            'is_proxy': is_proxy,
            'is_substitution': is_substitution,
            'transfer_type_label': transfer_type_label,
            'transfer_badge_class': transfer_badge_class,
            'transfer_obj': transfer_obj,
            'is_marked': is_marked,
            'marked_by_name': marked_by_name,
            'marked_at_time': marked_at_time,
            'present_count': p_count,
            'absent_count': a_count,
            'leave_count': l_count,
            'total_students': total_students,
            'attendance_pct': att_pct,
            'has_diary': has_diary,
            'diary_obj': diary_obj,
            'fac_day_status': fac_day_status,
            'class_status': class_status,
            'status_label': status_label,
            'status_badge': status_badge,
        }

        if status_filter == 'marked' and not is_marked:
            continue
        if status_filter == 'unmarked' and is_marked:
            continue
        if status_filter == 'transferred' and not is_transferred:
            continue
        if status_filter == 'proxy' and not is_proxy:
            continue
        if status_filter == 'substitution' and not is_substitution:
            continue

        rows.append(row)

    return {
        'rows': rows,
        'tot_scheduled': tot_scheduled,
        'tot_marked': tot_marked,
        'tot_unmarked': tot_unmarked,
        'tot_transferred': tot_transferred,
        'tot_proxies': tot_proxies,
        'tot_substitutions': tot_substitutions,
        'overall_compliance_pct': round((tot_marked / tot_scheduled * 100), 1) if tot_scheduled > 0 else 0.0,
        'day_name': day_name,
        'target_date': target_date,
    }



@hod_required
def faculty_class_attendance_audit(request):
    """
    Dedicated HOD monitoring screen to audit which faculty went to class
    and marked student attendance for any given date.
    """
    dept = request.department

    date_str = request.GET.get('date')
    if date_str:
        try:
            target_date = dt.datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            target_date = timezone.localdate()
    else:
        target_date = timezone.localdate()

    year_filter = request.GET.get('year')
    sec_filter = request.GET.get('section')
    fac_filter = request.GET.get('faculty')
    status_filter = request.GET.get('status', 'all')

    # Action: Send attendance reminder to faculty
    if request.method == 'POST' and request.POST.get('action') == 'send_reminder':
        slot_id = request.POST.get('slot_id')
        slot_obj = get_object_or_404(Timetable, id=slot_id, section__branch=dept)
        if slot_obj.faculty and slot_obj.faculty.user:
            Notification.objects.create(
                title=f"URGENT: Mark Attendance for Period {slot_obj.period}",
                message=f"HOD has requested you to mark student attendance for {slot_obj.subject.code} ({slot_obj.section}) on {target_date.strftime('%d-%b-%Y')}.",
                notif_type=Notification.TYPE_ALERT,
                priority=Notification.PRIORITY_HIGH,
                target_user=slot_obj.faculty.user,
                created_by=request.user
            )
            messages.success(request, f"Attendance reminder notification dispatched to {slot_obj.faculty.user.get_full_name()}.")
        return redirect(f"{request.path}?date={target_date.isoformat()}&year={year_filter or ''}&section={sec_filter or ''}&faculty={fac_filter or ''}&status={status_filter or 'all'}")

    audit_data = get_department_class_attendance_audit_data(
        dept, target_date, year_filter=year_filter, sec_filter=sec_filter, fac_filter=fac_filter, status_filter=status_filter
    )

    years = Year.objects.all().order_by('year')
    sections = Section.objects.filter(branch=dept).order_by('name')
    faculty_list = Faculty.objects.filter(department=dept, is_active=True).select_related('user').order_by('user__first_name')

    context = {
        'department': dept,
        'audit_data': audit_data,
        'selected_date': target_date.isoformat(),
        'target_date': target_date,
        'years': years,
        'sections': sections,
        'faculty_list': faculty_list,
        'selected_year': year_filter,
        'selected_section': sec_filter,
        'selected_faculty': fac_filter,
        'selected_status': status_filter,
    }
    return render(request, 'hod/faculty_class_audit.html', context)


@hod_required
def class_session_audit_detail(request, timetable_id, date):
    """
    Detailed inspector for a specific class period:
    Shows faculty actions (conduction, proxy status, topic taught) and
    the complete student attendance roster for that period.
    """
    dept = request.department
    slot = get_object_or_404(
        Timetable.objects.select_related(
            'section', 'section__year', 'section__branch', 'subject', 'faculty__user'
        ),
        id=timetable_id,
        section__branch=dept
    )

    try:
        target_date = dt.datetime.strptime(date, '%Y-%m-%d').date()
    except ValueError:
        target_date = timezone.localdate()

    # Check for Class Transfer (Proxy / Substituted Session)
    transfer = ClassTransfer.objects.filter(
        timetable_entry=slot,
        date=target_date,
        status__in=['accepted', 'completed', 'pending']
    ).select_related('substitute_faculty__user', 'original_faculty__user').first()


    effective_faculty = transfer.substitute_faculty if transfer else slot.faculty

    # Handle HOD manual override for a specific student
    if request.method == 'POST' and request.POST.get('action') == 'override_status':
        student_id = request.POST.get('student_id')
        new_status = request.POST.get('status')
        if new_status in ['P', 'A', 'L']:
            student_obj = get_object_or_404(Student, id=student_id, section=slot.section)
            att_rec, created = Attendance.objects.get_or_create(
                student=student_obj,
                timetable_entry=slot,
                date=target_date,
                defaults={'status': new_status, 'marked_by': request.faculty}
            )
            if not created:
                att_rec.status = new_status
                att_rec.save()
            messages.success(request, f"Attendance status for {student_obj.roll_number} updated to {att_rec.get_status_display()}.")
            return redirect('hod:class_attendance_detail', timetable_id=slot.id, date=target_date.isoformat())

    # Fetch all students in this section
    section_students = Student.objects.filter(
        section=slot.section,
        is_active=True
    ).select_related('user').order_by('roll_number')

    # Fetch attendance records for this slot & date
    att_records = Attendance.objects.filter(
        timetable_entry=slot,
        date=target_date
    ).select_related('student__user', 'marked_by__user')

    att_map = {att.student_id: att for att in att_records}

    # Class Diary Topic Log
    diary = ClassDiary.objects.filter(
        timetable_entry=slot,
        date=target_date
    ).select_related('faculty__user').first()

    # Build complete student roster with attendance status
    student_roster = []
    p_count = 0
    a_count = 0
    l_count = 0

    for st in section_students:
        att = att_map.get(st.id)
        status = att.status if att else 'UNMARKED'
        if status == 'P':
            p_count += 1
        elif status == 'A':
            a_count += 1
        elif status == 'L':
            l_count += 1

        student_roster.append({
            'student': st,
            'status': status,
            'record': att,
            'last_modified': att.last_modified if att else None,
            'marked_by': att.marked_by if att else None,
        })

    total_students = len(section_students)
    is_marked = len(att_records) > 0
    att_pct = round((p_count / total_students * 100), 1) if total_students > 0 else 0.0
    first_rec = att_records.first()
    marked_by = first_rec.marked_by if first_rec else None
    marked_at = first_rec.last_modified if first_rec else None

    context = {
        'department': dept,
        'slot': slot,
        'target_date': target_date,
        'transfer': transfer,
        'effective_faculty': effective_faculty,
        'diary': diary,
        'student_roster': student_roster,
        'is_marked': is_marked,
        'marked_by': marked_by,
        'marked_at': marked_at,
        'p_count': p_count,
        'a_count': a_count,
        'l_count': l_count,
        'total_students': total_students,
        'att_pct': att_pct,
    }
    return render(request, 'hod/class_attendance_detail.html', context)


# ─────────────────────────────────────────────
# STUDENT FEEDBACK FORMS & DOCUMENT MANAGEMENT (HOD)
# ─────────────────────────────────────────────
@hod_required
def manage_feedback_forms(request):
    """HOD feedback management console listing department feedback forms."""
    from core.models import FeedbackForm
    dept = request.department
    type_filter = request.GET.get('type', '')
    status_filter = request.GET.get('status', '')

    forms_qs = FeedbackForm.objects.filter(
        Q(branch=dept) | Q(branch__isnull=True)
    ).select_related('branch', 'year', 'section', 'created_by').order_by('-created_at')

    if type_filter:
        forms_qs = forms_qs.filter(feedback_type=type_filter)
    if status_filter == 'active':
        forms_qs = forms_qs.filter(is_active=True)
    elif status_filter == 'closed':
        forms_qs = forms_qs.filter(is_active=False)

    return render(request, 'feedback/manage_forms.html', {
        'forms': forms_qs,
        'department': dept,
        'selected_type': type_filter,
        'selected_status': status_filter,
        'is_hod': True,
    })


@hod_required
def extract_feedback_document_api(request):
    """AJAX API endpoint for HOD to extract form questions, title, and metadata from uploaded photo or PDF."""
    from django.http import JsonResponse
    from core.document_extractor import extract_feedback_form_data, parse_questionnaire_structure
    from core.models import FeedbackForm

    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST request required.'}, status=405)

    try:
        raw_text = request.POST.get('raw_text', '').strip()
        if raw_text:
            data = parse_questionnaire_structure(raw_text)
            return JsonResponse(data)

        if 'file' in request.FILES:
            uploaded_file = request.FILES['file']
            data = extract_feedback_form_data(uploaded_file, uploaded_file.name)
            return JsonResponse(data)

        form_id = request.POST.get('form_id')
        if form_id:
            dept = request.department
            form_obj = get_object_or_404(FeedbackForm, id=form_id)
            if form_obj.branch and form_obj.branch != dept:
                return JsonResponse({'success': False, 'error': 'Access denied to this department feedback form.'}, status=403)
            if not form_obj.uploaded_document:
                return JsonResponse({'success': False, 'error': 'No document is attached to this form.'}, status=400)
            data = extract_feedback_form_data(form_obj.uploaded_document.file, form_obj.uploaded_document.name)
            return JsonResponse(data)

        return JsonResponse({'success': False, 'error': 'No file, form_id, or text provided for extraction.'}, status=400)
    except Exception as e:
        logger.exception("Error extracting feedback document (HOD)")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@hod_required
def create_feedback_form(request):
    """HOD create/upload feedback form view for department."""
    from core.models import FeedbackForm, FeedbackQuestion, Year, Section
    from core.feedback_service import populate_preset_questions
    from core.document_extractor import extract_feedback_form_data

    dept = request.department
    years = Year.objects.all().order_by('year')
    sections = Section.objects.filter(branch=dept).order_by('year', 'name')

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        feedback_type = request.POST.get('feedback_type', 'faculty')
        year_id = request.POST.get('year') or None
        semester = request.POST.get('semester') or None
        section_id = request.POST.get('section') or None
        deadline_str = request.POST.get('deadline', '').strip()
        allow_online = request.POST.get('allow_online_submission') == 'on'
        allow_offline = request.POST.get('allow_offline_download') == 'on'
        preset_template = request.POST.get('preset_template', '').strip()
        auto_extract = request.POST.get('auto_extract_questions') == 'on'

        uploaded_doc = request.FILES.get('uploaded_document')

        deadline = None
        if deadline_str:
            import datetime
            try:
                deadline = datetime.datetime.strptime(deadline_str, '%Y-%m-%d').date()
            except ValueError:
                pass

        if not title:
            messages.error(request, "Please enter a feedback form title.")
        else:
            if uploaded_doc:
                from core.file_validators import validate_document_upload
                from django.core.exceptions import ValidationError
                try:
                    validate_document_upload(uploaded_doc, allowed_extensions={'.pdf', '.jpg', '.jpeg', '.png', '.webp'}, max_size_mb=10)
                except ValidationError as ve:
                    messages.error(request, f"Attached document rejected: {ve.message if hasattr(ve, 'message') else ve}")
                    return redirect('hod:manage_feedback_forms')

            form_obj = FeedbackForm.objects.create(
                title=title,
                description=description,
                feedback_type=feedback_type,
                branch=dept,
                year_id=year_id,
                semester=semester if semester else None,
                section_id=section_id,
                uploaded_document=uploaded_doc,
                deadline=deadline,
                allow_online_submission=allow_online,
                allow_offline_download=allow_offline,
                created_by=request.user
            )

            # 1. Custom / Extracted questions parsing from UI
            q_texts = request.POST.getlist('custom_question_text[]')
            q_types = request.POST.getlist('custom_question_type[]')
            q_options = request.POST.getlist('custom_question_options[]')
            q_required = request.POST.getlist('custom_question_required[]')

            created_questions = False
            order = 1
            for idx, q_t in enumerate(q_texts):
                if q_t.strip():
                    q_tp = q_types[idx] if idx < len(q_types) else 'rating_5'
                    q_opt = q_options[idx] if idx < len(q_options) else ''
                    is_req = True
                    if idx < len(q_required):
                        is_req = q_required[idx] == '1' or q_required[idx] == 'on' or q_required[idx] == 'true'

                    FeedbackQuestion.objects.create(
                        form=form_obj,
                        question_text=q_t.strip(),
                        question_type=q_tp if q_tp else 'rating_5',
                        options=q_opt.strip() if q_opt else None,
                        is_required=is_req,
                        order=order
                    )
                    order += 1
                    created_questions = True

            # 2. Populate preset if selected and no questions manually entered
            if preset_template and not created_questions:
                populate_preset_questions(form_obj, preset_template)
                created_questions = True

            # 3. Auto-extract if requested and no questions built
            if not created_questions and uploaded_doc and auto_extract:
                try:
                    uploaded_doc.seek(0)
                    extracted = extract_feedback_form_data(uploaded_doc, uploaded_doc.name)
                    if extracted.get('success') and extracted.get('questions'):
                        for eq in extracted['questions']:
                            FeedbackQuestion.objects.create(
                                form=form_obj,
                                question_text=eq['question_text'],
                                question_type=eq['question_type'],
                                options=eq.get('options') or None,
                                is_required=eq.get('is_required', True),
                                order=order
                            )
                            order += 1
                except Exception as ex:
                    logger.warning(f"Auto-extraction during save failed: {ex}")

            messages.success(request, f"Feedback form '{form_obj.title}' created successfully for {dept.code}!")
            return redirect('hod:manage_feedback_forms')

    return render(request, 'feedback/form_editor.html', {
        'department': dept,
        'years': years,
        'sections': sections,
        'is_hod': True,
    })


@hod_required
def edit_feedback_form(request, form_id):
    """HOD edit department feedback form."""
    from core.models import FeedbackForm, FeedbackQuestion, Year, Section
    dept = request.department
    form_obj = get_object_or_404(FeedbackForm, id=form_id)

    if form_obj.branch and form_obj.branch != dept:
        messages.error(request, "Access denied. You can only edit feedback forms for your department.")
        return redirect('hod:manage_feedback_forms')

    years = Year.objects.all().order_by('year')
    sections = Section.objects.filter(branch=dept).order_by('year', 'name')
    questions = form_obj.questions.all().order_by('order', 'id')

    if request.method == 'POST':
        form_obj.title = request.POST.get('title', '').strip() or form_obj.title
        form_obj.description = request.POST.get('description', '').strip()
        form_obj.feedback_type = request.POST.get('feedback_type', form_obj.feedback_type)
        form_obj.year_id = request.POST.get('year') or None
        sem = request.POST.get('semester')
        form_obj.semester = int(sem) if sem else None
        form_obj.section_id = request.POST.get('section') or None
        form_obj.allow_online_submission = request.POST.get('allow_online_submission') == 'on'
        form_obj.allow_offline_download = request.POST.get('allow_offline_download') == 'on'
        form_obj.is_active = request.POST.get('is_active') == 'on'

        deadline_str = request.POST.get('deadline', '').strip()
        if deadline_str:
            import datetime
            try:
                form_obj.deadline = datetime.datetime.strptime(deadline_str, '%Y-%m-%d').date()
            except ValueError:
                pass
        else:
            form_obj.deadline = None

        if 'uploaded_document' in request.FILES:
            from core.file_validators import validate_document_upload
            from django.core.exceptions import ValidationError
            uploaded_doc = request.FILES['uploaded_document']
            try:
                validate_document_upload(uploaded_doc, allowed_extensions={'.pdf', '.jpg', '.jpeg', '.png', '.webp'}, max_size_mb=10)
                form_obj.uploaded_document = uploaded_doc
            except ValidationError as ve:
                messages.error(request, f"Attached document rejected: {ve.message if hasattr(ve, 'message') else ve}")

        form_obj.save()

        # Update questions if submitted
        q_texts = request.POST.getlist('custom_question_text[]')
        q_types = request.POST.getlist('custom_question_type[]')
        q_options = request.POST.getlist('custom_question_options[]')
        q_required = request.POST.getlist('custom_question_required[]')

        if q_texts:
            form_obj.questions.all().delete()
            order = 1
            for idx, q_t in enumerate(q_texts):
                if q_t.strip():
                    q_tp = q_types[idx] if idx < len(q_types) else 'rating_5'
                    q_opt = q_options[idx] if idx < len(q_options) else ''
                    is_req = True
                    if idx < len(q_required):
                        is_req = q_required[idx] == '1' or q_required[idx] == 'on' or q_required[idx] == 'true'

                    FeedbackQuestion.objects.create(
                        form=form_obj,
                        question_text=q_t.strip(),
                        question_type=q_tp if q_tp else 'rating_5',
                        options=q_opt.strip() if q_opt else None,
                        is_required=is_req,
                        order=order
                    )
                    order += 1

        messages.success(request, f"Feedback form '{form_obj.title}' updated successfully.")
        return redirect('hod:manage_feedback_forms')

    return render(request, 'feedback/form_editor.html', {
        'form_obj': form_obj,
        'questions': questions,
        'department': dept,
        'years': years,
        'sections': sections,
        'is_hod': True,
        'is_edit': True,
    })


@hod_required
def feedback_analytics(request, form_id):
    """HOD feedback analytics view."""
    from core.models import FeedbackForm
    from core.feedback_service import get_form_analytics

    dept = request.department
    form_obj = get_object_or_404(FeedbackForm, id=form_id)

    if form_obj.branch and form_obj.branch != dept:
        messages.error(request, "Access denied to external department feedback forms.")
        return redirect('hod:manage_feedback_forms')

    analytics_data = get_form_analytics(form_obj)
    analytics_data['is_hod'] = True
    analytics_data['department'] = dept

    return render(request, 'feedback/analytics.html', analytics_data)


@hod_required
def export_feedback_analytics_pdf(request, form_id):
    """HOD export consolidated analytics PDF."""
    from core.models import FeedbackForm
    from core.pdf_utils import generate_feedback_analytics_pdf

    dept = request.department
    form_obj = get_object_or_404(FeedbackForm, id=form_id)
    if form_obj.branch and form_obj.branch != dept:
        messages.error(request, "Access denied.")
        return redirect('hod:manage_feedback_forms')

    try:
        pdf_buffer = generate_feedback_analytics_pdf(form_obj)
        filename = f"VVIT_Feedback_Analytics_{dept.code}_{form_obj.id}.pdf"
        response = HttpResponse(pdf_buffer.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    except Exception as e:
        messages.error(request, f"Failed to generate analytics PDF: {e}")
        return redirect('hod:feedback_analytics', form_id=form_id)


@hod_required
def download_blank_feedback_pdf(request, form_id):
    """HOD download blank printable PDF."""
    from core.models import FeedbackForm
    from core.pdf_utils import generate_feedback_blank_printable_pdf

    form_obj = get_object_or_404(FeedbackForm, id=form_id)
    try:
        pdf_buffer = generate_feedback_blank_printable_pdf(form_obj)
        filename = f"VVIT_Blank_Feedback_Form_{form_obj.id}.pdf"
        response = HttpResponse(pdf_buffer.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    except Exception as e:
        messages.error(request, f"Failed to generate blank form: {e}")
        return redirect('hod:manage_feedback_forms')


@hod_required
def view_student_feedback_summary(request, form_id, submission_id):
    """HOD view specific student response."""
    from core.models import FeedbackForm, FeedbackSubmission
    dept = request.department
    form_obj = get_object_or_404(FeedbackForm, id=form_id)
    submission = get_object_or_404(FeedbackSubmission, id=submission_id, form=form_obj)

    answers = submission.answers.select_related('question').order_by('question__order', 'id')

    return render(request, 'feedback/student_summary.html', {
        'form_obj': form_obj,
        'submission': submission,
        'answers': answers,
        'student': submission.student,
        'is_hod': True,
        'department': dept,
    })


@hod_required
def download_student_feedback_pdf(request, form_id, submission_id):
    """HOD download student's signed summary PDF."""
    from core.models import FeedbackForm, FeedbackSubmission
    from core.pdf_utils import generate_student_feedback_summary_pdf

    form_obj = get_object_or_404(FeedbackForm, id=form_id)
    submission = get_object_or_404(FeedbackSubmission, id=submission_id, form=form_obj)

    try:
        pdf_buffer = generate_student_feedback_summary_pdf(submission)
        filename = f"VVIT_Feedback_{submission.student.roll_number}_{form_obj.id}.pdf"
        response = HttpResponse(pdf_buffer.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    except Exception as e:
        messages.error(request, f"Failed to generate student PDF: {e}")
        return redirect('hod:feedback_analytics', form_id=form_id)


@hod_required
def toggle_feedback_status(request, form_id):
    """HOD toggle active/closed status."""
    from core.models import FeedbackForm
    dept = request.department
    form_obj = get_object_or_404(FeedbackForm, id=form_id)
    if form_obj.branch and form_obj.branch != dept:
        messages.error(request, "Access denied.")
        return redirect('hod:manage_feedback_forms')

    form_obj.is_active = not form_obj.is_active
    form_obj.save()
    status_str = "Activated" if form_obj.is_active else "Closed"
    messages.success(request, f"Feedback form '{form_obj.title}' is now {status_str}.")
    return redirect('hod:manage_feedback_forms')


@hod_required
def delete_feedback_form(request, form_id):
    """HOD delete feedback form."""
    from core.models import FeedbackForm
    dept = request.department
    form_obj = get_object_or_404(FeedbackForm, id=form_id)
    if form_obj.branch and form_obj.branch != dept:
        messages.error(request, "Access denied.")
        return redirect('hod:manage_feedback_forms')

    title = form_obj.title
    form_obj.delete()
    messages.success(request, f"Feedback form '{title}' deleted successfully.")
    return redirect('hod:manage_feedback_forms')


@hod_required
def academic_calendar(request):
    """HOD view of the university academic calendar."""
    today = timezone.localdate()
    dept = request.department

    events = list(
        AcademicCalendar.objects
        .filter(date__gte=today - datetime.timedelta(days=30))
        .filter(Q(branch=dept) | Q(branch__isnull=True) if dept else Q())
        .order_by('date')
    )
    return render(request, 'student/academic_calendar.html', {
        'upcoming': [e for e in events if e.date >= today],
        'past':     [e for e in events if e.date <  today],
        'today':    today,
    })









