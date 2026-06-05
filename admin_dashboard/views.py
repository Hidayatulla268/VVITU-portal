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
from functools import wraps

from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Count, Q
from django.core.paginator import Paginator
from django.core.mail import send_mail
from django.conf import settings as django_settings

from accounts.models import User, Student, Faculty, DEOProfile
from core.models import (
    Branch, Year, Section, Subject, Timetable,
    Attendance, Exam, Result, AcademicCalendar, QuestionPaper, ResultRelease
)


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
    """High-level statistics card view for the admin home page."""
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

    context = {
        'stats':       stats,
        'branch_data': json.dumps(branch_data),
    }
    return render(request, 'admin_dashboard/dashboard.html', context)


# ═══════════════════════════════════════════════
# STUDENT MANAGEMENT
# ═══════════════════════════════════════════════
@admin_required
def manage_students(request):
    qs = (
        Student.objects
        .filter(user__is_deleted=False)
        .select_related('user', 'branch', 'year', 'section')
        .order_by('roll_number')
    )
    search = request.GET.get('q', '')
    if search:
        from django.db.models import Q
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
    page      = paginator.get_page(request.GET.get('page', 1))
    return render(request, 'admin_dashboard/manage_students.html', {'page': page, 'search': search})


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

        user = User.objects.create_user(
            username   = username,
            password   = p.get('password', 'vvit@1234'),
            first_name = first_name,
            last_name  = last_name,
            email      = email,
            role       = 'student',
            phone      = p.get('phone', ''),
        )
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
            parent_mobile = p.get('parent_mobile', '').strip() or None,
        )
        messages.success(request, f"Student {username} created successfully.")
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
        u.save()

        student.branch_id    = p.get('branch',        student.branch_id)
        student.year_id      = p.get('year',          student.year_id)
        student.section_id   = p.get('section',       student.section_id)
        student.class_teacher_id = p.get('class_teacher') or None
        student.counsellor_id    = p.get('counsellor')    or None
        student.parent_name  = p.get('parent_name', '').strip() or None
        student.parent_mobile = p.get('parent_mobile', '').strip() or None
        student.save()
        messages.success(request, "Student updated.")
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
        user = User.objects.create_user(
            username   = emp,
            password   = p.get('password', 'vvit@1234'),
            first_name = first_name,
            last_name  = last_name,
            email      = email,
            role       = role,
            phone      = p.get('phone', ''),
        )
        Faculty.objects.create(
            user        = user,
            employee_id = emp,
            department_id = p.get('department') or None,
            designation = p.get('designation', '') or ('Data Entry Operator' if role == 'deo' else 'Associate Professor'),
        )
        if role == 'deo':
            DEOProfile.objects.create(
                user        = user,
                employee_id = emp,
                branch_id   = p.get('department') or None,
            )
        messages.success(request, f"Faculty/Staff {emp} created.")
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
    """Edit an existing faculty member's name, phone, department, and designation."""
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
        u.save()

        fac.department_id = p.get('department') or fac.department_id
        fac.designation   = p.get('designation', fac.designation)
        
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
        messages.success(request, f"Faculty/Staff {fac.employee_id} updated.")
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
# TIMETABLE
# ═══════════════════════════════════════════════
@admin_required
def manage_timetable(request):
    sections  = Section.objects.select_related('branch', 'year').all()
    subjects  = Subject.objects.select_related('branch', 'year').all()
    faculties = Faculty.objects.select_related('user').filter(is_active=True)

    if request.method == 'POST':
        p = request.POST
        start_time = p.get('start_time') or None
        end_time   = p.get('end_time') or None
        Timetable.objects.update_or_create(
            section_id = p.get('section'),
            day        = p.get('day'),
            period     = p.get('period'),
            defaults   = {
                'subject_id': p.get('subject'),
                'faculty_id': p.get('faculty'),
                'start_time': start_time,
                'end_time':   end_time,
            }
        )
        messages.success(request, "Timetable entry saved.")
        return redirect('admin_dashboard:manage_timetable')

    entries = Timetable.objects.select_related('section__branch','section__year','subject','faculty__user').order_by('section','day','period')
    day_choices = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday']
    context = {
        'sections':    sections,
        'subjects':    subjects,
        'faculties':   faculties,
        'entries':     entries,
        'day_choices': day_choices,
        'periods':     range(1, 9),
    }
    return render(request, 'admin_dashboard/manage_timetable.html', context)


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

            # Send emails if not already sent
            if not release_obj.email_sent:
                sent, failed = _send_result_emails(exam, request)
                release_obj.email_sent = True
                release_obj.save()
                messages.success(
                    request,
                    f"Results released for '{exam.name}'. "
                    f"Emails sent: {sent}, Failed: {failed}."
                )
            else:
                messages.success(request, f"Results released for '{exam.name}'.")

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

    for sid, data in student_results.items():
        student = data['student']
        email   = student.user.email

        if not email:
            failed += 1
            continue

        # Build result table as plain text
        lines = []
        total_marks = 0
        total_max   = 0
        for r in data['results']:
            lines.append(
                f"  {r.subject.code:<8} {r.subject.name:<35} "
                f"{r.marks_obtained:>6}/{r.max_marks:<6}  Grade: {r.grade}"
            )
            total_marks += float(r.marks_obtained)
            total_max   += float(r.max_marks)

        overall_pct = round(total_marks / total_max * 100, 1) if total_max else 0

        subject_line = f"[VVIT] Results Released — {exam.name}"

        body = f"""Dear {student.user.get_full_name()},

Your results for {exam.name} have been released.

Roll Number : {student.roll_number}
Exam        : {exam.name}
Branch      : {student.branch.code if student.branch else 'N/A'}
Year        : {student.year} | Semester : {exam.semester}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SUBJECT RESULTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{chr(10).join(lines)}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Overall Percentage : {overall_pct}%
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

You can also view your detailed results by logging into the VVIT Portal:
{django_settings.COLLEGE_WEBSITE}/student/results/

For any queries, contact your class teacher or the examination cell.

Regards,
Examination Cell
{django_settings.COLLEGE_NAME}
{django_settings.COLLEGE_LOCATION}
"""

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
                            'max_marks': max_mks
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
            
            # Read first line to check if it's a header
            header = next(io_string, None)
            
            success_count = 0
            errors = []
            
            reader = csv.reader(io_string, delimiter=',', quotechar='"')
            for row_idx, row in enumerate(reader, start=2):
                if not row or not row[0].strip():
                    continue  # Skip empty rows
                    
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
                            'max_marks': max_mks
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
            
            header = next(io_string, None)
            
            success_count = 0
            errors = []
            
            reader = csv.reader(io_string, delimiter=',', quotechar='"')
            
            with transaction.atomic():
                for row_idx, row in enumerate(reader, start=2):
                    if not row or not row[0].strip():
                        continue
                        
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
                        
                    user = User.objects.create_user(
                        username=roll_number,
                        password='vvit@1234',
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
                    
            if errors:
                for err in errors[:5]:
                    messages.error(request, err)
                if len(errors) > 5:
                    messages.error(request, f"...and {len(errors) - 5} more errors. Database transaction rolled back.")
                raise Exception("Upload failed due to data errors.")
            else:
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

    timestamp = timezone.now().strftime('%Y%md_%H%M%S')
    filename = f"db_backup_{timestamp}.json"
    filepath = os.path.join(backups_dir, filename)

    try:
        # Dump data excluding contenttypes and permissions
        out = io.StringIO()
        call_command('dumpdata', exclude=['contenttypes', 'auth.Permission'], stdout=out)
        
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
            except Exception:
                pass

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




