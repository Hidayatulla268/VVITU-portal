"""
VVIT Portal — Admin Dashboard Views

Full administrative control:
  • Statistics overview
  • Manage students and faculty (add / edit / delete)
  • Assign class teacher and counsellor to a section
  • Manage timetable entries
  • Override attendance records (no date restriction)
  • Manage subjects, exams, results, calendar, question papers
"""

import datetime
import json
import logging
from functools import wraps

logger = logging.getLogger(__name__)

from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Count, Q
from django.core.paginator import Paginator
from django.core.mail import send_mail
from django.conf import settings
from django.conf import settings as django_settings
from django.views.decorators.http import require_POST

from accounts.models import User, Student, Faculty, DEOProfile, FacultyLeaveRequest, generate_secure_temp_password
from core.models import (
    Branch, Year, Section, Subject, Timetable,
    Attendance, Exam, Result, AcademicCalendar, QuestionPaper, ResultRelease,
    FacultyAttendance, ClassTransfer, ClassDiary, Notification,
    SubjectTopicPlan, ExamSchedule, ensure_sections_for_all_branches
)
from core.sms_utils import send_result_notifications, send_result_sms_to_parent
from core.syllabus_utils import get_subject_syllabus_progress, check_and_dispatch_syllabus_reminders


# ─────────────────────────────────────────────
# HELPER DECORATOR
# ─────────────────────────────────────────────
def admin_required(view_func):
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if request.user.role != 'admin':
            messages.error(request, "Administrators only.")
            return redirect(request.user.get_dashboard_url())
        return view_func(request, *args, **kwargs)
    return wrapper


# ─────────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────────
@admin_required
def dashboard(request):
    """High-level statistics card view for the admin home page with institutional class audit."""
    stats = {
        'total_students': Student.objects.filter(is_active=True, user__is_deleted=False).count(),
        'total_faculty':  Faculty.objects.filter(is_active=True, user__is_deleted=False).count(),
        'total_subjects': Subject.objects.filter(is_deleted=False).count(),
        'total_sections': Section.objects.count(),
        'total_branches': Branch.objects.count(),
    }

    today          = timezone.localdate()
    att_today      = Attendance.objects.filter(date=today)
    stats['present_today'] = att_today.filter(status='P').count()
    stats['absent_today']  = att_today.filter(status='A').count()

    # Branch-wise student counts for chart
    branch_data = list(
        Student.objects
        .values('branch__code')
        .annotate(count=Count('id'))
        .order_by('branch__code')
    )

    # Institutional Class Conduction & Attendance Audit (Today)
    class_audit_data = get_institutional_class_attendance_audit_data(target_date=today)
    branches = Branch.objects.all().order_by('code')

    context = {
        'stats':            stats,
        'branch_data':      json.dumps(branch_data),
        'today':            today,
        'day_name':         today.strftime('%A'),
        'class_audit_data': class_audit_data,
        'branches':         branches,
    }
    return render(request, 'admin_dashboard/dashboard.html', context)



# ═══════════════════════════════════════════════
# STUDENT MANAGEMENT
# ═══════════════════════════════════════════════
@admin_required
def manage_students(request):
    from core.models import Branch, Year
    branches = Branch.objects.all()
    years    = Year.objects.all()

    branch_id = request.GET.get('branch', '')
    year_id   = request.GET.get('year', '')
    search    = request.GET.get('q', '').strip()

    qs = (
        Student.objects
        .filter(user__is_deleted=False)
        .select_related('user', 'branch', 'year', 'section')
        .order_by('roll_number')
    )

    if branch_id:
        qs = qs.filter(branch_id=branch_id)
    if year_id:
        qs = qs.filter(year_id=year_id)

    if search:
        from django.db.models import Q
        qs = qs.filter(
            Q(roll_number__icontains=search) | 
            Q(user__first_name__icontains=search) | 
            Q(user__last_name__icontains=search) |
            Q(user__username__icontains=search) |
            Q(branch__code__icontains=search) |
            Q(branch__name__icontains=search) |
            Q(section__name__icontains=search) |
            Q(year__year__icontains=search)
        )

    paginator = Paginator(qs, 25)
    page      = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'admin_dashboard/manage_students.html', {
        'page': page,
        'search': search,
        'branches': branches,
        'years': years,
        'branch_id': branch_id,
        'year_id': year_id,
    })


@admin_required
def add_student(request):
    branches = Branch.objects.all()
    years    = Year.objects.all()
    sections = Section.objects.select_related('branch', 'year').all()
    faculties= Faculty.objects.select_related('user').filter(is_active=True)

    if request.method == 'POST':
        p = request.POST
        # Create User
        username = p.get('username', '').strip()
        if User.objects.filter(username=username).exists():
            messages.error(request, f"Username '{username}' already exists.")
            return redirect('admin_dashboard:add_student')

        first_name = p.get('first_name', '').strip()
        last_name  = p.get('last_name',  '').strip()

        if len(first_name) < 3:
            messages.error(request, "First name must be at least 3 characters long.")
            return redirect('admin_dashboard:add_student')
        if len(last_name) < 1:
            messages.error(request, "Last name must be at least 1 character long.")
            return redirect('admin_dashboard:add_student')

        email = p.get('email', '').strip()
        if not email:
            email = f"{username}@vvitu.net"

        temp_pwd = p.get('password', '').strip() or generate_secure_temp_password()
        user = User.objects.create_user(
            username   = username,
            password   = temp_pwd,
            first_name = first_name,
            last_name  = last_name,
            email      = email,
            role       = 'student',
            phone      = p.get('phone', ''),
        )
        fees_val = p.get('fees_pending')
        fees_pending_amount = 0.00
        if fees_val is not None and fees_val != '':
            try:
                fees_pending_amount = float(fees_val)
            except ValueError:
                pass

        Student.objects.create(
            user          = user,
            roll_number   = username,
            branch_id     = p.get('branch'),
            year_id       = p.get('year'),
            section_id    = p.get('section'),
            class_teacher_id = p.get('class_teacher') or None,
            counsellor_id    = p.get('counsellor')    or None,
            admission_year   = p.get('admission_year', 2024),
            parent_name   = p.get('parent_name', '').strip() or None,
            parent_occupation = p.get('parent_occupation', '').strip() or None,
            parent_mobile = p.get('parent_mobile', '').strip() or None,
            personal_mobile = p.get('personal_mobile', '').strip() or None,
            gender        = p.get('gender', '').strip() or None,
            caste         = p.get('caste', '').strip() or None,
            religion      = p.get('religion', '').strip() or None,
            permanent_address = p.get('permanent_address', '').strip() or None,
            present_address   = p.get('present_address', '').strip() or None,
            fees_pending  = fees_pending_amount,
            fees_updated_at = timezone.now() if fees_pending_amount > 0 else None,
        )
        messages.success(request, f"Student {username} created successfully! (Initial Password: {temp_pwd})")
        return redirect('admin_dashboard:manage_students')

    context = {'branches': branches, 'years': years, 'sections': sections, 'faculties': faculties}
    return render(request, 'admin_dashboard/add_student.html', context)


@admin_required
def edit_student(request, pk):
    student  = get_object_or_404(Student, pk=pk)
    branches = Branch.objects.all()
    years    = Year.objects.all()
    sections = Section.objects.select_related('branch', 'year').all()
    faculties= Faculty.objects.select_related('user').filter(is_active=True)

    if request.method == 'POST':
        p = request.POST
        first_name = p.get('first_name', '').strip()
        last_name  = p.get('last_name',  '').strip()

        if len(first_name) < 3:
            messages.error(request, "First name must be at least 3 characters long.")
            return redirect('admin_dashboard:edit_student', pk=pk)
        if len(last_name) < 1:
            messages.error(request, "Last name must be at least 1 character long.")
            return redirect('admin_dashboard:edit_student', pk=pk)

        u = student.user
        u.first_name = first_name
        u.last_name  = last_name
        u.phone      = p.get('phone',      u.phone)
        email = p.get('email', '').strip()
        u.email = email or f"{student.roll_number}@vvitu.net"

        password = p.get('password', '').strip()
        if password:
            if len(password) < 6:
                messages.error(request, "Password must be at least 6 characters long.")
                return redirect('admin_dashboard:edit_student', pk=pk)
            u.set_password(password)
            student.is_first_login = False

        u.save()

        student.branch_id    = p.get('branch',        student.branch_id)
        student.year_id      = p.get('year',          student.year_id)
        student.section_id   = p.get('section',       student.section_id)
        student.class_teacher_id = p.get('class_teacher') or None
        student.counsellor_id    = p.get('counsellor')    or None
        student.parent_name  = p.get('parent_name', '').strip() or None
        student.parent_occupation = p.get('parent_occupation', '').strip() or None
        student.parent_mobile = p.get('parent_mobile', '').strip() or None
        student.personal_mobile = p.get('personal_mobile', '').strip() or None
        student.gender       = p.get('gender', '').strip() or None
        student.caste        = p.get('caste', '').strip() or None
        student.religion     = p.get('religion', '').strip() or None
        student.permanent_address = p.get('permanent_address', '').strip() or None
        student.present_address   = p.get('present_address', '').strip() or None

        fees_val = p.get('fees_pending')
        if fees_val is not None and fees_val != '':
            try:
                student.fees_pending = float(fees_val)
                student.fees_updated_at = timezone.now()
            except ValueError:
                pass

        student.save()
        messages.success(request, "Student details, fee status, and demographics updated successfully.")
        return redirect('admin_dashboard:manage_students')

    context = {
        'student':   student,
        'branches':  branches,
        'years':     years,
        'sections':  sections,
        'faculties': faculties,
    }
    return render(request, 'admin_dashboard/edit_student.html', context)


@admin_required
def delete_student(request, pk):
    student = get_object_or_404(Student, pk=pk)
    if request.method == 'POST':
        user = student.user
        user.is_active = False
        user.is_deleted = True
        user.deleted_by_name = f"{request.user.get_full_name() or request.user.username} ({request.user.role.upper()})"
        from django.utils import timezone
        user.deleted_at = timezone.now()
        user.save()
        messages.success(request, "Student soft-deleted successfully.")
    return redirect('admin_dashboard:manage_students')



# ═══════════════════════════════════════════════
# FACULTY MANAGEMENT
# ═══════════════════════════════════════════════
@admin_required
def manage_faculty(request):
    qs = Faculty.objects.select_related('user', 'department').filter(is_active=True, user__is_deleted=False).order_by('employee_id')
    return render(request, 'admin_dashboard/manage_faculty.html', {'faculties': qs})


@admin_required
def add_faculty(request):
    branches = Branch.objects.all()
    if request.method == 'POST':
        p   = request.POST
        first_name = p.get('first_name', '').strip()
        last_name  = p.get('last_name',  '').strip()

        if len(first_name) < 3:
            messages.error(request, "First name must be at least 3 characters long.")
            return redirect('admin_dashboard:add_faculty')
        if len(last_name) < 1:
            messages.error(request, "Last name must be at least 1 character long.")
            return redirect('admin_dashboard:add_faculty')

        emp = p.get('employee_id', '').strip()
        if User.objects.filter(username=emp).exists():
            messages.error(request, f"Employee ID '{emp}' already exists.")
            return redirect('admin_dashboard:add_faculty')

        role = p.get('role', 'faculty')
        email = p.get('email', '').strip()
        temp_pwd = p.get('password', '').strip() or generate_secure_temp_password()
        user = User.objects.create_user(
            username   = emp,
            password   = temp_pwd,
            first_name = first_name,
            last_name  = last_name,
            email      = email,
            role       = role,
            phone      = p.get('phone', ''),
        )
        leave_limit_raw = p.get('monthly_leave_limit', '2.0').strip()
        try:
            monthly_leave_limit = max(0.0, float(leave_limit_raw))
        except (ValueError, TypeError):
            monthly_leave_limit = 2.0

        Faculty.objects.create(
            user        = user,
            employee_id = emp,
            department_id = p.get('department') or None,
            designation = p.get('designation', '') or ('Data Entry Operator' if role == 'deo' else 'Associate Professor'),
            monthly_leave_limit = monthly_leave_limit,
        )
        if role == 'deo':
            DEOProfile.objects.create(
                user        = user,
                employee_id = emp,
                branch_id   = p.get('department') or None,
            )
        messages.success(request, f"Faculty/Staff {emp} created successfully! (Initial Password: {temp_pwd})")
        return redirect('admin_dashboard:manage_faculty')

    return render(request, 'admin_dashboard/add_faculty.html', {'branches': branches})


@admin_required
def delete_faculty(request, pk):
    fac = get_object_or_404(Faculty, pk=pk)
    if request.method == 'POST':
        user = fac.user
        user.is_active = False
        user.is_deleted = True
        user.deleted_by_name = f"{request.user.get_full_name() or request.user.username} ({request.user.role.upper()})"
        from django.utils import timezone
        user.deleted_at = timezone.now()
        user.save()
        messages.success(request, "Faculty soft-deleted successfully.")
    return redirect('admin_dashboard:manage_faculty')



@admin_required
def edit_faculty(request, pk):
    """Edit an existing faculty member's name, phone, department, designation, and monthly leave limit."""
    fac      = get_object_or_404(Faculty, pk=pk)
    branches = Branch.objects.all()

    if request.method == 'POST':
        p = request.POST
        first_name = p.get('first_name', '').strip()
        last_name  = p.get('last_name',  '').strip()

        if len(first_name) < 3:
            messages.error(request, "First name must be at least 3 characters long.")
            return redirect('admin_dashboard:edit_faculty', pk=pk)
        if len(last_name) < 1:
            messages.error(request, "Last name must be at least 1 character long.")
            return redirect('admin_dashboard:edit_faculty', pk=pk)

        u = fac.user
        u.first_name = first_name
        u.last_name  = last_name
        u.phone      = p.get('phone',      u.phone)
        u.email      = p.get('email', '').strip()
        role = p.get('role', u.role)
        if role in dict(u.ROLE_CHOICES):
            u.role = role

        password = p.get('password', '').strip()
        if password:
            if len(password) < 6:
                messages.error(request, "Password must be at least 6 characters long.")
                return redirect('admin_dashboard:edit_faculty', pk=pk)
            u.set_password(password)

        u.save()

        dept_val = p.get('department', '').strip()
        fac.department_id = int(dept_val) if dept_val and dept_val.isdigit() else None
        fac.designation   = p.get('designation', fac.designation)
        leave_limit_raw   = p.get('monthly_leave_limit', '').strip()
        if leave_limit_raw:
            try:
                fac.monthly_leave_limit = max(0.0, float(leave_limit_raw))
            except (ValueError, TypeError):
                pass
        
        if role == 'deo':
            if not fac.designation:
                fac.designation = 'Data Entry Operator'
            deo_prof, created = DEOProfile.objects.get_or_create(
                user=u,
                defaults={
                    'employee_id': fac.employee_id,
                    'branch_id': fac.department_id
                }
            )
            if not created:
                deo_prof.branch_id = fac.department_id
                deo_prof.save()
        else:
            DEOProfile.objects.filter(user=u).delete()
            
        fac.save()
        messages.success(request, f"Faculty/Staff {fac.employee_id} updated successfully.")
        return redirect('admin_dashboard:manage_faculty')

    context = {
        'fac':       fac,
        'branches':  branches,
        'role_choices': [
            ('faculty',        'Faculty'),
            ('hod',            'Head of Department (HOD)'),
            ('lab_technician', 'Lab Technician'),
            ('deo',            'Data Entry Operator (DEO)'),
            ('admin',          'Admin'),
        ],
    }
    return render(request, 'admin_dashboard/edit_faculty.html', context)


# ═══════════════════════════════════════════════
# ASSIGN CLASS TEACHER / COUNSELLOR
# ═══════════════════════════════════════════════
@admin_required
def assign_class_teacher(request):
    """
    Assigns a class teacher to every student in a given section.
    A single POST updates all matching Student records at once.
    """
    sections  = Section.objects.select_related('branch', 'year').all()
    faculties = Faculty.objects.select_related('user').filter(is_active=True)

    if request.method == 'POST':
        section_id  = request.POST.get('section')
        faculty_id  = request.POST.get('faculty')
        updated     = Student.objects.filter(section_id=section_id).update(class_teacher_id=faculty_id)
        messages.success(request, f"Class teacher assigned to {updated} students.")
        return redirect('admin_dashboard:assign_class_teacher')

    return render(request, 'admin_dashboard/assign_class_teacher.html',
                  {'sections': sections, 'faculties': faculties})


@admin_required
def assign_counsellor(request):
    """
    Assigns a counsellor to every student in a given section.
    Supports per-semester reassignment by running this again next semester.
    """
    sections  = Section.objects.select_related('branch', 'year').all()
    faculties = Faculty.objects.select_related('user').filter(is_active=True)

    if request.method == 'POST':
        section_id = request.POST.get('section')
        faculty_id = request.POST.get('faculty')
        updated    = Student.objects.filter(section_id=section_id).update(counsellor_id=faculty_id)
        messages.success(request, f"Counsellor assigned to {updated} students.")
        return redirect('admin_dashboard:assign_counsellor')

    return render(request, 'admin_dashboard/assign_counsellor.html',
                  {'sections': sections, 'faculties': faculties})


# ═══════════════════════════════════════════════
# TIMETABLE (COLLEGE-WIDE ADMINISTRATIVE CONTROL)
# ═══════════════════════════════════════════════
from core.models import SectionTimetableMetadata
from core.timetable_service import (
    get_section_timetable_context, get_faculty_timetable_context,
    sync_class_timetable_from_data, sync_faculty_timetable_from_data,
    extract_timetable_with_ai, generate_official_timetable_pdf,
    check_faculty_schedule_clash,
    STANDARD_PERIOD_TIMINGS, DAY_LIST, PERIOD_LIST
)

@admin_required
def manage_timetable(request):
    """
    College-wide timetable dashboard for Administrators.
    Provides section filtering, faculty weekly schedules, and photo/PDF upload across all branches.
    """
    ensure_sections_for_all_branches()
    branches = Branch.objects.all().order_by('name')
    years = Year.objects.all().order_by('year')

    selected_branch = request.GET.get('branch', '')
    selected_year = request.GET.get('year', '')

    sections_qs = Section.objects.select_related('branch', 'year').all()
    if selected_branch:
        sections_qs = sections_qs.filter(branch__code=selected_branch)
    if selected_year:
        sections_qs = sections_qs.filter(year__year=selected_year)

    faculties_qs = Faculty.objects.select_related('user', 'department').filter(is_active=True)
    if selected_branch:
        faculties_qs = faculties_qs.filter(department__code=selected_branch)

    return render(request, 'admin_dashboard/manage_timetable.html', {
        'branches': branches,
        'years': years,
        'selected_branch': selected_branch,
        'selected_year': selected_year,
        'sections': sections_qs,
        'faculties': faculties_qs,
        'can_upload': True,
    })


@admin_required
def edit_timetable(request, section_id):
    """
    Allows Admin to view, edit, modify periods, and update metadata for ANY section throughout the college
    in the official VVIT Timetable layout. Handles schedule conflicts with interactive resolution.
    """
    section = get_object_or_404(Section, id=section_id)
    branch = section.branch
    subjects = Subject.objects.filter(branch=branch, year=section.year, is_deleted=False)
    faculties = Faculty.objects.filter(is_active=True).select_related('user', 'department')
    
    metadata, _ = SectionTimetableMetadata.objects.get_or_create(
        section=section,
        defaults={
            'academic_year': '2026-27',
            'room_number': 'C-402',
            'program_name': f"[Program: {branch.name} – {branch.code}]",
        }
    )

    if request.method == 'POST':
        action = request.POST.get('action', '')

        # 1. Update Official Metadata (Room, Academic Year, Effective Date, Class Teacher, Signatures)
        if action == 'update_metadata':
            metadata.academic_year = request.POST.get('academic_year', '2026-27').strip()
            metadata.room_number = request.POST.get('room_number', 'C-402').strip()
            metadata.program_name = request.POST.get('program_name', '').strip() or f"[Program: {branch.name} – {branch.code}]"
            metadata.timetable_incharge = request.POST.get('timetable_incharge', 'Timetable I/C').strip()
            metadata.hod_name = request.POST.get('hod_name', 'HOD').strip()
            metadata.dean_academics_name = request.POST.get('dean_academics_name', 'Dean, Academics').strip()
            metadata.principal_name = request.POST.get('principal_name', 'Principal').strip()

            eff_date_str = request.POST.get('with_effect_from', '')
            if eff_date_str:
                try:
                    metadata.with_effect_from = datetime.date.fromisoformat(eff_date_str)
                except Exception:
                    pass

            ct_id = request.POST.get('class_teacher')
            if ct_id:
                ct_fac = Faculty.objects.filter(id=ct_id).first()
                if ct_fac:
                    metadata.class_teacher = ct_fac
                    metadata.class_teacher_name = ct_fac.user.get_full_name()
                    Student.objects.filter(section=section).update(class_teacher=ct_fac)
            else:
                ct_name_input = request.POST.get('class_teacher_name', '').strip()
                if ct_name_input:
                    metadata.class_teacher_name = ct_name_input

            metadata.save()
            messages.success(request, f"Official timetable metadata for {section} updated.")
            return redirect('admin_dashboard:edit_timetable', section_id=section_id)

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
            return redirect('admin_dashboard:edit_timetable', section_id=section_id)
            
        if delete_slot:
            Timetable.objects.filter(section=section, day=day, period=period).delete()
            messages.success(request, f"Timetable slot for {day} Period {period} deleted.")
        else:
            subj = get_object_or_404(Subject, id=subject_id)
            fac = None
            if faculty_id:
                fac = get_object_or_404(Faculty, id=faculty_id)
            
            start_time = request.POST.get('start_time') or None
            end_time = request.POST.get('end_time') or None
            room_number = request.POST.get('room_number', '').strip() or metadata.room_number or 'C-402'

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
                                    f"Your schedule on {day}, Period {period} has been reassigned by Admin. "
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
                    return redirect('admin_dashboard:edit_timetable', section_id=section_id)

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
                    return redirect('admin_dashboard:edit_timetable', section_id=section_id)

                else:
                    # Conflict without resolution: prevent duplicate slot and alert Admin
                    messages.error(
                        request,
                        f"Schedule Clash Detected! {fac.user.get_full_name()} is already assigned to {clash_info['section_name']} "
                        f"({clash_info['subject_name']}) on {day}, Period {period}. Please resolve using 'Fix That Period (Remove Past)' or 'Fix Only Past Period'."
                    )
                    return redirect('admin_dashboard:edit_timetable', section_id=section_id)
            
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
            
        return redirect('admin_dashboard:edit_timetable', section_id=section_id)

    # Build full official VVIT timetable context
    ctx = get_section_timetable_context(section)
    ctx.update({
        'subjects': subjects,
        'faculties': faculties,
        'can_edit': True,
        'can_upload': True,
        'pdf_export_url': f"/admin-dashboard/timetable/export-pdf/{section.id}/",
    })
    return render(request, 'admin_dashboard/edit_timetable.html', ctx)


@admin_required
def ajax_check_timetable_clash(request):
    """
    Real-time AJAX endpoint to check if a faculty member has a timetable conflict on (day, period).
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


@admin_required
def upload_timetable_api(request):
    """
    AJAX API endpoint for Admin to parse and commit timetables across ALL branches.
    """
    if request.method == 'POST':
        if request.content_type and 'application/json' in request.content_type:
            try:
                body = json.loads(request.body.decode('utf-8'))
            except Exception as e:
                logger.error(f"Admin Timetable JSON decode error: {e}", exc_info=True)
                return JsonResponse({'success': False, 'error': f'Invalid JSON body: {str(e)}'}, status=400)

            action = body.get('action')
            sec_id = body.get('section_id')
            data = body.get('data')

            if action == 'commit':
                section = get_object_or_404(Section, id=sec_id)
                res = sync_class_timetable_from_data(section, data, user=request.user)
                return JsonResponse(res)

        else:
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

                section = get_object_or_404(Section, id=sec_id)
                content_type = uploaded_file.content_type
                file_bytes = uploaded_file.read()

                parsed = extract_timetable_with_ai(file_bytes, content_type)
                return JsonResponse({
                    'success': True,
                    'parsed': parsed,
                    'filename': uploaded_file.name,
                })

    return JsonResponse({'success': False, 'error': 'Invalid request method.'}, status=405)


@admin_required
def export_timetable_pdf(request, section_id):
    """
    Exports official VVIT Timetable as A4 Landscape PDF for any section in the college.
    """
    section = get_object_or_404(Section, id=section_id)
    pdf_bytes = generate_official_timetable_pdf(section)
    
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="VVIT_Timetable_{section.branch.code}_{section.year.year}_{section.name}.pdf"'
    return response


@admin_required
def faculty_timetable_view(request, faculty_id):
    """
    Displays the weekly timetable and assigned classes for any faculty member in the college.
    """
    faculty = get_object_or_404(Faculty, id=faculty_id)
    ctx = get_faculty_timetable_context(faculty)
    return render(request, 'admin_dashboard/faculty_timetable_view.html', ctx)



# ═══════════════════════════════════════════════
# SECTION MANAGEMENT (CUSTOM SECTIONS PER BRANCH & YEAR)
# ═══════════════════════════════════════════════
@admin_required
def manage_sections(request):
    """
    Allows Admin to view, create, and manage custom sections 
    for any Branch and Year as per their preference.
    """
    ensure_sections_for_all_branches()
    branches = Branch.objects.all()
    years = Year.objects.all().order_by('year')

    selected_branch_id = request.GET.get('branch', '')
    selected_year_id   = request.GET.get('year', '')

    if request.method == 'POST':
        branch_id = request.POST.get('branch')
        year_id   = request.POST.get('year')
        sec_name  = request.POST.get('name', '').strip().upper()

        if not branch_id or not year_id or not sec_name:
            messages.error(request, "Branch, Year, and Section Name are all required.")
        else:
            branch = get_object_or_404(Branch, id=branch_id)
            year   = get_object_or_404(Year, id=year_id)

            if Section.objects.filter(branch=branch, year=year, name=sec_name).exists():
                messages.error(request, f"Section '{sec_name}' already exists for {branch.code} — {year}.")
            else:
                new_sec = Section.objects.create(branch=branch, year=year, name=sec_name)
                messages.success(request, f"Section '{new_sec}' created successfully!")
                return redirect(f"{request.path}?branch={branch_id}&year={year_id}")

    sections_qs = Section.objects.select_related('branch', 'year').annotate(student_count=Count('student'))

    if selected_branch_id:
        sections_qs = sections_qs.filter(branch_id=selected_branch_id)
    if selected_year_id:
        sections_qs = sections_qs.filter(year_id=selected_year_id)

    sections = sections_qs.order_by('branch__name', 'year__year', 'name')

    context = {
        'branches': branches,
        'years': years,
        'sections': sections,
        'selected_branch_id': selected_branch_id,
        'selected_year_id': selected_year_id,
    }
    return render(request, 'admin_dashboard/manage_sections.html', context)


@admin_required
def delete_section(request, pk):
    """Allows Admin to delete a section if no students are assigned to it."""
    section = get_object_or_404(Section, pk=pk)
    sec_name = str(section)

    if request.method == 'POST':
        if section.student_set.exists():
            messages.error(request, f"Cannot delete '{sec_name}': {section.student_set.count()} students are assigned to this section.")
            return redirect('admin_dashboard:manage_sections')

        section.delete()
        messages.success(request, f"Section '{sec_name}' deleted successfully.")
        return redirect('admin_dashboard:manage_sections')

    return render(request, 'admin_dashboard/confirm_delete.html', {
        'object_name': f"Section {sec_name}",
        'cancel_url': 'admin_dashboard:manage_sections'
    })


# ═══════════════════════════════════════════════
# ATTENDANCE OVERRIDE
# ═══════════════════════════════════════════════
@admin_required
def attendance_list(request):
    """
    Admin view of all attendance records with filters.
    Admin has no date restriction (can edit any record).
    """
    qs = (
        Attendance.objects
        .select_related('student__user', 'timetable_entry__subject', 'timetable_entry__section')
        .order_by('-date', 'student__roll_number')
    )

    date_filter    = request.GET.get('date',    '')
    section_filter = request.GET.get('section', '')
    if date_filter:
        qs = qs.filter(date=date_filter)
    if section_filter:
        qs = qs.filter(timetable_entry__section_id=section_filter)

    paginator = Paginator(qs, 30)
    page      = paginator.get_page(request.GET.get('page', 1))
    sections  = Section.objects.select_related('branch', 'year').all()

    context = {
        'page':           page,
        'sections':       sections,
        'date_filter':    date_filter,
        'section_filter': section_filter,
    }
    return render(request, 'admin_dashboard/attendance_list.html', context)


@admin_required
def edit_attendance(request, pk):
    """Admin can override any attendance record without date restrictions."""
    record = get_object_or_404(
        Attendance.objects.select_related(
            'student__user', 'timetable_entry__subject'
        ), pk=pk
    )
    if request.method == 'POST':
        new_status = request.POST.get('status', record.status)
        if new_status in ('P', 'A'):
            record.status = new_status
            record.save()
            messages.success(request, "Attendance record updated.")
        return redirect('admin_dashboard:attendance_list')

    return render(request, 'admin_dashboard/edit_attendance.html', {'record': record})



@admin_required
def release_results(request):
    """
    Admin sees all exams with their release status.
    Clicking Release:
      1. Marks the exam as released
      2. Sends a result email to every student who sat that exam
    """
    exams = (
        Exam.objects
        .select_related('branch', 'year')
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

        exam = get_object_or_404(Exam, pk=exam_id)

        release_obj, _ = ResultRelease.objects.get_or_create(exam=exam)

        if action == 'release':
            release_obj.released    = True
            release_obj.released_at = timezone.now()
            release_obj.released_by = request.user
            release_obj.save()

            # Create in-app Notification for students
            Notification.objects.create(
                title=f"Result Released: {exam.name}",
                message=f"Results for '{exam.name}' have been officially published by Admin. Log in to your student portal to view your grades and CGPA.",
                notif_type=Notification.TYPE_RESULT,
                priority=Notification.PRIORITY_URGENT,
                target_role='student',
                target_branch=exam.branch if hasattr(exam, 'branch') else None,
                created_by=request.user
            )

            # Send parent SMS notifications
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

        elif action == 'unrelease':
            release_obj.released = False
            release_obj.save()
            messages.warning(request, f"Results hidden for '{exam.name}'.")

        return redirect('admin_dashboard:release_results')

    context = {
        'exams':       exams,
        'release_map': release_map,
    }
    return render(request, 'admin_dashboard/release_results.html', context)


# ═══════════════════════════════════════════════
# FACULTY ATTENDANCE MANAGEMENT (ADMIN)
# ═══════════════════════════════════════════════
@admin_required
def faculty_attendance_report(request):
    """
    Admin view to manage & view Faculty Attendance across all departments.
    Supports filtering by Department/Branch, Month-wise (`month_year`), and Custom Date Range (`date_from`, `date_to`).
    Admin can also mark daily attendance for any faculty member.
    """
    today = timezone.localdate()

    branches = Branch.objects.all()
    selected_branch_id = request.GET.get('branch', '')
    month_year         = request.GET.get('month_year', '')
    date_from          = request.GET.get('date_from', '')
    date_to            = request.GET.get('date_to', '')
    selected_date_str  = request.GET.get('date', today.isoformat())

    try:
        selected_date = datetime.date.fromisoformat(selected_date_str)
    except (ValueError, TypeError):
        selected_date = today

    faculty_qs = Faculty.objects.filter(is_active=True, user__is_deleted=False).select_related('user', 'department')
    if selected_branch_id:
        faculty_qs = faculty_qs.filter(department_id=selected_branch_id)
    faculties = faculty_qs.order_by('department__code', 'employee_id')

    # Fetch approved leave applications for the selected mark date
    approved_leaves = {
        lr.faculty_id: lr
        for lr in FacultyLeaveRequest.objects.filter(
            status='approved',
            start_date__lte=selected_date,
            end_date__gte=selected_date
        ).select_related('faculty')
    }

    # Save attendance POST
    if request.method == 'POST':
        date_param = request.POST.get('date', today.isoformat())
        try:
            post_date = datetime.date.fromisoformat(date_param)
        except ValueError:
            post_date = today

        existing_date_records = {
            att.faculty_id: att for att in FacultyAttendance.objects.filter(date=post_date)
        }
        post_approved_leaves = {
            lr.faculty_id: lr
            for lr in FacultyLeaveRequest.objects.filter(
                status='approved',
                start_date__lte=post_date,
                end_date__gte=post_date
            )
        }

        saved_count = 0
        locked_count = 0
        now = timezone.now()

        for fac in faculties:
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
                    absent_locked_until = rec.absent_locked_until if (rec and rec.absent_locked_until and rec.absent_locked_until > now) else (now + datetime.timedelta(hours=3))
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
            messages.info(request, f"{locked_count} faculty record(s) marked Absent within the last 3 hours remain locked from modification.")
        messages.success(request, f"Faculty attendance updated for {saved_count} staff members for {post_date.strftime('%d %b %Y')}.")
        return redirect(f"{request.path}?branch={selected_branch_id}&date={post_date.isoformat()}&month_year={month_year}&date_from={date_from}&date_to={date_to}")

    # Build log query
    records_qs = FacultyAttendance.objects.select_related('faculty__user', 'faculty__department', 'marked_by')
    if selected_branch_id:
        records_qs = records_qs.filter(faculty__department_id=selected_branch_id)

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

    records = records_qs.order_by('-date', 'faculty__department__code', 'faculty__employee_id')

    today_records = {
        att.faculty_id: att for att in FacultyAttendance.objects.filter(date=selected_date)
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
        1 for fac in faculties
        if (fac.id in today_records and today_records[fac.id].status == 'P')
        or (fac.id not in today_records and fac.id not in approved_leaves)
    )
    total_absent  = sum(
        1 for fac in faculties
        if fac.id in today_records and today_records[fac.id].status == 'A'
    )
    total_leave   = sum(
        1 for fac in faculties
        if (fac.id in today_records and today_records[fac.id].status == 'L')
        or (fac.id not in today_records and fac.id in approved_leaves and not approved_leaves[fac.id].is_half_day)
    )
    total_half_day = sum(
        1 for fac in faculties
        if (fac.id in today_records and today_records[fac.id].status == 'HD')
        or (fac.id not in today_records and fac.id in approved_leaves and approved_leaves[fac.id].is_half_day)
    )
    total_half_day_eq = round(total_half_day * 0.5, 1)

    context = {
        'branches':           branches,
        'selected_branch_id': selected_branch_id,
        'faculties':          faculties,
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
    return render(request, 'admin_dashboard/faculty_attendance.html', context)


def _send_result_emails(exam, request):
    """
    Send individual result emails to every student who has results for this exam.
    Returns (sent_count, failed_count).
    """
    results = (
        Result.objects
        .filter(exam=exam)
        .select_related('student__user', 'subject')
        .order_by('student__roll_number', 'subject__name')
    )

    # Group results by student
    student_results = {}
    for r in results:
        sid = r.student.id
        if sid not in student_results:
            student_results[sid] = {
                'student': r.student,
                'results': [],
            }
        student_results[sid]['results'].append(r)

    sent = 0
    failed = 0

    from core.sms_utils import build_result_email_body

    for sid, data in student_results.items():
        student = data['student']
        email   = student.user.email

        if not email:
            failed += 1
            continue

        subject_line = f"[Exam Results Published] {exam.name} Semester Results"
        body = build_result_email_body(student, exam, data['results'])

        try:
            send_mail(
                subject      = subject_line,
                message      = body,
                from_email   = django_settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=False,
            )
            sent += 1
        except Exception as e:
            print(f"Email failed for {email}: {e}")
            failed += 1

    return sent, failed


# ═══════════════════════════════════════════════
# ADMIN ATTENDANCE REPORT
# ═══════════════════════════════════════════════
@admin_required
def admin_attendance_report(request):
    """
    Comprehensive Attendance Report for the Admin.
    Allows filtering by Section and Date Range to see overall percentages
    for all students, highlighting those with low attendance.
    """
    today = timezone.localdate()
    sections = Section.objects.select_related('branch', 'year').all()

    section_id = request.GET.get('section')
    date_from  = request.GET.get('date_from', (today - datetime.timedelta(days=30)).isoformat())
    date_to    = request.GET.get('date_to',   today.isoformat())

    report_data = []
    if section_id:
        att_qs = (
            Attendance.objects
            .filter(
                timetable_entry__section_id=section_id,
                date__gte=date_from,
                date__lte=date_to,
            )
            .select_related('student__user')
        )

        student_map = {}
        for rec in att_qs:
            sid = rec.student.id
            if sid not in student_map:
                student_map[sid] = {
                    'roll':    rec.student.roll_number,
                    'name':    rec.student.user.get_full_name(),
                    'total':   0,
                    'present': 0,
                }
            student_map[sid]['total'] += 1
            if rec.status == 'P':
                student_map[sid]['present'] += 1

        for sid, d in student_map.items():
            t = d['total']
            p = d['present']
            d['pct']    = round(p / t * 100, 1) if t else 0
            d['absent'] = t - p
            d['low']    = d['pct'] < getattr(django_settings, 'LOW_ATTENDANCE_THRESHOLD', 75)
            report_data.append(d)

        report_data.sort(key=lambda x: x['roll'])

    context = {
        'sections':    sections,
        'report_data': report_data,
        'section_id':  section_id,
        'date_from':   date_from,
        'date_to':     date_to,
        'threshold':   getattr(django_settings, 'LOW_ATTENDANCE_THRESHOLD', 75),
    }
    return render(request, 'admin_dashboard/admin_attendance_report.html', context)


# ═══════════════════════════════════════════════
# ADD RESULTS
# ═══════════════════════════════════════════════
@admin_required
def add_results(request):
    """
    Admin directly adds marks for a specific Exam, Subject, and Section.
    Shows a grid of students in the section to input marks_obtained and max_marks.
    """
    branches = Branch.objects.all()
    years    = Year.objects.all()

    branch_id = request.GET.get('branch') or request.POST.get('branch')
    year_id   = request.GET.get('year') or request.POST.get('year')

    exam_id    = request.GET.get('exam') or request.POST.get('exam')
    subject_id = request.GET.get('subject') or request.POST.get('subject')
    section_id = request.GET.get('section') or request.POST.get('section')

    # Validate cross-parameters to prevent mismatch errors
    if branch_id and year_id:
        if exam_id and not Exam.objects.filter(id=exam_id, branch_id=branch_id, year_id=year_id).exists():
            exam_id = None
        if subject_id and not Subject.objects.filter(id=subject_id, branch_id=branch_id, year_id=year_id, is_deleted=False).exists():
            subject_id = None
        if section_id and not Section.objects.filter(id=section_id, branch_id=branch_id, year_id=year_id).exists():
            section_id = None
    else:
        # If branch or year are not both selected, clear subsequent selections
        exam_id = None
        subject_id = None
        section_id = None

    # Filter querysets based on branch and year
    if branch_id and year_id:
        exams    = Exam.objects.filter(branch_id=branch_id, year_id=year_id).order_by('-date')
        subjects = Subject.objects.filter(branch_id=branch_id, year_id=year_id, is_deleted=False).select_related('branch', 'year')
        sections = Section.objects.filter(branch_id=branch_id, year_id=year_id).select_related('branch', 'year')
    else:
        exams    = Exam.objects.none()
        subjects = Subject.objects.none()
        sections = Section.objects.none()

    students = []
    if exam_id and subject_id and section_id:
        students = (
            Student.objects
            .filter(section_id=section_id, is_active=True)
            .select_related('user')
            .order_by('roll_number')
        )

    # Fetch existing results if any to prefill
    existing_results = {}
    if exam_id and subject_id and students:
        results = Result.objects.filter(
            exam_id=exam_id, subject_id=subject_id, student__in=students
        )
        for r in results:
            existing_results[r.student.id] = {
                'marks_obtained': r.marks_obtained,
                'max_marks': r.max_marks
            }

    if request.method == 'POST' and exam_id and subject_id and section_id:
        exam    = get_object_or_404(Exam, id=exam_id)
        subject = get_object_or_404(Subject, id=subject_id)
        
        saved_count = 0
        for student in students:
            marks_str = request.POST.get(f"marks_obtained_{student.id}")
            max_str   = request.POST.get(f"max_marks_{student.id}")
            
            if marks_str and max_str:
                try:
                    marks_obt = float(marks_str)
                    max_mks   = float(max_str)
                    
                    Result.objects.update_or_create(
                        student=student,
                        exam=exam,
                        subject=subject,
                        defaults={
                            'marks_obtained': marks_obt,
                            'max_marks': max_mks,
                            'grade': '',  # Clear grade so Result.save() recalculates it
                        }
                    )
                    saved_count += 1
                except ValueError:
                    pass
        
        messages.success(request, f"Successfully saved results for {saved_count} students.")
        return redirect(f"{request.path}?branch={branch_id}&year={year_id}&exam={exam_id}&subject={subject_id}&section={section_id}")

    context = {
        'branches': branches,
        'years': years,
        'branch_id': branch_id,
        'year_id': year_id,
        'exams': exams,
        'subjects': subjects,
        'sections': sections,
        'exam_id': exam_id,
        'subject_id': subject_id,
        'section_id': section_id,
        'students': students,
        'existing_results': existing_results,
    }
    return render(request, 'admin_dashboard/add_results.html', context)


# ═══════════════════════════════════════════════
# BULK CSV UPLOAD RESULTS
# ═══════════════════════════════════════════════
@admin_required
def bulk_upload_results(request):
    """
    Admin uploads a CSV file of marks for a specific Exam and Subject.
    CSV Format: Roll Number, Marks Obtained, Max Marks
    """
    import csv
    import io
    
    branches = Branch.objects.all()
    years    = Year.objects.all()

    branch_id = request.GET.get('branch') or request.POST.get('branch')
    year_id   = request.GET.get('year') or request.POST.get('year')

    # Filter querysets based on branch and year
    if branch_id and year_id:
        exams = Exam.objects.filter(branch_id=branch_id, year_id=year_id).order_by('-date')
        subjects = Subject.objects.filter(branch_id=branch_id, year_id=year_id, is_deleted=False).select_related('branch', 'year')
    else:
        exams = Exam.objects.none()
        subjects = Subject.objects.none()
    
    if request.method == 'POST':
        exam_id = request.POST.get('exam')
        subject_id = request.POST.get('subject')
        
        if not exam_id or not subject_id:
            messages.error(request, "Please select both Exam and Subject.")
            return redirect('admin_dashboard:bulk_upload_results')
            
        exam = get_object_or_404(Exam, id=exam_id)
        subject = get_object_or_404(Subject, id=subject_id)
        
        if 'csv_file' not in request.FILES:
            messages.error(request, "Please upload a CSV file.")
            return redirect('admin_dashboard:bulk_upload_results')
            
        csv_file = request.FILES['csv_file']
        if not csv_file.name.endswith('.csv'):
            messages.error(request, "Invalid file format. Please upload a .csv file.")
            return redirect('admin_dashboard:bulk_upload_results')
            
        try:
            data_set = csv_file.read().decode('utf-8-sig')
            io_string = io.StringIO(data_set)
            
            success_count = 0
            errors = []
            
            reader = csv.reader(io_string, delimiter=',', quotechar='"')
            is_first_row = True
            for row_idx, row in enumerate(reader, start=1):
                if not row or not any(cell.strip() for cell in row):
                    continue  # Skip empty rows
                
                # Dynamic header check on first non-empty row
                if is_first_row:
                    is_first_row = False
                    first_cell = row[0].strip().lower()
                    if 'roll' in first_cell or 'student' in first_cell or 'name' in first_cell:
                        continue  # Skip actual header row
                    
                if len(row) < 2:
                    errors.append(f"Row {row_idx}: Missing columns. Expected at least Roll Number and Marks.")
                    continue
                    
                roll_num = row[0].strip().upper()
                marks_str = row[1].strip()
                max_str = row[2].strip() if len(row) > 2 and row[2].strip() else '100'
                
                try:
                    marks_obt = float(marks_str)
                    max_mks = float(max_str)
                except ValueError:
                    errors.append(f"Row {row_idx}: Invalid marks format for {roll_num}.")
                    continue
                    
                try:
                    student = Student.objects.get(roll_number=roll_num)
                    Result.objects.update_or_create(
                        student=student,
                        exam=exam,
                        subject=subject,
                        defaults={
                            'marks_obtained': marks_obt,
                            'max_marks': max_mks,
                            'grade': '',  # Clear grade so Result.save() recalculates it
                        }
                    )
                    success_count += 1
                except Student.DoesNotExist:
                    errors.append(f"Row {row_idx}: Student {roll_num} not found.")
            
            if success_count > 0:
                messages.success(request, f"Successfully uploaded marks for {success_count} students.")
            if errors:
                for err in errors[:5]:  # Show top 5 errors
                    messages.error(request, err)
                if len(errors) > 5:
                    messages.error(request, f"...and {len(errors) - 5} more errors.")
                    
        except Exception as e:
            messages.error(request, f"Error processing file: {e}")
            
        return redirect(f"/admin-dashboard/bulk-upload-results/?branch={branch_id}&year={year_id}")

    context = {
        'branches': branches,
        'years': years,
        'branch_id': branch_id,
        'year_id': year_id,
        'exams': exams,
        'subjects': subjects,
    }
    return render(request, 'admin_dashboard/bulk_upload_results.html', context)


@admin_required
def download_sample_results_csv(request):
    """Generates and returns a sample CSV file for bulk result uploads."""
    from django.http import HttpResponse
    import csv
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="sample_results_upload.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Roll Number', 'Marks Obtained', 'Max Marks'])
    writer.writerow(['24BQ1A4901', '85.5', '100'])
    writer.writerow(['24BQ1A4902', '92', '100'])
    writer.writerow(['24BQ1A4903', '76.5', '100'])
    
    return response


# ═══════════════════════════════════════════════
# BULK CSV UPLOAD STUDENTS
# ═══════════════════════════════════════════════
@admin_required
def bulk_upload_students(request):
    """
    Admin uploads a CSV file of students to create their accounts and profiles.
    CSV Format: Roll Number, First Name, Last Name, Email, Phone, Branch Code, Year, Section, Admission Year
    """
    import csv
    import io
    from django.db import transaction
    
    if request.method == 'POST':
        if 'csv_file' not in request.FILES:
            messages.error(request, "Please upload a CSV file.")
            return redirect('admin_dashboard:bulk_upload_students')
            
        csv_file = request.FILES['csv_file']
        if not csv_file.name.endswith('.csv'):
            messages.error(request, "Invalid file format. Please upload a .csv file.")
            return redirect('admin_dashboard:bulk_upload_students')
            
        try:
            data_set = csv_file.read().decode('utf-8-sig')
            io_string = io.StringIO(data_set)
            
            success_count = 0
            errors = []
            
            reader = csv.reader(io_string, delimiter=',', quotechar='"')
            is_first_row = True
            
            with transaction.atomic():
                for row_idx, row in enumerate(reader, start=1):
                    if not row or not any(cell.strip() for cell in row):
                        continue

                    # Dynamic header check on first non-empty row
                    if is_first_row:
                        is_first_row = False
                        first_cell = row[0].strip().lower()
                        if 'roll' in first_cell or 'student' in first_cell or 'name' in first_cell:
                            continue  # Skip actual header row
                        
                    if len(row) < 9:
                        errors.append(f"Row {row_idx}: Missing columns. Expected 9, got {len(row)}.")
                        continue
                        
                    roll_number = row[0].strip().upper()
                    first_name = row[1].strip()
                    last_name = row[2].strip()
                    email = row[3].strip()
                    phone = row[4].strip()
                    branch_code = row[5].strip().upper()
                    year_val = row[6].strip()
                    section_name = row[7].strip()
                    adm_year = row[8].strip()
                    
                    if not roll_number:
                        errors.append(f"Row {row_idx}: Roll Number is required.")
                        continue
                        
                    # Lookup foreign keys
                    branch = Branch.objects.filter(code=branch_code).first() if branch_code else None
                    year = Year.objects.filter(year=year_val).first() if year_val else None
                    section = Section.objects.filter(name__iexact=section_name, branch=branch, year=year).first() if (section_name and branch and year) else None
                    
                    if not branch:
                        errors.append(f"Row {row_idx}: Invalid Branch Code '{branch_code}'.")
                        continue
                        
                    if year_val and not year:
                        errors.append(f"Row {row_idx}: Invalid Year '{year_val}'.")
                        continue
                        
                    if section_name and not section:
                        errors.append(f"Row {row_idx}: Section '{section_name}' does not exist for Branch '{branch_code}' and Year '{year_val}'.")
                        continue
                        
                    # Create User
                    if User.objects.filter(username=roll_number).exists():
                        errors.append(f"Row {row_idx}: User with username '{roll_number}' already exists.")
                        continue
                        
                    if not email:
                        email = f"{roll_number}@vvitu.net"
                        
                    temp_pwd = generate_secure_temp_password()
                    user = User.objects.create_user(
                        username=roll_number,
                        password=temp_pwd,
                        first_name=first_name,
                        last_name=last_name,
                        email=email,
                        role='student',
                        phone=phone
                    )
                    
                    # Create Student
                    adm_year_int = int(adm_year) if adm_year.isdigit() else timezone.now().year
                    Student.objects.create(
                        user=user,
                        roll_number=roll_number,
                        branch=branch,
                        year=year,
                        section=section,
                        admission_year=adm_year_int
                    )
                    success_count += 1

                # Inside atomic block: raise to trigger rollback if any errors
                if errors:
                    for err in errors[:5]:
                        messages.error(request, err)
                    if len(errors) > 5:
                        messages.error(request, f"...and {len(errors) - 5} more errors. No data was saved (transaction rolled back).")
                    raise Exception("Upload failed due to data errors.")

            # Atomic block exited cleanly — success message only shown here
            messages.success(request, f"Successfully imported {success_count} students.")
            return redirect('admin_dashboard:manage_students')
                
        except Exception as e:
            if not errors:
                messages.error(request, f"Error processing file: {str(e)}")
            return redirect('admin_dashboard:bulk_upload_students')
            
    return render(request, 'admin_dashboard/bulk_upload_students.html')


@admin_required
def download_sample_students_csv(request):
    """Generates and returns a sample CSV file for bulk student uploads."""
    from django.http import HttpResponse
    import csv
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="sample_students_upload.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Roll Number', 'First Name', 'Last Name', 'Email', 'Phone', 'Branch Code', 'Year', 'Section', 'Admission Year'])
    writer.writerow(['24BQ1A4999', 'Rahul', 'Sharma', 'rahul@example.com', '9876543210', 'CSM', '1', 'A', '2024'])
    writer.writerow(['24BQ1A4998', 'Priya', 'Reddy', 'priya@example.com', '9876543211', 'CSE', '1', 'B', '2024'])
    
    return response


# ═══════════════════════════════════════════════
# SUBJECT CRUD
# ═══════════════════════════════════════════════
@admin_required
def manage_subjects(request):
    qs = Subject.objects.filter(is_deleted=False).select_related('branch', 'year', 'faculty__user').order_by('branch', 'year', 'semester', 'name')
    
    search = request.GET.get('q', '')
    branch_filter = request.GET.get('branch', '')
    
    if search:
        qs = qs.filter(
            Q(name__icontains=search) | 
            Q(code__icontains=search)
        )
    if branch_filter:
        qs = qs.filter(branch_id=branch_filter)
        
    paginator = Paginator(qs, 25)
    page = paginator.get_page(request.GET.get('page', 1))
    branches = Branch.objects.all()
    
    return render(request, 'admin_dashboard/manage_subjects.html', {
        'page': page,
        'search': search,
        'branch_filter': branch_filter,
        'branches': branches
    })


@admin_required
def add_subject(request):
    branches = Branch.objects.all()
    years = Year.objects.all()
    faculties = Faculty.objects.filter(is_active=True).select_related('user', 'department')
    
    if request.method == 'POST':
        p = request.POST
        name = p.get('name', '').strip()
        code = p.get('code', '').strip().upper()
        branch_id = p.get('branch')
        year_id = p.get('year')
        semester = p.get('semester')
        faculty_id = p.get('faculty') or None
        credits_val = p.get('credits', '3')
        is_lab = p.get('is_lab') == 'true'
        
        if not name or not code or not branch_id or not year_id or not semester:
            messages.error(request, "Please fill in all required fields.")
            return redirect('admin_dashboard:add_subject')
            
        if Subject.objects.filter(code=code).exists():
            messages.error(request, f"Subject code '{code}' already exists.")
            return redirect('admin_dashboard:add_subject')
            
        try:
            credits_int = int(credits_val)
        except ValueError:
            credits_int = 3
            
        Subject.objects.create(
            name=name,
            code=code,
            branch_id=branch_id,
            year_id=year_id,
            semester=semester,
            faculty_id=faculty_id,
            credits=credits_int,
            is_lab=is_lab
        )
        messages.success(request, f"Subject '{name}' created successfully.")
        return redirect('admin_dashboard:manage_subjects')
        
    return render(request, 'admin_dashboard/add_subject.html', {
        'branches': branches,
        'years': years,
        'faculties': faculties,
        'semester_choices': Subject.SEMESTER_CHOICES,
    })


@admin_required
def delete_subject(request, pk):
    subject = get_object_or_404(Subject, pk=pk)
    if request.method == 'POST':
        subject.is_deleted = True
        subject.deleted_by_name = f"{request.user.get_full_name() or request.user.username} ({request.user.role.upper()})"
        from django.utils import timezone
        subject.deleted_at = timezone.now()
        subject.save()
        messages.success(request, "Subject soft-deleted successfully.")
    return redirect('admin_dashboard:manage_subjects')


# ═══════════════════════════════════════════════
# DATABASE BACKUPS & EXPORTS
# ═══════════════════════════════════════════════
@admin_required
def backup_list(request):
    """View to list all database backups."""
    from core.models import DatabaseBackup
    import os
    from django.conf import settings

    backups_dir = os.path.join(settings.BASE_DIR, 'backups')
    if not os.path.exists(backups_dir):
        os.makedirs(backups_dir)

    backups = DatabaseBackup.objects.select_related('created_by').order_by('-created_at')
    
    # Verify file existence on disk
    for b in backups:
        path = os.path.join(backups_dir, b.filename)
        b.exists = os.path.exists(path)

    return render(request, 'admin_dashboard/backups.html', {
        'backups': backups,
        'page_title': 'System Backups & Data Export'
    })


@admin_required
def create_backup(request):
    """Create a new database JSON dump file and log it."""
    from django.core.management import call_command
    from core.models import DatabaseBackup
    import os
    import io
    from django.conf import settings
    from django.utils import timezone

    backups_dir = os.path.join(settings.BASE_DIR, 'backups')
    if not os.path.exists(backups_dir):
        os.makedirs(backups_dir)

    timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
    filename = f"db_backup_{timestamp}.json"
    filepath = os.path.join(backups_dir, filename)

    try:
        # Dump data with 2-space indentation, excluding temporary session tokens & admin logs
        out = io.StringIO()
        call_command('dumpdata', exclude=['contenttypes', 'auth.Permission', 'sessions', 'admin.logentry'], indent=2, stdout=out)
        
        # Write to backups directory
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(out.getvalue())

        # Log in database
        file_size = os.path.getsize(filepath)
        DatabaseBackup.objects.create(
            filename=filename,
            created_by=request.user,
            file_size=file_size
        )
        messages.success(request, f"Backup file '{filename}' created successfully.")
    except Exception as e:
        messages.error(request, f"Error creating backup: {str(e)}")

    return redirect('admin_dashboard:backup_list')


@admin_required
def download_backup(request, pk):
    """Serve a backup file for download."""
    from core.models import DatabaseBackup
    import os
    from django.conf import settings
    from django.http import HttpResponse, Http404

    backup = get_object_or_404(DatabaseBackup, pk=pk)
    backups_dir = os.path.join(settings.BASE_DIR, 'backups')
    filepath = os.path.join(backups_dir, backup.filename)

    if not os.path.exists(filepath):
        raise Http404("Backup file not found on disk.")

    with open(filepath, 'rb') as f:
        response = HttpResponse(f.read(), content_type='application/json')
        response['Content-Disposition'] = f'attachment; filename="{backup.filename}"'
        return response


@admin_required
@require_POST
def restore_backup(request, pk):
    """Restore database from a selected JSON backup file."""
    from django.core.management import call_command
    from core.models import DatabaseBackup
    import os
    from django.conf import settings

    backup = get_object_or_404(DatabaseBackup, pk=pk)
    backups_dir = os.path.join(settings.BASE_DIR, 'backups')
    filepath = os.path.join(backups_dir, backup.filename)

    if not os.path.exists(filepath):
        messages.error(request, f"Backup file '{backup.filename}' not found on disk.")
        return redirect('admin_dashboard:backup_list')

    try:
        # Load data from backup file
        call_command('loaddata', filepath)
        messages.success(request, f"Database restored successfully from '{backup.filename}'.")
    except Exception as e:
        messages.error(request, f"Error restoring database: {str(e)}")

    return redirect('admin_dashboard:backup_list')


@admin_required
@require_POST
def delete_backup(request, pk):
    """Delete a backup record and its corresponding file on disk."""
    from core.models import DatabaseBackup
    import os
    from django.conf import settings

    if request.method == 'POST':
        backup = get_object_or_404(DatabaseBackup, pk=pk)
        backups_dir = os.path.join(settings.BASE_DIR, 'backups')
        filepath = os.path.join(backups_dir, backup.filename)

        # Delete file from disk
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except OSError as err:
                logger.warning(f"Could not remove backup file {filepath}: {err}")

        # Delete DB log
        backup.delete()
        messages.success(request, f"Backup record '{backup.filename}' deleted.")

    return redirect('admin_dashboard:backup_list')


@admin_required
def export_database_pdf(request):
    """Generate and download a beautifully styled PDF of all system data and student results."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    import io
    
    from accounts.models import Student, Faculty
    from core.models import Subject, Branch, Section, Attendance

    # Fetch data
    active_students = Student.objects.filter(user__is_deleted=False).select_related('user', 'branch', 'section', 'year').order_by('roll_number')
    active_faculty = Faculty.objects.filter(user__is_deleted=False).select_related('user', 'department').order_by('employee_id')
    active_subjects = Subject.objects.filter(is_deleted=False).select_related('branch', 'year').order_by('branch', 'code')
    branches = Branch.objects.all()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=36, leftMargin=36, topMargin=40, bottomMargin=40)
    story = []

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=20,
        textColor=colors.HexColor('#991b1b'),
        spaceAfter=15,
        alignment=1 # Center
    )
    subtitle_style = ParagraphStyle(
        'SubtitleStyle',
        parent=styles['Heading2'],
        fontName='Helvetica',
        fontSize=12,
        textColor=colors.HexColor('#4b5563'),
        spaceAfter=25,
        alignment=1 # Center
    )
    section_heading = ParagraphStyle(
        'SectionHeading',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=14,
        textColor=colors.HexColor('#1f2937'),
        spaceBefore=15,
        spaceAfter=10
    )
    body_style = ParagraphStyle(
        'BodyStyle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        textColor=colors.HexColor('#374151')
    )
    header_cell_style = ParagraphStyle(
        'HeaderCellStyle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        textColor=colors.white
    )

    # 1. Cover Page
    story.append(Spacer(1, 100))
    story.append(Paragraph("VASIREDDY VENKATADRI INTERNATIONAL TECHNOLOGICAL UNIVERSITY", title_style))
    story.append(Paragraph("Consolidated Institutional Data Audit & Student Results Report", subtitle_style))
    story.append(Spacer(1, 50))
    
    meta_data = [
        [Paragraph("<b>Report Generated On:</b>", body_style), Paragraph(timezone.now().strftime("%d %B %Y, %I:%M %p"), body_style)],
        [Paragraph("<b>Generated By:</b>", body_style), Paragraph(f"{request.user.get_full_name()} ({request.user.username})", body_style)],
        [Paragraph("<b>Role:</b>", body_style), Paragraph("Portal Administrator", body_style)],
        [Paragraph("<b>Database Status:</b>", body_style), Paragraph("Active / Verified", body_style)],
    ]
    t_meta = Table(meta_data, colWidths=[150, 250])
    t_meta.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LINEBELOW', (0,0), (-1,-1), 0.5, colors.lightgrey),
    ]))
    story.append(t_meta)
    story.append(PageBreak())

    # 2. Institutional Overview
    story.append(Paragraph("1. Institutional Overview & Statistics", section_heading))
    overview_data = [
        [Paragraph("<b>Entity</b>", header_cell_style), Paragraph("<b>Active Count</b>", header_cell_style)],
        [Paragraph("Academic Branches / Depts", body_style), Paragraph(str(branches.count()), body_style)],
        [Paragraph("Registered Students", body_style), Paragraph(str(active_students.count()), body_style)],
        [Paragraph("Faculty Members", body_style), Paragraph(str(active_faculty.count()), body_style)],
        [Paragraph("Registered Subjects", body_style), Paragraph(str(active_subjects.count()), body_style)],
    ]
    t_overview = Table(overview_data, colWidths=[200, 200])
    t_overview.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#991b1b')),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e5e7eb')),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(t_overview)
    story.append(Spacer(1, 20))

    # 3. Student Registry Table
    story.append(Paragraph("2. Active Student Registry", section_heading))
    stud_headers = [
        Paragraph("<b>Roll No</b>", header_cell_style),
        Paragraph("<b>Name</b>", header_cell_style),
        Paragraph("<b>Branch</b>", header_cell_style),
        Paragraph("<b>Year & Sec</b>", header_cell_style),
        Paragraph("<b>Email</b>", header_cell_style),
    ]
    stud_table_data = [stud_headers]
    for s in active_students:
        stud_table_data.append([
            Paragraph(s.roll_number, body_style),
            Paragraph(s.user.get_full_name(), body_style),
            Paragraph(s.branch.code if s.branch else "—", body_style),
            Paragraph(f"{s.year.year if s.year else '—'} Year / {s.section.name if s.section else '—'}", body_style),
            Paragraph(s.user.email, body_style),
        ])
    t_stud = Table(stud_table_data, colWidths=[80, 120, 60, 90, 150])
    t_stud.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1f2937')),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e5e7eb')),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(t_stud)
    story.append(PageBreak())

    # 4. Faculty Registry Table
    story.append(Paragraph("3. Faculty Directory", section_heading))
    fac_headers = [
        Paragraph("<b>Employee ID</b>", header_cell_style),
        Paragraph("<b>Name</b>", header_cell_style),
        Paragraph("<b>Department</b>", header_cell_style),
        Paragraph("<b>Designation</b>", header_cell_style),
        Paragraph("<b>Phone</b>", header_cell_style),
    ]
    fac_table_data = [fac_headers]
    for f in active_faculty:
        fac_table_data.append([
            Paragraph(f.employee_id, body_style),
            Paragraph(f.user.get_full_name(), body_style),
            Paragraph(f.department.code if f.department else "—", body_style),
            Paragraph(f.designation or "—", body_style),
            Paragraph(f.user.phone or "—", body_style),
        ])
    t_fac = Table(fac_table_data, colWidths=[80, 120, 80, 120, 100])
    t_fac.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1f2937')),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e5e7eb')),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(t_fac)
    story.append(PageBreak())

    # 4. Curriculum Summary Table
    story.append(Paragraph("4. Curriculum Summary", section_heading))
    sub_headers = [
        Paragraph("<b>Code</b>", header_cell_style),
        Paragraph("<b>Subject Name</b>", header_cell_style),
        Paragraph("<b>Branch</b>", header_cell_style),
        Paragraph("<b>Year</b>", header_cell_style),
        Paragraph("<b>Credits</b>", header_cell_style),
    ]
    sub_table_data = [sub_headers]
    for sub in active_subjects:
        sub_table_data.append([
            Paragraph(sub.code, body_style),
            Paragraph(sub.name, body_style),
            Paragraph(sub.branch.code if sub.branch else "—", body_style),
            Paragraph(sub.year.get_year_display() if sub.year else "—", body_style),
            Paragraph(str(sub.credits), body_style),
        ])
    t_sub = Table(sub_table_data, colWidths=[80, 180, 80, 100, 60])
    t_sub.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1f2937')),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e5e7eb')),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(t_sub)
    story.append(PageBreak())

    # 5. Consolidated Student Results Table
    story.append(Paragraph("5. Consolidated Student Results & CGPA Summary", section_heading))
    res_headers = [
        Paragraph("<b>Roll No</b>", header_cell_style),
        Paragraph("<b>Student Name</b>", header_cell_style),
        Paragraph("<b>Branch</b>", header_cell_style),
        Paragraph("<b>Overall Attendance</b>", header_cell_style),
        Paragraph("<b>CGPA</b>", header_cell_style),
    ]
    res_table_data = [res_headers]
    
    for s in active_students:
        cgpa = s.calculate_cgpa()
        att_recs = Attendance.objects.filter(student=s)
        total_att = att_recs.count()
        present = att_recs.filter(status='P').count()
        att_pct = round((present / total_att * 100), 2) if total_att > 0 else 0.0

        res_table_data.append([
            Paragraph(s.roll_number, body_style),
            Paragraph(s.user.get_full_name(), body_style),
            Paragraph(s.branch.code if s.branch else "—", body_style),
            Paragraph(f"{att_pct}%", body_style),
            Paragraph(f"{cgpa:.2f}", body_style),
        ])
    t_res = Table(res_table_data, colWidths=[80, 150, 80, 110, 80])
    t_res.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#991b1b')),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e5e7eb')),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(t_res)
    story.append(PageBreak())

    # 6. Examination Schedules & Syllabus Milestone Targets
    from core.models import ExamSchedule, SubjectTopicPlan
    story.append(Paragraph("6. Examination Timetables & Syllabus Milestones", section_heading))
    exam_schedules = ExamSchedule.objects.all().select_related('branch', 'year').order_by('start_date')
    exam_headers = [
        Paragraph("<b>Exam Title</b>", header_cell_style),
        Paragraph("<b>Branch & Year</b>", header_cell_style),
        Paragraph("<b>Exam Type</b>", header_cell_style),
        Paragraph("<b>Required Units</b>", header_cell_style),
        Paragraph("<b>Faculty Deadline</b>", header_cell_style),
    ]
    exam_table_data = [exam_headers]
    for es in exam_schedules:
        b_name = es.branch.code if es.branch else "All Branches"
        exam_table_data.append([
            Paragraph(es.title, body_style),
            Paragraph(f"{b_name} Y{es.year.year} S{es.semester}", body_style),
            Paragraph(es.get_exam_type_display(), body_style),
            Paragraph(f"{es.target_units} Units", body_style),
            Paragraph(es.target_completion_date.strftime("%d-%b-%Y"), body_style),
        ])
    if len(exam_table_data) > 1:
        t_exam = Table(exam_table_data, colWidths=[140, 90, 100, 80, 90])
        t_exam.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1f2937')),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e5e7eb')),
            ('TOPPADDING', (0,0), (-1,-1), 5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ]))
        story.append(t_exam)
    else:
        story.append(Paragraph("<i>No active examination milestones scheduled.</i>", body_style))
    story.append(Spacer(1, 15))

    # 7. Faculty Leave Quotas & Limits
    story.append(Paragraph("7. Faculty Monthly Leave Allocations", section_heading))
    cur_today = timezone.localdate()
    leave_headers = [
        Paragraph("<b>Emp ID</b>", header_cell_style),
        Paragraph("<b>Faculty Name</b>", header_cell_style),
        Paragraph("<b>Department</b>", header_cell_style),
        Paragraph("<b>Monthly Quota</b>", header_cell_style),
        Paragraph("<b>Taken This Month</b>", header_cell_style),
    ]
    leave_table_data = [leave_headers]
    for f in active_faculty:
        taken = f.get_monthly_leaves_taken(cur_today.year, cur_today.month)
        quota = float(f.monthly_leave_limit or 2.0)
        leave_table_data.append([
            Paragraph(f.employee_id, body_style),
            Paragraph(f.full_name, body_style),
            Paragraph(f.department.code if f.department else "General", body_style),
            Paragraph(f"{quota} Days", body_style),
            Paragraph(f"{taken} Days", body_style),
        ])
    t_leave = Table(leave_table_data, colWidths=[80, 150, 90, 90, 90])
    t_leave.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1f2937')),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e5e7eb')),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(t_leave)

    doc.build(story)
    response = HttpResponse(buf.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="VVITU_Portal_Database_Audit_Report.pdf"'
    return response


@admin_required
def export_student_results_pdf(request):
    """Generate and download a beautifully styled PDF of all student results."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    import io
    
    from accounts.models import Student
    from core.models import Result

    # Fetch active students with their results
    active_students = Student.objects.filter(user__is_deleted=False).select_related('user', 'branch', 'section', 'year').order_by('roll_number')

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=36, leftMargin=36, topMargin=40, bottomMargin=40)
    story = []

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=20,
        textColor=colors.HexColor('#991b1b'),
        spaceAfter=15,
        alignment=1 # Center
    )
    subtitle_style = ParagraphStyle(
        'SubtitleStyle',
        parent=styles['Heading2'],
        fontName='Helvetica',
        fontSize=12,
        textColor=colors.HexColor('#4b5563'),
        spaceAfter=25,
        alignment=1 # Center
    )
    student_header_style = ParagraphStyle(
        'StudentHeaderStyle',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=12,
        textColor=colors.HexColor('#991b1b'),
        spaceBefore=15,
        spaceAfter=5
    )
    student_sub_style = ParagraphStyle(
        'StudentSubStyle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        textColor=colors.HexColor('#4b5563'),
        spaceAfter=10
    )
    body_style = ParagraphStyle(
        'BodyStyle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        textColor=colors.HexColor('#374151')
    )
    header_cell_style = ParagraphStyle(
        'HeaderCellStyle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        textColor=colors.white
    )

    # 1. Cover Page
    story.append(Spacer(1, 100))
    story.append(Paragraph("VASIREDDY VENKATADRI INTERNATIONAL TECHNOLOGICAL UNIVERSITY", title_style))
    story.append(Paragraph("Detailed Student Academic Results Registry", subtitle_style))
    story.append(Spacer(1, 50))
    
    meta_data = [
        [Paragraph("<b>Report Generated On:</b>", body_style), Paragraph(timezone.now().strftime("%d %B %Y, %I:%M %p"), body_style)],
        [Paragraph("<b>Generated By:</b>", body_style), Paragraph(f"{request.user.get_full_name()} ({request.user.username})", body_style)],
        [Paragraph("<b>Role:</b>", body_style), Paragraph("Portal Administrator", body_style)],
        [Paragraph("<b>Report Content:</b>", body_style), Paragraph("All registered student exam marks, grades, and subjects.", body_style)],
    ]
    t_meta = Table(meta_data, colWidths=[150, 250])
    t_meta.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LINEBELOW', (0,0), (-1,-1), 0.5, colors.lightgrey),
    ]))
    story.append(t_meta)
    story.append(PageBreak())

    # 2. Detailed Results by Student
    for student in active_students:
        results = Result.objects.filter(student=student).select_related('exam', 'subject').order_by('exam__date', 'subject__code')
        
        # Student Section Header
        story.append(Paragraph(f"{student.roll_number} — {student.user.get_full_name()}", student_header_style))
        story.append(Paragraph(
            f"<b>Branch:</b> {student.branch.name if student.branch else '—'} | "
            f"<b>Year/Section:</b> {student.year.get_year_display() if student.year else '—'} / {student.section.name if student.section else '—'} | "
            f"<b>Current CGPA:</b> {student.calculate_cgpa():.2f}",
            student_sub_style
        ))

        if results.exists():
            res_headers = [
                Paragraph("<b>Exam</b>", header_cell_style),
                Paragraph("<b>Subject Code</b>", header_cell_style),
                Paragraph("<b>Subject Name</b>", header_cell_style),
                Paragraph("<b>Marks</b>", header_cell_style),
                Paragraph("<b>Grade</b>", header_cell_style),
            ]
            res_table_data = [res_headers]
            for r in results:
                marks_str = f"{r.marks_obtained} / {r.max_marks}"
                res_table_data.append([
                    Paragraph(r.exam.name, body_style),
                    Paragraph(r.subject.code, body_style),
                    Paragraph(r.subject.name, body_style),
                    Paragraph(marks_str, body_style),
                    Paragraph(r.grade or "—", body_style),
                ])
            t_res = Table(res_table_data, colWidths=[100, 80, 160, 100, 60])
            t_res.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1f2937')),
                ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e5e7eb')),
                ('TOPPADDING', (0,0), (-1,-1), 4),
                ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ]))
            story.append(t_res)
        else:
            story.append(Paragraph("<i>No examination results recorded for this student.</i>", body_style))
            
        story.append(Spacer(1, 20))

    doc.build(story)
    response = HttpResponse(buf.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="VVITU_Portal_All_Student_Results.pdf"'
    return response


# ─────────────────────────────────────────────
# ADMIN LEAVE MANAGEMENT (ALL DEPARTMENTS)
# ─────────────────────────────────────────────
@admin_required
def manage_leave_requests(request):
    status_filter = request.GET.get('status', '')
    dept_filter   = request.GET.get('department', '')
    role_filter   = request.GET.get('role', '')  # 'hod', 'faculty', 'emergency'
    
    leaves_qs = FacultyLeaveRequest.objects.select_related('faculty__user', 'faculty__department', 'action_by').order_by('-created_at')
    
    if status_filter in ['pending', 'approved', 'rejected']:
        leaves_qs = leaves_qs.filter(status=status_filter)
        
    if dept_filter.isdigit():
        leaves_qs = leaves_qs.filter(faculty__department_id=int(dept_filter))

    if role_filter == 'hod':
        leaves_qs = leaves_qs.filter(faculty__user__role='hod')
    elif role_filter == 'faculty':
        leaves_qs = leaves_qs.filter(faculty__user__role='faculty')
    elif role_filter == 'emergency':
        leaves_qs = leaves_qs.filter(is_limit_exceeded=True)
        
    branches = Branch.objects.all()
    pending_count = FacultyLeaveRequest.objects.filter(status='pending').count()
    hod_pending_count = FacultyLeaveRequest.objects.filter(status='pending', faculty__user__role='hod').count()
    emergency_pending_count = FacultyLeaveRequest.objects.filter(status='pending', is_limit_exceeded=True).count()
    
    return render(request, 'admin_dashboard/leave_requests.html', {
        'leaves': leaves_qs,
        'status_filter': status_filter,
        'dept_filter': dept_filter,
        'role_filter': role_filter,
        'branches': branches,
        'pending_count': pending_count,
        'hod_pending_count': hod_pending_count,
        'emergency_pending_count': emergency_pending_count,
    })


@admin_required
def action_leave_request(request, pk, action):
    leave_req = get_object_or_404(FacultyLeaveRequest, pk=pk)
    
    if action not in ['approve', 'reject']:
        messages.error(request, "Invalid leave action.")
        return redirect('admin_dashboard:manage_leave_requests')
        
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
            curr_d += datetime.timedelta(days=1)
    
    try:
        status_text = "Approved" if new_status == 'approved' else "Rejected"
        notif_msg = (
            f"Your leave request for {leave_req.get_leave_type_display()} "
            f"({leave_req.start_date.strftime('%d-%b-%Y')} to {leave_req.end_date.strftime('%d-%b-%Y')}) "
            f"has been {status_text} by Admin ({request.user.get_full_name() or request.user.username})."
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

Your leave application request has been reviewed by College Administration.

Details:
- Leave Type: {leave_req.get_leave_type_display()}
- Duration: {leave_req.start_date.strftime('%d-%b-%Y')} to {leave_req.end_date.strftime('%d-%b-%Y')} ({leave_req.total_days} days)
- Status: {status_text.upper()}
- Action By: Admin ({request.user.get_full_name() or request.user.username})
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
            sms_text = f"VVITU ALERT: Your {leave_req.get_leave_type_display()} leave request ({leave_req.start_date.strftime('%d/%m')} to {leave_req.end_date.strftime('%d/%m')}) has been {status_text} by Admin. Log in for details."
            send_sms(phone_num, sms_text)

    except Exception as dispatch_err:
        logger.warning(f"Failed to send leave action notification/SMS/email: {dispatch_err}")
        
    messages.success(request, f"Leave request for {leave_req.faculty.full_name} {new_status} successfully.")
    return redirect('admin_dashboard:manage_leave_requests')


# ═══════════════════════════════════════════════
# ACHIEVEMENTS MANAGEMENT & COLLEGE ACHIEVEMENTS
# ═══════════════════════════════════════════════
@admin_required
def manage_achievements(request):
    """
    Allows Admin to view all achievements (Student, Faculty, College),
    verify student/faculty pending achievements, and add official College Achievements.
    """
    from accounts.models import Achievement
    from django.db.models import Q
    
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        category = request.POST.get('category', 'college')
        date_achieved = request.POST.get('date_achieved')
        
        if not title or not description or not date_achieved:
            messages.error(request, "Please fill in all required achievement fields.")
            return redirect('admin_dashboard:manage_achievements')
            
        Achievement.objects.create(
            user=request.user,
            title=title,
            description=description,
            category=category,
            date_achieved=date_achieved,
            is_verified=True,
            verified_by=request.user
        )
        
        messages.success(request, f"Official Achievement '{title}' created successfully.")
        return redirect('admin_dashboard:manage_achievements')
        
    category_filter = request.GET.get('category', '')
    status_filter = request.GET.get('status', '')
    search = request.GET.get('q', '').strip()
    
    achievements = Achievement.objects.select_related('user', 'verified_by').order_by('-date_achieved', '-created_at')
    
    if category_filter:
        achievements = achievements.filter(category=category_filter)
    if status_filter == 'pending':
        achievements = achievements.filter(is_verified=False)
    elif status_filter == 'verified':
        achievements = achievements.filter(is_verified=True)
    if search:
        achievements = achievements.filter(
            Q(title__icontains=search) | Q(description__icontains=search) | Q(user__username__icontains=search) | Q(user__first_name__icontains=search) | Q(user__last_name__icontains=search)
        )
        
    pending_count = Achievement.objects.filter(is_verified=False).count()
    college_count = Achievement.objects.filter(category='college').count()
    
    return render(request, 'admin_dashboard/manage_achievements.html', {
        'achievements': achievements,
        'category_filter': category_filter,
        'status_filter': status_filter,
        'search': search,
        'pending_count': pending_count,
        'college_count': college_count,
        'category_choices': Achievement.CATEGORY_CHOICES,
    })


@admin_required
def action_achievement(request, pk, action):
    """Approve or unverify an achievement."""
    from accounts.models import Achievement
    achievement = get_object_or_404(Achievement, pk=pk)
    
    if action == 'approve':
        achievement.is_verified = True
        achievement.verified_by = request.user
        achievement.save()
        messages.success(request, f"Achievement '{achievement.title}' verified successfully.")
    elif action == 'reject':
        achievement.is_verified = False
        achievement.verified_by = None
        achievement.save()
        messages.info(request, f"Achievement '{achievement.title}' set to unverified.")
        
    return redirect('admin_dashboard:manage_achievements')


@admin_required
def delete_achievement(request, pk):
    """Delete an achievement record."""
    from accounts.models import Achievement
    achievement = get_object_or_404(Achievement, pk=pk)
    if request.method == 'POST':
        title = achievement.title
        achievement.delete()
        messages.success(request, f"Achievement '{title}' deleted.")
    return redirect('admin_dashboard:manage_achievements')


# ═══════════════════════════════════════════════
# STUDENT FEE MANAGEMENT SYSTEM
# ═══════════════════════════════════════════════
@admin_required
def manage_fees(request):
    """
    Allows Admin to view, update, and manage student fee structures and payments.
    Supports College, Hostel, Bus, NBA, Exam, Book Bank, and Misc fee components.
    """
    from accounts.models import Student, StudentFee
    from core.models import Year, Branch
    from django.db.models import Sum, Q

    years = Year.objects.all()
    branches = Branch.objects.all()
    
    year_id = request.GET.get('year', '')
    branch_id = request.GET.get('branch', '')
    status_filter = request.GET.get('status', '')
    search = request.GET.get('q', '').strip()

    students = Student.objects.filter(is_active=True, user__is_deleted=False).select_related('user', 'branch', 'section', 'year').order_by('roll_number')

    if branch_id:
        students = students.filter(branch_id=branch_id)
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
            stu = get_object_or_404(Student, id=stu_id)

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

            return redirect(f"{request.path}?year={year_id}&branch={branch_id}&q={search}&status={status_filter}")

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

            messages.success(request, f"Standard fee structure applied to {count} students.")
            return redirect(f"{request.path}?year={year_id}&branch={branch_id}")

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
        'branches': branches,
        'sel_year': sel_year,
        'year_id': year_id,
        'branch_id': branch_id,
        'search': search,
        'status_filter': status_filter,
        'total_expected': total_expected,
        'total_collected': total_collected,
        'total_outstanding': total_outstanding,
        'role': 'admin',
    })


@login_required
def faculty_class_history(request):
    """
    Admin View — College-wide audit log of all classes conducted by faculty across ALL branches,
    with authority to assign substitute proxy classes to free faculty in any branch.
    Admin can filter by Branch, search by Faculty Name, Subject Code, Employee ID, and Date Range.
    """
    if request.user.role != 'admin':
        messages.error(request, "Access restricted to College Administration.")
        return redirect('accounts:dashboard')

    import datetime
    from core.transfer_utils import get_conducted_class_history, get_free_faculty_for_period, parse_flexible_date
    from core.sms_utils import send_class_transfer_notification
    from core.models import Timetable, ClassTransfer

    today = timezone.localdate()

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'assign_proxy':
            timetable_id = request.POST.get('timetable_id')
            substitute_id = request.POST.get('substitute_id')
            reason = request.POST.get('reason', 'Admin Proxy Assignment').strip()
            date_val_str = request.POST.get('date', '').strip()

            t_date = parse_flexible_date(date_val_str) or today

            slot = get_object_or_404(Timetable, id=timetable_id)
            substitute = get_object_or_404(Faculty, id=substitute_id, is_active=True)

            # Verify substitute is FREE (Admin can choose substitute college-wide or branch-scoped)
            free_fac = get_free_faculty_for_period(
                date=t_date,
                period=slot.period,
                department=None,
                exclude_faculty=slot.faculty
            )

            if substitute not in free_fac:
                messages.error(
                    request,
                    f"Prof. {substitute.full_name} ({substitute.department.code if substitute.department else 'General'}) is NOT free during Period {slot.period} on {t_date.strftime('%d-%b-%Y')}."
                )
            else:
                transfer_obj, _ = ClassTransfer.objects.update_or_create(
                    timetable_entry=slot,
                    date=t_date,
                    defaults={
                        'original_faculty': slot.faculty,
                        'substitute_faculty': substitute,
                        'reason': reason or 'Admin Official Proxy Assignment',
                        'status': 'pending',
                        'rejection_reason': None,
                        'responded_at': None,
                        'assigned_by_role': 'admin',
                        'transfer_type': 'proxy',
                        'assigned_by': request.user,
                    }
                )

                send_class_transfer_notification(transfer_obj)
                branch_label = f"{slot.section.branch.code} " if (slot.section and slot.section.branch) else ""
                messages.success(
                    request,
                    f"Official proxy request for Period {slot.period} ({slot.subject.code} — {branch_label}{slot.section.name if slot.section else ''}) sent to Prof. {substitute.full_name}. Notification dispatched — class will transfer once accepted."
                )
            return redirect('admin_dashboard:faculty_class_history')

        elif action == 'cancel_proxy':
            transfer_id = request.POST.get('transfer_id')
            if transfer_id:
                ct_to_cancel = ClassTransfer.objects.filter(id=transfer_id).first()
                if ct_to_cancel:
                    desc = f"Period {ct_to_cancel.timetable_entry.period} ({ct_to_cancel.timetable_entry.subject.code if ct_to_cancel.timetable_entry.subject else 'Class'}) on {ct_to_cancel.date.strftime('%d-%b-%Y')}"
                    ct_to_cancel.delete()
                    messages.success(request, f"Class transfer/proxy for {desc} was cancelled. Reverted to regular instructor.")
                else:
                    messages.error(request, "Class transfer record not found.")
            return redirect('admin_dashboard:faculty_class_history')

    # Search & Filter Parameters
    search_query = request.GET.get('search', '').strip()
    branch_id = request.GET.get('branch_id', '').strip()
    selected_fac_id = request.GET.get('faculty_id', '').strip()
    date_from_str = request.GET.get('date_from', '').strip()
    date_to_str = request.GET.get('date_to', '').strip()

    selected_branch = None
    if branch_id and branch_id.isdigit():
        selected_branch = Branch.objects.filter(id=int(branch_id)).first()

    date_from = parse_flexible_date(date_from_str)
    date_to = parse_flexible_date(date_to_str)

    # Conducted Class History (College-Wide / All Branches)
    conducted_history = get_conducted_class_history(
        branch=selected_branch,
        faculty=selected_fac_id if selected_fac_id else None,
        search_query=search_query,
        date_from=date_from,
        date_to=date_to
    )

    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
    page = request.GET.get('page', 1)
    paginator = Paginator(conducted_history, 50)
    try:
        history_page = paginator.page(page)
    except PageNotAnInteger:
        history_page = paginator.page(1)
    except EmptyPage:
        history_page = paginator.page(paginator.num_pages)

    branches = Branch.objects.all().order_by('code')
    
    # Filter faculty list based on selected branch or all faculty
    faculty_qs = Faculty.objects.filter(is_active=True).select_related('user', 'department')
    if selected_branch:
        faculty_qs = faculty_qs.filter(department=selected_branch)
    all_faculty = faculty_qs.order_by('department__code', 'user__first_name')

    day_name = today.strftime('%A')
    day_slots = Timetable.objects.filter(day__iexact=day_name).select_related(
        'faculty__user', 'subject', 'section__branch', 'section__year'
    ).order_by('section__branch__code', 'period', 'section__name')

    context = {
        'conducted_history': history_page,
        'history_page': history_page,
        'paginator': paginator,
        'total_records_count': len(conducted_history),
        'branches': branches,
        'all_faculty': all_faculty,
        'day_slots': day_slots,
        'selected_branch': selected_branch,
        'branch_id': int(branch_id) if (branch_id and branch_id.isdigit()) else '',
        'search_query': search_query,
        'selected_fac_id': selected_fac_id,
        'date_from': date_from_str,
        'date_to': date_to_str,
        'today': today,
    }
    return render(request, 'admin_dashboard/faculty_class_history.html', context)


@login_required
def ajax_get_all_timetable_slots(request):
    """
    Return JSON list of scheduled class slots college-wide or filtered by branch on a specific date/day.
    Each slot contains: id, period, timing, subject_code, subject_name, faculty_name, section_name, branch_code.
    """
    if request.user.role != 'admin':
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    from core.transfer_utils import parse_flexible_date
    date_str = request.GET.get('date')
    branch_id_str = request.GET.get('branch_id')

    req_date = parse_flexible_date(date_str) if date_str else timezone.localdate()
    if not req_date:
        req_date = timezone.localdate()

    day_name = req_date.strftime('%A')

    slots_qs = Timetable.objects.filter(
        day__iexact=day_name
    ).select_related('subject', 'faculty__user', 'section', 'section__year', 'section__branch')


    if branch_id_str and branch_id_str.isdigit():
        slots_qs = slots_qs.filter(section__branch_id=int(branch_id_str))

    slots = slots_qs.order_by('section__branch__code', 'period', 'section__name')

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

        branch_code = s.section.branch.code if (s.section and s.section.branch) else 'GEN'
        sec_name = f"Y{s.section.year.year} Sec {s.section.name}" if (s.section and s.section.year) else (s.section.name if s.section else '')

        data.append({
            'id': s.id,
            'period': s.period,
            'timing': timing_str,
            'branch_id': s.section.branch_id if (s.section and s.section.branch_id) else None,
            'branch_code': branch_code,
            'subject_code': s.subject.code if s.subject else 'N/A',
            'subject_name': s.subject.name if s.subject else 'N/A',
            'original_faculty_id': s.faculty.id if s.faculty else None,
            'original_faculty_name': f"Prof. {s.faculty.full_name}" if s.faculty else "Unassigned",
            'section_name': f"{branch_code} {sec_name}",
        })

    return JsonResponse({'slots': data, 'day_name': day_name, 'date_str': req_date.strftime('%d-%b-%Y')})


@login_required
def ajax_get_free_faculty(request):
    """
    Return JSON list of free faculty for a specific (date, period) across all departments or filtered by branch.
    """
    if request.user.role != 'admin':
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    from core.transfer_utils import get_free_faculty_for_period, parse_flexible_date
    date_str = request.GET.get('date')
    period_str = request.GET.get('period')
    branch_id_str = request.GET.get('branch_id') or request.GET.get('department')
    exclude_fac_id = request.GET.get('exclude_faculty_id')

    if not date_str or not period_str:
        return JsonResponse({'error': 'date and period parameters required'}, status=400)

    req_date = parse_flexible_date(date_str)
    if not req_date:
        return JsonResponse({'error': 'Invalid date format'}, status=400)

    try:
        period = int(period_str)
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Invalid period format'}, status=400)

    dept = None
    if branch_id_str and branch_id_str.isdigit():
        dept = Branch.objects.filter(id=int(branch_id_str)).first()

    exclude_fac = None
    if exclude_fac_id and exclude_fac_id.isdigit():
        exclude_fac = Faculty.objects.filter(id=int(exclude_fac_id)).first()

    free_fac_qs = get_free_faculty_for_period(
        date=req_date,
        period=period,
        department=dept,
        exclude_faculty=exclude_fac
    )

    data = [
        {
            'id': f.id,
            'name': f.full_name,
            'employee_id': f.employee_id,
            'department': f.department.code if f.department else 'Gen',
        }
        for f in free_fac_qs
    ]
    return JsonResponse({'free_faculty': data})


# ─────────────────────────────────────────────
# ADMIN COLLEGE-WIDE CLASS DIARY & SYLLABUS TRACKER
# ─────────────────────────────────────────────
@admin_required
def class_diary_coverage(request):
    """
    Allows Administrator to track which faculty discussed which topics across all branches,
    and monitor unit completion / syllabus progress college-wide.
    """
    from core.transfer_utils import parse_flexible_date
    from core.models import ClassDiary

    # Filters
    search_query = request.GET.get('search', '').strip()
    branch_id    = request.GET.get('branch_id', '').strip()
    year_id      = request.GET.get('year_id', '').strip()
    faculty_id   = request.GET.get('faculty_id', '').strip()
    subject_id   = request.GET.get('subject_id', '').strip()
    section_id   = request.GET.get('section_id', '').strip()
    unit_filter  = request.GET.get('unit_number', '').strip()
    date_from_str= request.GET.get('date_from', '').strip()
    date_to_str  = request.GET.get('date_to', '').strip()

    base_qs = ClassDiary.objects.all().select_related('section__branch', 'section__year', 'subject__branch', 'faculty__user', 'faculty__department')

    diary_qs = base_qs

    if branch_id and branch_id.isdigit():
        diary_qs = diary_qs.filter(Q(section__branch_id=int(branch_id)) | Q(subject__branch_id=int(branch_id)) | Q(faculty__department_id=int(branch_id)))

    if year_id and year_id.isdigit():
        diary_qs = diary_qs.filter(section__year_id=int(year_id))

    if faculty_id and faculty_id.isdigit():
        diary_qs = diary_qs.filter(faculty_id=int(faculty_id))

    if subject_id and subject_id.isdigit():
        diary_qs = diary_qs.filter(subject_id=int(subject_id))

    if section_id and section_id.isdigit():
        diary_qs = diary_qs.filter(section_id=int(section_id))

    if unit_filter and unit_filter.isdigit():
        diary_qs = diary_qs.filter(unit_number=int(unit_filter))

    if search_query:
        diary_qs = diary_qs.filter(
            Q(topic_covered__icontains=search_query) |
            Q(discussion_summary__icontains=search_query) |
            Q(homework_assignment__icontains=search_query) |
            Q(faculty__user__first_name__icontains=search_query) |
            Q(faculty__user__last_name__icontains=search_query) |
            Q(faculty__employee_id__icontains=search_query) |
            Q(subject__name__icontains=search_query) |
            Q(subject__code__icontains=search_query) |
            Q(section__branch__name__icontains=search_query) |
            Q(section__branch__code__icontains=search_query)
        )

    date_from = parse_flexible_date(date_from_str)
    date_to   = parse_flexible_date(date_to_str)

    if date_from:
        diary_qs = diary_qs.filter(date__gte=date_from)
    if date_to:
        diary_qs = diary_qs.filter(date__lte=date_to)

    entries = diary_qs.order_by('-date', 'period')

    # Dropdown lists for Admin
    branches = Branch.objects.all().order_by('code')
    years = Year.objects.all().order_by('year')
    all_faculty = Faculty.objects.filter(is_active=True, user__is_deleted=False).select_related('user', 'department').order_by('department__code', 'user__first_name')
    all_subjects = Subject.objects.filter(is_deleted=False).select_related('branch', 'year').order_by('branch__code', 'code')
    all_sections = Section.objects.all().select_related('branch', 'year').order_by('branch__code', 'year__year', 'name')

    if branch_id and branch_id.isdigit():
        b_id = int(branch_id)
        all_faculty = all_faculty.filter(department_id=b_id)
        all_subjects = all_subjects.filter(branch_id=b_id)
        all_sections = all_sections.filter(branch_id=b_id)

    # ── Syllabus / Unit Coverage Aggregation per Faculty & Subject ──
    coverage_stats = []
    timetable_qs = Timetable.objects.all().select_related('faculty__user', 'faculty__department', 'subject__branch', 'section__branch', 'section__year')
    if branch_id and branch_id.isdigit():
        timetable_qs = timetable_qs.filter(section__branch_id=int(branch_id))

    pair_keys = set()
    for t in timetable_qs:
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
            'branch': sec.branch if sec else (subj.branch if subj else fac.department),
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

    coverage_stats.sort(key=lambda x: (getattr(x['branch'], 'code', ''), x['subject'].code, str(x['section'])))

    # Handle audit & dispatch reminders trigger
    if request.method == 'POST' and request.POST.get('action') == 'dispatch_reminders':
        b_id = int(branch_id) if branch_id and branch_id.isdigit() else None
        sent = check_and_dispatch_syllabus_reminders(branch_id=b_id, triggered_by=request.user)
        messages.success(request, f"University syllabus audit completed: {sent} reminder notification(s) dispatched to respective faculty and HODs.")
        return redirect('admin_dashboard:class_diary_coverage')

    # University-wide KPIs
    total_logs_count = base_qs.count()
    active_faculty_count = base_qs.values('faculty').distinct().count()
    active_subjects_count = base_qs.values('subject').distinct().count()
    avg_progress = int(sum(c['progress_pct'] for c in coverage_stats) / len(coverage_stats)) if coverage_stats else 0
    total_overdue_count = sum(c['overdue_topics_count'] for c in coverage_stats)
    delayed_mid1_count = sum(1 for c in coverage_stats if not c['is_mid1_target_met'] and c['mid1_deadline'] and timezone.localdate() > c['mid1_deadline'])

    context = {
        'entries': entries,
        'coverage_stats': coverage_stats,
        'branches': branches,
        'years': years,
        'all_faculty': all_faculty,
        'all_subjects': all_subjects,
        'all_sections': all_sections,
        'total_logs_count': total_logs_count,
        'active_faculty_count': active_faculty_count,
        'active_subjects_count': active_subjects_count,
        'avg_progress': avg_progress,
        'total_overdue_count': total_overdue_count,
        'delayed_mid1_count': delayed_mid1_count,
        'search_query': search_query,
        'branch_id': int(branch_id) if branch_id and branch_id.isdigit() else '',
        'year_id': int(year_id) if year_id and year_id.isdigit() else '',
        'faculty_id': int(faculty_id) if faculty_id and faculty_id.isdigit() else '',
        'subject_id': int(subject_id) if subject_id and subject_id.isdigit() else '',
        'section_id': int(section_id) if section_id and section_id.isdigit() else '',
        'unit_number': int(unit_filter) if unit_filter and unit_filter.isdigit() else '',
        'unit_choices': ClassDiary.UNIT_CHOICES,
        'date_from': date_from_str,
        'date_to': date_to_str,
    }
    return render(request, 'admin_dashboard/class_diary_coverage.html', context)


# ─────────────────────────────────────────────
# STUDENT COUNSELLING DOSSIER (ADMIN)
# ─────────────────────────────────────────────
@admin_required
def student_counselling_report(request, student_id):
    """
    View complete counselling dossier for any student university-wide.
    """
    from core.counselling_utils import get_student_counselling_dossier
    from django.urls import reverse

    student = get_object_or_404(Student, id=student_id, is_active=True, user__is_deleted=False)
    dossier = get_student_counselling_dossier(student)

    context = {
        'dossier': dossier,
        'pdf_download_url': reverse('admin_dashboard:download_student_counselling_report_pdf', args=[student.id]),
        'back_url': reverse('admin_dashboard:manage_students'),
    }
    return render(request, 'reports/counselling_report.html', context)


@admin_required
def download_student_counselling_report_pdf(request, student_id):
    """
    Download official student counselling dossier PDF university-wide for Administrator.
    """
    from core.counselling_utils import generate_counselling_report_pdf
    from django.http import HttpResponse

    student = get_object_or_404(Student, id=student_id, is_active=True, user__is_deleted=False)
    pdf_bytes = generate_counselling_report_pdf(student)

    filename = f"{student.roll_number}_Counselling_Dossier.pdf"
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


# ─────────────────────────────────────────────
# SUBJECT SYLLABUS & TOPIC SCHEDULE MANAGER (ADMIN - ALL BRANCHES)
# ─────────────────────────────────────────────
@admin_required
def manage_subject_syllabus(request, subject_id=None):
    """
    Allows Admin to view, create, edit, and schedule the topic timetable for any subject
    across all branches & departments, set target dates, and monitor milestone readiness.
    """
    today = timezone.localdate()
    from core.transfer_utils import parse_flexible_date

    branches = Branch.objects.all().order_by('code')
    branch_id = request.GET.get('branch_id', '').strip()
    year_id = request.GET.get('year_id', '').strip()

    subjects_qs = Subject.objects.filter(is_deleted=False).select_related('branch', 'year', 'faculty').order_by('branch__code', 'year__year', 'semester', 'code')
    if branch_id and branch_id.isdigit():
        subjects_qs = subjects_qs.filter(branch_id=int(branch_id))
    if year_id and year_id.isdigit():
        subjects_qs = subjects_qs.filter(year_id=int(year_id))

    selected_subject = None
    if subject_id:
        selected_subject = get_object_or_404(Subject, id=subject_id, is_deleted=False)
    elif subjects_qs.exists():
        selected_subject = subjects_qs.first()

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
            return redirect('admin_dashboard:manage_subject_syllabus_subject', subject_id=selected_subject.id)

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
            
            is_comp = (request.POST.get('is_completed') == '1')
            topic.is_completed = is_comp
            if is_comp and not topic.completed_date:
                topic.completed_date = today
            elif not is_comp:
                topic.completed_date = None

            topic.save()
            messages.success(request, f"Topic '{topic.topic_name}' updated successfully.")
            return redirect('admin_dashboard:manage_subject_syllabus_subject', subject_id=selected_subject.id)

        elif action == 'delete_topic':
            topic_id = request.POST.get('topic_id')
            topic = get_object_or_404(SubjectTopicPlan, id=topic_id, subject=selected_subject)
            t_name = topic.topic_name
            topic.delete()
            messages.success(request, f"Topic '{t_name}' deleted.")
            return redirect('admin_dashboard:manage_subject_syllabus_subject', subject_id=selected_subject.id)

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
            return redirect('admin_dashboard:manage_subject_syllabus_subject', subject_id=selected_subject.id)

        elif action == 'send_reminders':
            sent = check_and_dispatch_syllabus_reminders(subject_id=selected_subject.id, branch_id=selected_subject.branch_id, triggered_by=request.user)
            messages.success(request, f"Syllabus reminders evaluated: {sent} notification(s) sent to faculty and HOD.")
            return redirect('admin_dashboard:manage_subject_syllabus_subject', subject_id=selected_subject.id)

    progress_data = None
    topics_by_unit = {}
    if selected_subject:
        progress_data = get_subject_syllabus_progress(selected_subject)
        all_topics = SubjectTopicPlan.objects.filter(subject=selected_subject).order_by('unit_number', 'order', 'target_date')
        for u in [1, 2, 3, 4, 5]:
            topics_by_unit[u] = [t for t in all_topics if t.unit_number == u]

    years = Year.objects.all().order_by('year')

    context = {
        'branches': branches,
        'years': years,
        'branch_id': int(branch_id) if branch_id and branch_id.isdigit() else '',
        'year_id': int(year_id) if year_id and year_id.isdigit() else '',
        'subjects': subjects_qs,
        'selected_subject': selected_subject,
        'progress_data': progress_data,
        'topics_by_unit': topics_by_unit,
        'unit_choices': ClassDiary.UNIT_CHOICES,
        'milestone_choices': SubjectTopicPlan.MILESTONE_CHOICES,
        'today': today,
    }
    return render(request, 'admin_dashboard/manage_subject_syllabus.html', context)


# ─────────────────────────────────────────────
# EXAM TIMETABLE & SYLLABUS MILESTONE SCHEDULES (ADMIN - ALL BRANCHES)
# ─────────────────────────────────────────────
@admin_required
def manage_exam_schedules(request):
    """
    Allows Admin to view, create, edit, reschedule, and customize Exam Timetables
    and Syllabus Milestones (e.g. 2.5 units target before Mid-1 date) across all branches.
    """
    today = timezone.localdate()
    from core.transfer_utils import parse_flexible_date

    branches = Branch.objects.all().order_by('code')
    years = Year.objects.all().order_by('year')

    branch_id = request.GET.get('branch_id', '').strip()
    year_id = request.GET.get('year_id', '').strip()

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'save_exam_schedule':
            schedule_id = request.POST.get('schedule_id')
            branch_val = request.POST.get('branch')
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
            branch_obj = Branch.objects.filter(id=int(branch_val)).first() if branch_val and branch_val.isdigit() else None
            target_units = float(target_units_val) if target_units_val else 2.5

            b_code = branch_obj.code if branch_obj else "All Branches"
            if not title:
                title = f"{b_code} Y{year_obj.year} Sem-{semester} {dict(ExamSchedule.EXAM_TYPE_CHOICES).get(exam_type, 'Exam')}"

            if schedule_id and schedule_id.isdigit():
                sched = get_object_or_404(ExamSchedule, id=int(schedule_id))
                sched.branch = branch_obj
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
                ExamSchedule.objects.create(
                    branch=branch_obj,
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
            return redirect('admin_dashboard:manage_exam_schedules')

        elif action == 'delete_exam_schedule':
            schedule_id = request.POST.get('schedule_id')
            if schedule_id and schedule_id.isdigit():
                sched = get_object_or_404(ExamSchedule, id=int(schedule_id))
                t = sched.title
                sched.delete()
                messages.success(request, f"Exam Schedule '{t}' deleted.")
            return redirect('admin_dashboard:manage_exam_schedules')

    schedules_qs = ExamSchedule.objects.all().select_related('branch', 'year').order_by('-start_date')
    if branch_id and branch_id.isdigit():
        schedules_qs = schedules_qs.filter(Q(branch_id=int(branch_id)) | Q(branch__isnull=True))
    if year_id and year_id.isdigit():
        schedules_qs = schedules_qs.filter(year_id=int(year_id))

    context = {
        'branches': branches,
        'years': years,
        'branch_id': int(branch_id) if branch_id and branch_id.isdigit() else '',
        'year_id': int(year_id) if year_id and year_id.isdigit() else '',
        'schedules': schedules_qs,
        'exam_types': ExamSchedule.EXAM_TYPE_CHOICES,
        'semester_choices': Subject.SEMESTER_CHOICES,
        'today': today,
    }
    return render(request, 'admin_dashboard/manage_exam_schedules.html', context)


# ─────────────────────────────────────────────
# DETENTION & JUNIOR READMISSION RATIFICATION
# ─────────────────────────────────────────────
@admin_required
def manage_detention_readmissions(request):
    """
    Dean / Admin final review and ratification of student readmissions.
    """
    from accounts.models import StudentReadmissionRequest

    status_filter = request.GET.get('status', 'all')
    reqs_qs = StudentReadmissionRequest.objects.all().select_related(
        'student__user', 'student__branch', 'target_junior_year', 'target_junior_section', 'hod_reviewed_by__user'
    ).order_by('-created_at')

    if status_filter == 'pending':
        reqs_qs = reqs_qs.filter(admin_status='pending', hod_status='approved')
    elif status_filter in ['approved', 'rejected']:
        reqs_qs = reqs_qs.filter(admin_status=status_filter)

    # Detained students across all branches
    detained_students = Student.objects.filter(
        is_active=True
    ).filter(
        Q(academic_status__in=['DETAINED_ATTENDANCE', 'DETAINED_CREDITS']) | Q(is_detained=True)
    ).select_related('user', 'branch', 'year', 'section')

    return render(request, 'admin_dashboard/detention_readmissions.html', {
        'readmission_requests': reqs_qs,
        'detained_students': detained_students,
        'status_filter': status_filter,
    })


@admin_required
@require_POST
def action_readmission_request(request, pk, action):
    """
    Dean / Admin final approval or rejection of student readmission.
    If approved, executes readmission: moves student to target junior year/section.
    """
    from accounts.models import StudentReadmissionRequest

    readmission_req = get_object_or_404(StudentReadmissionRequest, pk=pk)
    remarks = request.POST.get('remarks', '').strip()

    if action == 'approve':
        readmission_req.admin_status = 'approved'
        readmission_req.admin_reviewed_by = request.user
        readmission_req.admin_reviewed_at = timezone.now()
        readmission_req.admin_remarks = remarks
        readmission_req.save()

        # Execute transfer to junior batch
        readmission_req.execute_readmission()
        messages.success(request, f"Readmission APPROVED for {readmission_req.student.roll_number}. Student has been enrolled into Junior Year {readmission_req.target_junior_year.year} (Sec {readmission_req.target_junior_section.name if readmission_req.target_junior_section else 'A'}).")
    elif action == 'reject':
        readmission_req.admin_status = 'rejected'
        readmission_req.admin_reviewed_by = request.user
        readmission_req.admin_reviewed_at = timezone.now()
        readmission_req.admin_remarks = remarks
        readmission_req.save()
        messages.warning(request, f"Readmission REJECTED for {readmission_req.student.roll_number}.")

    return redirect('admin_dashboard:manage_detention_readmissions')


# ═══════════════════════════════════════════════
# INSTITUTIONAL CLASS CONDUCTION & ATTENDANCE AUDIT
# ═══════════════════════════════════════════════

def get_institutional_class_attendance_audit_data(branch_filter=None, target_date=None, year_filter=None, sec_filter=None, fac_filter=None, status_filter=None):
    """
    Core engine for auditing faculty class conduction & student attendance college-wide across all branches.
    Accurately tracks peer class substitutions, HOD/Admin proxies, and direct faculty conduction.
    """
    if not target_date:
        target_date = timezone.localdate()

    day_name = target_date.strftime('%A').strip()
    slots_qs = list(Timetable.objects.filter(
        day__iexact=day_name
    ).select_related(
        'section', 'section__branch', 'section__year', 'subject', 'faculty__user'
    ).order_by('section__branch__code', 'section__year__year', 'section__name', 'period'))

    if branch_filter and str(branch_filter).isdigit():
        slots_qs = [s for s in slots_qs if s.section and s.section.branch_id == int(branch_filter)]

    slot_ids = {s.id for s in slots_qs}

    # Fetch Class Transfers / Proxies on target_date (accepted, completed, or pending)
    transfer_qs = ClassTransfer.objects.filter(
        date=target_date,
        status__in=['accepted', 'completed', 'pending']
    ).select_related(
        'substitute_faculty__user', 'substitute_faculty__department',
        'original_faculty__user', 'original_faculty__department',
        'timetable_entry__section__branch', 'timetable_entry__section__year',
        'timetable_entry__section', 'timetable_entry__subject',
        'timetable_entry__faculty__user'
    )

    if branch_filter and str(branch_filter).isdigit():
        b_id = int(branch_filter)
        transfer_qs = transfer_qs.filter(
            Q(timetable_entry__section__branch_id=b_id) |
            Q(original_faculty__department_id=b_id) |
            Q(substitute_faculty__department_id=b_id)
        )

    transfer_objs = list(transfer_qs)
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
        for f in Faculty.objects.filter(id__in=marked_by_fac_ids).select_related('user', 'department')
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

    branch_stats = {}

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

        b_code = slot.section.branch.code if slot.section and slot.section.branch else 'GEN'
        if b_code not in branch_stats:
            branch_stats[b_code] = {'scheduled': 0, 'marked': 0, 'unmarked': 0, 'branch': slot.section.branch}

        tot_scheduled += 1
        branch_stats[b_code]['scheduled'] += 1

        p_count = sum(1 for a in att_records if a['status'] == 'P')
        a_count = sum(1 for a in att_records if a['status'] == 'A')
        l_count = sum(1 for a in att_records if a['status'] == 'L')
        total_students = len(att_records)
        att_pct = round((p_count / total_students * 100), 1) if total_students > 0 else None

        diary_obj = diaries.get(slot.id)
        has_diary = diary_obj is not None

        fac_day_status = fac_att_map.get(slot.faculty_id, 'P') if slot.faculty else 'P'

        if is_marked:
            tot_marked += 1
            branch_stats[b_code]['marked'] += 1
            class_status = 'conducted_marked'
            status_label = 'Attendance Marked'
            status_badge = 'status-present'
        else:
            tot_unmarked += 1
            branch_stats[b_code]['unmarked'] += 1
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
            'branch': getattr(slot.section, 'branch', None),
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

    branch_summaries = []
    for b_code, bs in branch_stats.items():
        sched = bs['scheduled']
        m = bs['marked']
        pct = round((m / sched * 100), 1) if sched > 0 else 0.0
        branch_summaries.append({
            'code': b_code,
            'branch': bs['branch'],
            'scheduled': sched,
            'marked': m,
            'unmarked': bs['unmarked'],
            'pct': pct
        })
    branch_summaries.sort(key=lambda x: x['code'])

    return {
        'rows': rows,
        'tot_scheduled': tot_scheduled,
        'tot_marked': tot_marked,
        'tot_unmarked': tot_unmarked,
        'tot_transferred': tot_transferred,
        'tot_proxies': tot_proxies,
        'tot_substitutions': tot_substitutions,
        'overall_compliance_pct': round((tot_marked / tot_scheduled * 100), 1) if tot_scheduled > 0 else 0.0,
        'branch_summaries': branch_summaries,
        'day_name': day_name,
        'target_date': target_date,
    }



@admin_required
def faculty_class_attendance_audit(request):
    """
    Institutional Multi-Branch Class Conduction & Attendance Audit View for Administrators.
    Allows monitoring whether faculty members in ANY branch have entered classes and submitted attendance.
    """
    branches = Branch.objects.all().order_by('code')
    years = Year.objects.all().order_by('year')

    date_str = request.GET.get('date', '').strip()
    branch_id = request.GET.get('branch', '').strip()
    year_id = request.GET.get('year', '').strip()
    section_id = request.GET.get('section', '').strip()
    faculty_id = request.GET.get('faculty', '').strip()
    status_filter = request.GET.get('status', 'all').strip()

    if date_str:
        try:
            target_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            target_date = timezone.localdate()
    else:
        target_date = timezone.localdate()

    # Handle Urgent Reminder action
    action = request.GET.get('action')
    if action == 'remind_faculty':
        target_fac_id = request.GET.get('faculty_id')
        period_num = request.GET.get('period')
        subject_name = request.GET.get('subject')
        branch_code = request.GET.get('branch_code', '')
        if target_fac_id and period_num:
            fac = Faculty.objects.filter(id=target_fac_id).first()
            if fac:
                Notification.objects.create(
                    title=f"URGENT: Post Period {period_num} Attendance ({subject_name})",
                    message=f"Dear {fac.user.get_full_name()}, you are requested by the Dean / Central Admin to immediately mark the student attendance for Period {period_num} ({subject_name}) conducted today.",
                    notif_type=Notification.TYPE_ALERT,
                    priority=Notification.PRIORITY_URGENT,
                    target_role='faculty',
                    target_user=fac.user,
                    target_branch=fac.department,
                    created_by=request.user
                )
                messages.success(request, f"Urgent reminder notification dispatched to {fac.user.get_full_name()} for Period {period_num}.")
        return redirect(f"{request.path}?date={target_date}&branch={branch_id}&year={year_id}&status={status_filter}")

    audit_data = get_institutional_class_attendance_audit_data(
        branch_filter=branch_id,
        target_date=target_date,
        year_filter=year_id,
        sec_filter=section_id,
        fac_filter=faculty_id,
        status_filter=status_filter
    )

    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
    page = request.GET.get('page', 1)
    all_audit_rows = audit_data['rows']
    paginator = Paginator(all_audit_rows, 50)
    try:
        rows_page = paginator.page(page)
    except PageNotAnInteger:
        rows_page = paginator.page(1)
    except EmptyPage:
        rows_page = paginator.page(paginator.num_pages)

    sections_qs = Section.objects.all().select_related('branch', 'year').order_by('branch__code', 'year__year', 'name')
    if branch_id and branch_id.isdigit():
        sections_qs = sections_qs.filter(branch_id=int(branch_id))

    faculty_list = Faculty.objects.filter(is_active=True).select_related('user', 'department').order_by('department__code', 'user__first_name')
    if branch_id and branch_id.isdigit():
        faculty_list = faculty_list.filter(department_id=int(branch_id))

    selected_branch = Branch.objects.filter(id=int(branch_id)).first() if branch_id and branch_id.isdigit() else None

    context = {
        'branches': branches,
        'years': years,
        'sections': sections_qs,
        'faculty_list': faculty_list,
        'selected_branch': selected_branch,
        'selected_branch_id': branch_id,
        'selected_year_id': year_id,
        'selected_sec_id': section_id,
        'selected_fac_id': faculty_id,
        'selected_status': status_filter,
        'target_date': target_date,
        'target_date_str': target_date.strftime('%Y-%m-%d'),
        'day_name': target_date.strftime('%A'),
        'audit': audit_data,
        'rows': rows_page,
        'rows_page': rows_page,
        'paginator': paginator,
        'total_rows_count': len(all_audit_rows),
    }
    return render(request, 'admin_dashboard/faculty_class_audit.html', context)


@admin_required
def class_session_audit_detail(request, timetable_id, date):
    """
    Period-level session audit & student register inspection view for Administrators across all branches.
    Allows viewing who took the class, student-by-student attendance register, and making overrides.
    """
    try:
        session_date = datetime.datetime.strptime(date, '%Y-%m-%d').date()
    except ValueError:
        session_date = timezone.localdate()

    timetable = get_object_or_404(
        Timetable.objects.select_related(
            'section', 'section__branch', 'section__year', 'subject', 'faculty__user'
        ),
        id=timetable_id
    )

    transfer = ClassTransfer.objects.filter(
        timetable_entry=timetable,
        date=session_date,
        status__in=['accepted', 'completed', 'pending']
    ).select_related('substitute_faculty__user', 'original_faculty__user').first()


    effective_faculty = transfer.substitute_faculty if transfer else timetable.faculty

    diary = ClassDiary.objects.filter(
        timetable_entry=timetable,
        date=session_date
    ).first()

    # Handle Admin Manual Attendance Overrides
    if request.method == 'POST' and 'override_attendance' in request.POST:
        student_id = request.POST.get('student_id')
        new_status = request.POST.get('new_status')
        if student_id and new_status in ['P', 'A', 'L']:
            st = get_object_or_404(Student, id=student_id)
            att_rec, created = Attendance.objects.get_or_create(
                student=st,
                timetable_entry=timetable,
                date=session_date,
                defaults={'status': new_status, 'marked_by': effective_faculty}
            )
            if not created:
                att_rec.status = new_status
                att_rec.save()
            messages.success(request, f"Attendance status updated to '{new_status}' for {st.roll_number}.")
        return redirect('admin_dashboard:class_attendance_detail', timetable_id=timetable_id, date=date)

    students = Student.objects.filter(
        section=timetable.section,
        is_active=True,
        user__is_deleted=False
    ).select_related('user').order_by('roll_number')

    att_records = {
        a.student_id: a
        for a in Attendance.objects.filter(
            timetable_entry=timetable,
            date=session_date
        )
    }

    student_rows = []
    p_cnt, a_cnt, l_cnt = 0, 0, 0
    for st in students:
        rec = att_records.get(st.id)
        st_status = rec.status if rec else 'UNMARKED'
        if st_status == 'P': p_cnt += 1
        elif st_status == 'A': a_cnt += 1
        elif st_status == 'L': l_cnt += 1

        student_rows.append({
            'student': st,
            'record': rec,
            'status': st_status,
            'is_marked': rec is not None,
        })

    tot_students = len(students)
    is_conducted = len(att_records) > 0
    pct = round((p_cnt / tot_students * 100), 1) if tot_students > 0 else 0.0

    context = {
        'timetable': timetable,
        'branch': timetable.section.branch,
        'session_date': session_date,
        'session_date_str': session_date.strftime('%Y-%m-%d'),
        'day_name': session_date.strftime('%A'),
        'transfer': transfer,
        'effective_faculty': effective_faculty,
        'diary': diary,
        'student_rows': student_rows,
        'tot_students': tot_students,
        'present_count': p_cnt,
        'absent_count': a_cnt,
        'leave_count': l_cnt,
        'attendance_pct': pct,
        'is_conducted': is_conducted,
    }
    return render(request, 'admin_dashboard/class_attendance_detail.html', context)


# ─────────────────────────────────────────────
# STUDENT FEEDBACK FORMS & DOCUMENT MANAGEMENT
# ─────────────────────────────────────────────
@admin_required
def manage_feedback_forms(request):
    """Admin feedback management console listing all feedback forms."""
    from core.models import FeedbackForm, Branch
    branch_filter = request.GET.get('branch', '')
    type_filter = request.GET.get('type', '')
    status_filter = request.GET.get('status', '')

    forms_qs = FeedbackForm.objects.all().select_related('branch', 'year', 'section', 'created_by').order_by('-created_at')

    if branch_filter:
        forms_qs = forms_qs.filter(branch_id=branch_filter)
    if type_filter:
        forms_qs = forms_qs.filter(feedback_type=type_filter)
    if status_filter == 'active':
        forms_qs = forms_qs.filter(is_active=True)
    elif status_filter == 'closed':
        forms_qs = forms_qs.filter(is_active=False)

    branches = Branch.objects.all()

    return render(request, 'feedback/manage_forms.html', {
        'forms': forms_qs,
        'branches': branches,
        'selected_branch': branch_filter,
        'selected_type': type_filter,
        'selected_status': status_filter,
        'is_admin': True,
    })


@admin_required
def extract_feedback_document_api(request):
    """AJAX API endpoint for Admin to extract form questions, title, and metadata from uploaded photo or PDF."""
    from django.http import JsonResponse
    from core.document_extractor import extract_feedback_form_data, parse_questionnaire_structure
    from core.models import FeedbackForm

    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST request required.'}, status=405)

    try:
        # Case 1: Raw text provided (e.g. client-side OCR)
        raw_text = request.POST.get('raw_text', '').strip()
        if raw_text:
            data = parse_questionnaire_structure(raw_text)
            return JsonResponse(data)

        # Case 2: File uploaded directly via form data
        if 'file' in request.FILES:
            uploaded_file = request.FILES['file']
            data = extract_feedback_form_data(uploaded_file, uploaded_file.name)
            return JsonResponse(data)

        # Case 3: Extract from an existing FeedbackForm by form_id
        form_id = request.POST.get('form_id')
        if form_id:
            form_obj = get_object_or_404(FeedbackForm, id=form_id)
            if not form_obj.uploaded_document:
                return JsonResponse({'success': False, 'error': 'No document is attached to this form.'}, status=400)
            data = extract_feedback_form_data(form_obj.uploaded_document.file, form_obj.uploaded_document.name)
            return JsonResponse(data)

        return JsonResponse({'success': False, 'error': 'No file, form_id, or text provided for extraction.'}, status=400)
    except Exception as e:
        logger.exception("Error extracting feedback document")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@admin_required
def create_feedback_form(request):
    """Admin create/upload feedback form view."""
    from core.models import FeedbackForm, FeedbackQuestion, Branch, Year, Section
    from core.feedback_service import populate_preset_questions
    from core.document_extractor import extract_feedback_form_data

    branches = Branch.objects.all()
    years = Year.objects.all().order_by('year')
    sections = Section.objects.all().select_related('branch', 'year')

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        feedback_type = request.POST.get('feedback_type', 'faculty')
        branch_id = request.POST.get('branch') or None
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
                    return redirect('admin_dashboard:manage_feedback_forms')

            form_obj = FeedbackForm.objects.create(
                title=title,
                description=description,
                feedback_type=feedback_type,
                branch_id=branch_id,
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

            # 2. Populate preset if selected and no custom questions were provided
            if preset_template and not created_questions:
                populate_preset_questions(form_obj, preset_template)
                created_questions = True

            # 3. Auto-extract from uploaded document if requested and no questions were manually built
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

            messages.success(request, f"Feedback form '{form_obj.title}' created and published successfully!")
            return redirect('admin_dashboard:manage_feedback_forms')

    return render(request, 'feedback/form_editor.html', {
        'branches': branches,
        'years': years,
        'sections': sections,
        'is_admin': True,
    })


@admin_required
def edit_feedback_form(request, form_id):
    """Admin edit feedback form."""
    from core.models import FeedbackForm, FeedbackQuestion, Branch, Year, Section
    form_obj = get_object_or_404(FeedbackForm, id=form_id)

    branches = Branch.objects.all()
    years = Year.objects.all().order_by('year')
    sections = Section.objects.all().select_related('branch', 'year')
    questions = form_obj.questions.all().order_by('order', 'id')

    if request.method == 'POST':
        form_obj.title = request.POST.get('title', '').strip() or form_obj.title
        form_obj.description = request.POST.get('description', '').strip()
        form_obj.feedback_type = request.POST.get('feedback_type', form_obj.feedback_type)
        form_obj.branch_id = request.POST.get('branch') or None
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
        return redirect('admin_dashboard:manage_feedback_forms')

    return render(request, 'feedback/form_editor.html', {
        'form_obj': form_obj,
        'questions': questions,
        'branches': branches,
        'years': years,
        'sections': sections,
        'is_admin': True,
        'is_edit': True,
    })


@admin_required
def feedback_analytics(request, form_id):
    """Admin feedback analytics dashboard."""
    from core.models import FeedbackForm
    from core.feedback_service import get_form_analytics

    form_obj = get_object_or_404(FeedbackForm, id=form_id)
    analytics_data = get_form_analytics(form_obj)
    analytics_data['is_admin'] = True

    return render(request, 'feedback/analytics.html', analytics_data)


@admin_required
def export_feedback_analytics_pdf(request, form_id):
    """Admin export consolidated analytics PDF."""
    from core.models import FeedbackForm
    from core.pdf_utils import generate_feedback_analytics_pdf

    form_obj = get_object_or_404(FeedbackForm, id=form_id)
    try:
        pdf_buffer = generate_feedback_analytics_pdf(form_obj)
        filename = f"VVIT_Feedback_Analytics_{form_obj.id}.pdf"
        response = HttpResponse(pdf_buffer.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    except Exception as e:
        messages.error(request, f"Failed to generate analytics PDF: {e}")
        return redirect('admin_dashboard:feedback_analytics', form_id=form_id)


@admin_required
def download_blank_feedback_pdf(request, form_id):
    """Admin download blank printable PDF."""
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
        return redirect('admin_dashboard:manage_feedback_forms')


@admin_required
def view_student_feedback_summary(request, form_id, submission_id):
    """Admin view specific student's feedback response."""
    from core.models import FeedbackForm, FeedbackSubmission
    form_obj = get_object_or_404(FeedbackForm, id=form_id)
    submission = get_object_or_404(FeedbackSubmission, id=submission_id, form=form_obj)

    answers = submission.answers.select_related('question').order_by('question__order', 'id')

    return render(request, 'feedback/student_summary.html', {
        'form_obj': form_obj,
        'submission': submission,
        'answers': answers,
        'student': submission.student,
        'is_admin': True,
    })


@admin_required
def download_student_feedback_pdf(request, form_id, submission_id):
    """Admin download student's signed summary PDF."""
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
        return redirect('admin_dashboard:feedback_analytics', form_id=form_id)


@admin_required
def toggle_feedback_status(request, form_id):
    """Admin toggle active/closed status."""
    from core.models import FeedbackForm
    form_obj = get_object_or_404(FeedbackForm, id=form_id)
    form_obj.is_active = not form_obj.is_active
    form_obj.save()
    status_str = "Activated" if form_obj.is_active else "Closed"
    messages.success(request, f"Feedback form '{form_obj.title}' is now {status_str}.")
    return redirect('admin_dashboard:manage_feedback_forms')


@admin_required
def delete_feedback_form(request, form_id):
    """Admin delete feedback form."""
    from core.models import FeedbackForm
    form_obj = get_object_or_404(FeedbackForm, id=form_id)
    title = form_obj.title
    form_obj.delete()
    messages.success(request, f"Feedback form '{title}' deleted successfully.")
    return redirect('admin_dashboard:manage_feedback_forms')


@admin_required
def academic_calendar(request):
    """Admin view of the university academic calendar with full CRUD operations."""
    today = timezone.localdate()
    branch_id = request.GET.get('branch', '')
    event_type = request.GET.get('type', '')
    
    qs = AcademicCalendar.objects.select_related('branch', 'year').all()
    if branch_id:
        qs = qs.filter(Q(branch_id=branch_id) | Q(branch__isnull=True))
    if event_type:
        qs = qs.filter(event_type=event_type)
    
    events = list(qs.order_by('date'))
    branches = Branch.objects.all().order_by('code')
    years = Year.objects.all().order_by('year')

    return render(request, 'student/academic_calendar.html', {
        'upcoming': [e for e in events if e.date >= today],
        'past':     [e for e in events if e.date <  today],
        'today':    today,
        'branches': branches,
        'years':    years,
        'selected_branch': branch_id,
        'selected_type': event_type,
        'event_types': AcademicCalendar.EVENT_TYPE_CHOICES,
        'is_admin_manager': True,
    })


@admin_required
@require_POST
def add_academic_calendar_event(request):
    """Admin add new academic calendar event."""
    title = request.POST.get('title', '').strip()
    date_str = request.POST.get('date', '').strip()
    event_type = request.POST.get('event_type', 'other').strip()
    description = request.POST.get('description', '').strip()
    branch_id = request.POST.get('branch', '').strip()
    year_id = request.POST.get('year', '').strip()

    if not title or not date_str:
        messages.error(request, "Event Title and Date are required.")
        return redirect('admin_dashboard:academic_calendar')

    try:
        event_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        messages.error(request, "Invalid date format. Use YYYY-MM-DD.")
        return redirect('admin_dashboard:academic_calendar')

    branch = Branch.objects.filter(id=branch_id).first() if branch_id else None
    year = Year.objects.filter(id=year_id).first() if year_id else None

    AcademicCalendar.objects.create(
        title=title,
        date=event_date,
        event_type=event_type,
        description=description,
        branch=branch,
        year=year,
    )
    from django.core.cache import cache
    cache.clear()

    messages.success(request, f"Academic event '{title}' scheduled for {event_date.strftime('%d %b %Y')} successfully added!")
    return redirect('admin_dashboard:academic_calendar')


@admin_required
@require_POST
def edit_academic_calendar_event(request, event_id):
    """Admin edit existing academic calendar event."""
    event = get_object_or_404(AcademicCalendar, id=event_id)
    title = request.POST.get('title', '').strip()
    date_str = request.POST.get('date', '').strip()
    event_type = request.POST.get('event_type', 'other').strip()
    description = request.POST.get('description', '').strip()
    branch_id = request.POST.get('branch', '').strip()
    year_id = request.POST.get('year', '').strip()

    if not title or not date_str:
        messages.error(request, "Event Title and Date are required.")
        return redirect('admin_dashboard:academic_calendar')

    try:
        event.date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        messages.error(request, "Invalid date format. Use YYYY-MM-DD.")
        return redirect('admin_dashboard:academic_calendar')

    event.title = title
    event.event_type = event_type
    event.description = description
    event.branch = Branch.objects.filter(id=branch_id).first() if branch_id else None
    event.year = Year.objects.filter(id=year_id).first() if year_id else None
    event.save()

    from django.core.cache import cache
    cache.clear()

    messages.success(request, f"Academic event '{title}' updated successfully!")
    return redirect('admin_dashboard:academic_calendar')


@admin_required
@require_POST
def delete_academic_calendar_event(request, event_id):
    """Admin delete academic calendar event."""
    event = get_object_or_404(AcademicCalendar, id=event_id)
    title = event.title
    event.delete()

    from django.core.cache import cache
    cache.clear()

    messages.success(request, f"Academic event '{title}' removed from calendar.")
    return redirect('admin_dashboard:academic_calendar')













