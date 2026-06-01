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
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Count
from django.core.paginator import Paginator

from accounts.models import User, Student, Faculty
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
        'total_students': Student.objects.filter(is_active=True).count(),
        'total_faculty':  Faculty.objects.filter(is_active=True).count(),
        'total_subjects': Subject.objects.count(),
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
        .select_related('user', 'branch', 'year', 'section')
        .order_by('roll_number')
    )
    search = request.GET.get('q', '')
    if search:
        qs = qs.filter(
            roll_number__icontains=search
        ) | qs.filter(
            user__first_name__icontains=search
        ) | qs.filter(
            user__last_name__icontains=search
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

        user = User.objects.create_user(
            username   = username,
            password   = p.get('password', 'vvit@1234'),
            first_name = p.get('first_name', ''),
            last_name  = p.get('last_name',  ''),
            email      = f"{username}@vvit.net",
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
        u = student.user
        u.first_name = p.get('first_name', u.first_name)
        u.last_name  = p.get('last_name',  u.last_name)
        u.phone      = p.get('phone',      u.phone)
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
        student.user.delete()   # cascades to Student
        messages.success(request, "Student deleted.")
    return redirect('admin_dashboard:manage_students')


# ═══════════════════════════════════════════════
# FACULTY MANAGEMENT
# ═══════════════════════════════════════════════
@admin_required
def manage_faculty(request):
    qs = Faculty.objects.select_related('user', 'department').filter(is_active=True).order_by('employee_id')
    return render(request, 'admin_dashboard/manage_faculty.html', {'faculties': qs})


@admin_required
def add_faculty(request):
    branches = Branch.objects.all()
    if request.method == 'POST':
        p   = request.POST
        emp = p.get('employee_id', '').strip()
        if User.objects.filter(username=emp).exists():
            messages.error(request, f"Employee ID '{emp}' already exists.")
            return redirect('admin_dashboard:add_faculty')

        user = User.objects.create_user(
            username   = emp,
            password   = p.get('password', 'vvit@1234'),
            first_name = p.get('first_name', ''),
            last_name  = p.get('last_name', ''),
            email      = f"{emp}@vvit.net",
            role       = p.get('role', 'faculty'),
            phone      = p.get('phone', ''),
        )
        Faculty.objects.create(
            user        = user,
            employee_id = emp,
            department_id = p.get('department'),
            designation = p.get('designation', ''),
        )
        messages.success(request, f"Faculty {emp} created.")
        return redirect('admin_dashboard:manage_faculty')

    return render(request, 'admin_dashboard/add_faculty.html', {'branches': branches})


@admin_required
def delete_faculty(request, pk):
    fac = get_object_or_404(Faculty, pk=pk)
    if request.method == 'POST':
        fac.user.delete()
        messages.success(request, "Faculty deleted.")
    return redirect('admin_dashboard:manage_faculty')


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
        Timetable.objects.update_or_create(
            section_id = p.get('section'),
            day        = p.get('day'),
            period     = p.get('period'),
            defaults   = {
                'subject_id': p.get('subject'),
                'faculty_id': p.get('faculty'),
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


# ═══════════════════════════════════════════════
# RESULT RELEASE
# ═══════════════════════════════════════════════
from django.core.mail import send_mail
from django.utils import timezone as tz
from django.conf import settings as django_settings


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
            release_obj.released_at = tz.now()
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
http://127.0.0.1:8000/student/results/

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
    exams    = Exam.objects.select_related('branch', 'year').order_by('-date')
    subjects = Subject.objects.select_related('branch', 'year').all()
    sections = Section.objects.select_related('branch', 'year').all()

    exam_id    = request.GET.get('exam') or request.POST.get('exam')
    subject_id = request.GET.get('subject') or request.POST.get('subject')
    section_id = request.GET.get('section') or request.POST.get('section')

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
        return redirect(f"{request.path}?exam={exam_id}&subject={subject_id}&section={section_id}")

    context = {
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
    
    exams = Exam.objects.select_related('branch', 'year').order_by('-date')
    subjects = Subject.objects.select_related('branch', 'year').all()
    
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
            
        return redirect('admin_dashboard:bulk_upload_results')

    context = {
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
                        
                    user = User.objects.create_user(
                        username=roll_number,
                        password='password123',
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

