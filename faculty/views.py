"""
VVIT Portal — Faculty Views

Handles all faculty-facing functionality:
  • Dashboard overview
  • Mark / edit attendance (radio-button UI, AJAX-assisted)
  • View attendance reports with filters
  • Export reports to Excel (openpyxl) and PDF (reportlab)
  • Counselled-students list

HOD and Lab Technician roles share the same views through the middleware
permission mapping (both resolve to faculty:* URLs).
"""

import io
import datetime
from functools import wraps

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.db.models import Count, Q
from django.conf import settings
from django.views.decorators.http import require_POST

from accounts.models import Faculty, Student, Achievement
from core.models import (
    Section, Timetable, Attendance, Subject, Result, Exam
)


# ─────────────────────────────────────────────
# HELPER DECORATOR
# ─────────────────────────────────────────────
FACULTY_ROLES = {'faculty', 'hod', 'lab_technician'}

def faculty_required(view_func):
    """Ensures the user has a faculty-like role and a Faculty profile."""
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if request.user.role not in FACULTY_ROLES:
            messages.error(request, "Access denied.")
            return redirect(request.user.get_dashboard_url())
        try:
            request.faculty = request.user.faculty_profile
        except Faculty.DoesNotExist:
            messages.error(request, "Faculty profile not found. Contact admin.")
            return redirect('accounts:login')
        return view_func(request, *args, **kwargs)
    return wrapper


# ─────────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────────
@faculty_required
def dashboard(request):
    """
    Summary dashboard:
      • Sections and subjects taught by this faculty
      • Total students across all sections
      • Today's attendance summary
    """
    faculty  = request.faculty
    today    = timezone.localdate()
    day_name = today.strftime('%A')

    # Subjects and timetable entries for this faculty
    timetable_today = (
        Timetable.objects
        .filter(faculty=faculty, day=day_name)
        .select_related('section', 'subject')
    )

    subjects = (
        Subject.objects
        .filter(faculty=faculty)
        .select_related('branch', 'year')
    )

    # Sections this faculty handles (via timetable)
    sections = (
        Timetable.objects
        .filter(faculty=faculty)
        .values_list('section', flat=True)
        .distinct()
    )
    section_count = sections.count()
    student_count = Student.objects.filter(section__in=sections, user__is_deleted=False).count()

    # Today's attendance count
    today_att = Attendance.objects.filter(
        timetable_entry__faculty=faculty, date=today
    )
    present_today = today_att.filter(status='P').count()
    absent_today  = today_att.filter(status='A').count()

    context = {
        'faculty':         faculty,
        'timetable_today': timetable_today,
        'subjects':        subjects,
        'section_count':   section_count,
        'student_count':   student_count,
        'present_today':   present_today,
        'absent_today':    absent_today,
        'today':           today,
    }
    return render(request, 'faculty/dashboard.html', context)


# ─────────────────────────────────────────────
# AJAX — Load students for a section
# ─────────────────────────────────────────────
@faculty_required
def ajax_get_students(request):
    """Return JSON list of students in a section (for attendance form)."""
    section_id = request.GET.get('section_id')
    if not section_id:
        return JsonResponse({'error': 'section_id required'}, status=400)
    students = (
        Student.objects
        .filter(section_id=section_id, is_active=True, user__is_deleted=False)
        .select_related('user')
        .order_by('roll_number')
        .only('id', 'roll_number', 'user__first_name', 'user__last_name')
    )
    data = [
        {
            'id':          s.id,
            'roll_number': s.roll_number,
            'name':        s.user.get_full_name(),
        }
        for s in students
    ]
    return JsonResponse({'students': data})


# ─────────────────────────────────────────────
# AJAX — Load timetable slots for section + day
# ─────────────────────────────────────────────
@faculty_required
def ajax_get_timetable(request):
    """Return JSON timetable slots for (section, day)."""
    section_id = request.GET.get('section_id')
    day        = request.GET.get('day')
    if not section_id or not day:
        return JsonResponse({'error': 'section_id and day required'}, status=400)

    slots = (
        Timetable.objects
        .filter(section_id=section_id, day=day)
        .select_related('subject', 'faculty__user')
        .order_by('period')
    )
    data = [
        {
            'id':           s.id,
            'period':       s.period,
            'subject_code': s.subject.code,
            'subject_name': s.subject.name,
        }
        for s in slots
    ]
    return JsonResponse({'slots': data})


# ─────────────────────────────────────────────
# MARK ATTENDANCE
# ─────────────────────────────────────────────
@faculty_required
def mark_attendance(request):
    """
    Two-phase view:
      GET  — render the filter form (section, date, timetable slot).
      POST — save attendance records.

    Edit window: faculty may only submit attendance for today or the
    previous ATTENDANCE_EDIT_WINDOW_DAYS days.  Older records raise an
    error (admins can override via admin_dashboard).
    """
    faculty    = request.faculty
    edit_window = getattr(settings, 'ATTENDANCE_EDIT_WINDOW_DAYS', 2)
    today       = timezone.localdate()
    min_date    = today - datetime.timedelta(days=edit_window - 1)

    # Sections where this faculty teaches (deduplicated)
    section_ids = (
        Timetable.objects
        .filter(faculty=faculty)
        .values_list('section_id', flat=True)
        .distinct()
    )
    sections = Section.objects.filter(id__in=section_ids).select_related('branch', 'year')

    error = None

    if request.method == 'POST':
        section_id  = request.POST.get('section')
        date_str    = request.POST.get('date')
        slot_id     = request.POST.get('slot')

        try:
            att_date = datetime.date.fromisoformat(date_str)
        except (ValueError, TypeError):
            messages.error(request, "Invalid date format.")
            return redirect('faculty:mark_attendance')

        # Enforce edit window
        if att_date < min_date or att_date > today:
            messages.error(
                request,
                f"Attendance can only be marked for {today.strftime('%d %b')} "
                f"back to {min_date.strftime('%d %b %Y')}."
            )
            return redirect('faculty:mark_attendance')

        slot = get_object_or_404(Timetable, id=slot_id)
        students_in_section = Student.objects.filter(section_id=section_id, is_active=True, user__is_deleted=False)

        saved_count = 0
        for student in students_in_section:
            field_name = f"attendance_{student.id}"
            status     = request.POST.get(field_name, 'A')
            if status not in ('P', 'A'):
                status = 'A'
            Attendance.objects.update_or_create(
                student=student,
                timetable_entry=slot,
                date=att_date,
                defaults={'status': status, 'marked_by': faculty},
            )
            saved_count += 1

        messages.success(request, f"Attendance saved for {saved_count} students.")
        return redirect('faculty:mark_attendance')

    context = {
        'sections':    sections,
        'today':       today.isoformat(),
        'min_date':    min_date.isoformat(),
        'faculty':     faculty,
    }
    return render(request, 'faculty/mark_attendance.html', context)


# ─────────────────────────────────────────────
# ATTENDANCE REPORTS
# ─────────────────────────────────────────────
@faculty_required
def reports(request):
    """
    Display attendance report filtered by section, subject, and date range.
    Shows student-wise totals and percentages in a table.
    """
    faculty  = request.faculty
    today    = timezone.localdate()

    section_ids = (
        Timetable.objects
        .filter(faculty=faculty)
        .values_list('section_id', flat=True)
        .distinct()
    )
    sections = Section.objects.filter(id__in=section_ids).select_related('branch', 'year')
    subjects = Subject.objects.filter(faculty=faculty, is_deleted=False).select_related('branch', 'year')

    # Read filter params
    section_id = request.GET.get('section')
    subject_id = request.GET.get('subject')
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
            .select_related('student__user', 'timetable_entry__subject')
        )
        if subject_id:
            att_qs = att_qs.filter(timetable_entry__subject_id=subject_id)

        # Aggregate per student
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
            d['low']    = d['pct'] < getattr(settings, 'LOW_ATTENDANCE_THRESHOLD', 75)
            report_data.append(d)

        report_data.sort(key=lambda x: x['roll'])

    context = {
        'sections':    sections,
        'subjects':    subjects,
        'report_data': report_data,
        'section_id':  section_id,
        'subject_id':  subject_id,
        'date_from':   date_from,
        'date_to':     date_to,
        'threshold':   getattr(settings, 'LOW_ATTENDANCE_THRESHOLD', 75),
    }
    return render(request, 'faculty/reports.html', context)


# ─────────────────────────────────────────────
# EXPORT — EXCEL
# ─────────────────────────────────────────────
@faculty_required
def export_excel(request):
    """Export the current attendance report as an .xlsx file."""
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment
    except ImportError:
        messages.error(request, "openpyxl is not installed. Cannot export Excel.")
        return redirect('faculty:reports')

    faculty    = request.faculty
    section_id = request.GET.get('section')
    subject_id = request.GET.get('subject')
    date_from  = request.GET.get('date_from')
    date_to    = request.GET.get('date_to')
    today      = timezone.localdate()

    att_qs = (
        Attendance.objects
        .filter(
            timetable_entry__section_id=section_id or None,
            date__gte=date_from or (today - datetime.timedelta(days=30)).isoformat(),
            date__lte=date_to   or today.isoformat(),
        )
        .select_related('student__user', 'timetable_entry__subject')
    )
    if subject_id:
        att_qs = att_qs.filter(timetable_entry__subject_id=subject_id)

    # Aggregate
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

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Attendance Report'

    # Styles
    header_font = Font(bold=True, color='FFFFFF')
    header_fill = PatternFill('solid', fgColor='CC0000')
    center      = Alignment(horizontal='center')

    headers = ['S.No', 'Roll Number', 'Student Name', 'Total Classes', 'Present', 'Absent', 'Percentage']
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.font  = header_font
        cell.fill  = header_fill
        cell.alignment = center

    for row_idx, (_, d) in enumerate(student_map.items(), 2):
        t   = d['total']
        p   = d['present']
        pct = round(p / t * 100, 1) if t else 0
        ws.append([row_idx - 1, d['roll'], d['name'], t, p, t - p, pct])

    ws.column_dimensions['C'].width = 30

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    response = HttpResponse(
        buf.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="attendance_report.xlsx"'
    return response


# ─────────────────────────────────────────────
# EXPORT — PDF
# ─────────────────────────────────────────────
@faculty_required
def export_pdf(request):
    """Export attendance report as a PDF using reportlab."""
    try:
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib         import colors
        from reportlab.platypus    import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles  import getSampleStyleSheet
    except ImportError:
        messages.error(request, "reportlab is not installed. Cannot export PDF.")
        return redirect('faculty:reports')

    faculty    = request.faculty
    section_id = request.GET.get('section')
    subject_id = request.GET.get('subject')
    date_from  = request.GET.get('date_from')
    date_to    = request.GET.get('date_to')
    today      = timezone.localdate()

    att_qs = (
        Attendance.objects
        .filter(
            timetable_entry__section_id=section_id or None,
            date__gte=date_from or (today - datetime.timedelta(days=30)).isoformat(),
            date__lte=date_to   or today.isoformat(),
        )
        .select_related('student__user', 'timetable_entry__subject')
    )
    if subject_id:
        att_qs = att_qs.filter(timetable_entry__subject_id=subject_id)

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

    buf    = io.BytesIO()
    doc    = SimpleDocTemplate(buf, pagesize=landscape(A4))
    styles = getSampleStyleSheet()
    elems  = []

    # Title
    elems.append(Paragraph("VVIT — Attendance Report", styles['Title']))
    elems.append(Paragraph(f"Generated: {today.strftime('%d %B %Y')}", styles['Normal']))
    elems.append(Spacer(1, 12))

    # Table
    table_data = [['S.No', 'Roll Number', 'Student Name', 'Total', 'Present', 'Absent', 'Percentage']]
    for i, (_, d) in enumerate(student_map.items(), 1):
        t   = d['total']
        p   = d['present']
        pct = f"{round(p / t * 100, 1) if t else 0}%"
        table_data.append([i, d['roll'], d['name'], t, p, t - p, pct])

    tbl = Table(table_data, colWidths=[40, 90, 180, 60, 60, 60, 70])
    tbl.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#CC0000')),
        ('TEXTCOLOR',  (0,0), (-1,0), colors.white),
        ('FONTNAME',   (0,0), (-1,0), 'Helvetica-Bold'),
        ('GRID',       (0,0), (-1,-1), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#FFF0F0')]),
        ('ALIGN',      (0,0), (-1,-1), 'CENTER'),
        ('ALIGN',      (2,0), (2,-1), 'LEFT'),
    ]))
    elems.append(tbl)
    doc.build(elems)

    buf.seek(0)
    response = HttpResponse(buf.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="attendance_report.pdf"'
    return response


# ─────────────────────────────────────────────
# COUNSELLED & ASSIGNED STUDENTS
# ─────────────────────────────────────────────
@faculty_required
def counselled_students(request):
    """
    List all students associated with this faculty member:
      1. Counselled students (designated counsellor)
      2. Class students (designated class teacher)
      3. Subject students (students in sections taught by this faculty)
    """
    faculty = request.faculty
    
    # 1. Counselled Students
    counselled_list = (
        Student.objects
        .filter(counsellor=faculty, is_active=True, user__is_deleted=False)
        .select_related('user', 'branch', 'year', 'section')
        .order_by('roll_number')
    )
    
    # 2. Class Students
    class_list = (
        Student.objects
        .filter(class_teacher=faculty, is_active=True, user__is_deleted=False)
        .select_related('user', 'branch', 'year', 'section')
        .order_by('roll_number')
    )
    
    # 3. Subject Students (students in sections handled by this faculty)
    timetable_slots = Timetable.objects.filter(faculty=faculty).select_related('section', 'subject')
    section_ids = list(timetable_slots.values_list('section_id', flat=True).distinct())
    
    # Mapping of section ID to subjects taught
    section_subjects = {}
    for slot in timetable_slots:
        if slot.section_id not in section_subjects:
            section_subjects[slot.section_id] = []
        if slot.subject.code not in section_subjects[slot.section_id]:
            section_subjects[slot.section_id].append(slot.subject.code)
            
    subject_list = (
        Student.objects
        .filter(section_id__in=section_ids, is_active=True, user__is_deleted=False)
        .select_related('user', 'branch', 'year', 'section')
        .order_by('section__name', 'roll_number')
    )
    
    # Attach subject codes to each subject student for rendering
    for student in subject_list:
        student.subjects_taught = ", ".join(section_subjects.get(student.section_id, []))

    context = {
        'faculty': faculty,
        'counselled_students': counselled_list,
        'class_students': class_list,
        'subject_students': subject_list,
    }
    return render(request, 'faculty/counselled_students.html', context)


# ─────────────────────────────────────────────
# STUDENT RESULTS
# ─────────────────────────────────────────────
@faculty_required
def student_results(request):
    """
    View for class teachers and counsellors to see their assigned students' exam results.
    """
    faculty = request.faculty
    
    # Get students where faculty is class_teacher or counsellor (HOD sees all students in branch)
    if request.user.role == 'hod':
        students = Student.objects.filter(
            branch=faculty.department,
            is_active=True,
            user__is_deleted=False
        ).select_related('user')
    else:
        students = Student.objects.filter(
            Q(class_teacher=faculty) | Q(counsellor=faculty),
            is_active=True,
            user__is_deleted=False
        ).select_related('user')
    
    selected_student_id = request.GET.get('student', '')
    selected_exam_id = request.GET.get('exam', '')
    
    selected_student = None
    selected_exam_obj = None
    results_list = []
    sgpa = 0.0
    pass_status = "Pass"
    revaluation_date = None
    
    # List of all exams for branch/year combination of these students
    branch_ids = students.values_list('branch_id', flat=True).distinct()
    year_ids = students.values_list('year_id', flat=True).distinct()
    exams = Exam.objects.filter(branch_id__in=branch_ids, year_id__in=year_ids).order_by('-date')
    
    if selected_student_id and selected_exam_id:
        try:
            selected_student = students.get(id=selected_student_id)
            selected_exam_obj = Exam.objects.get(id=selected_exam_id)
            
            results_qs = Result.objects.filter(
                student=selected_student,
                exam_id=selected_exam_id,
                exam__release__released=True
            ).select_related('subject').order_by('subject__name')
            
            results_list = list(results_qs)
            
            # Calculate SGPA and Pass/Fail status dynamically according to R23 regulation
            grade_points = {
                'S': 10, 'A': 9, 'B': 8, 'C': 7, 'D': 6, 'E': 5,
                'F': 0, 'Ab': 0
            }
            total_points = 0
            total_credits = 0
            has_fail = False
            
            for r in results_list:
                g = r.grade
                if g in ['CP', 'NCP']:
                    if g == 'NCP':
                        has_fail = True
                    continue
                if g in ['F', 'Ab'] or not g:
                    has_fail = True
                
                credits = r.subject.credits if r.subject else 3
                points = grade_points.get(g, 0)
                total_points += points * credits
                total_credits += credits
                
            sgpa = round(total_points / total_credits, 2) if total_credits > 0 else 0.0
            pass_status = "Fail" if has_fail else "Pass"
            
            if selected_exam_obj.date:
                revaluation_date = selected_exam_obj.date + datetime.timedelta(days=40)
            else:
                revaluation_date = timezone.localdate() + datetime.timedelta(days=30)
                
        except (Student.DoesNotExist, Exam.DoesNotExist):
            pass
            
    # Default view list
    results = Result.objects.filter(
        student__in=students,
        exam__release__released=True
    ).select_related('student__user', 'exam', 'subject').order_by('student__roll_number', '-exam__date')
    
    if selected_student_id:
        results = results.filter(student_id=selected_student_id)
    if selected_exam_id:
        results = results.filter(exam_id=selected_exam_id)
        
    context = {
        'faculty':             faculty,
        'students':            students,
        'exams':               exams,
        'selected_student':    selected_student,
        'selected_exam_obj':   selected_exam_obj,
        'selected_student_id': selected_student_id,
        'selected_exam_id':    selected_exam_id,
        'results_list':        results_list,
        'sgpa':                sgpa,
        'pass_status':         pass_status,
        'revaluation_date':    revaluation_date,
        'results':             results,
    }
    return render(request, 'faculty/student_results.html', context)


# ─────────────────────────────────────────────
# FACULTY UPLOAD MARKS
# ─────────────────────────────────────────────
@faculty_required
def upload_marks(request):
    """
    Allows faculty to input or upload marks for a specific subject, exam, and section (class).
    """
    import csv
    import io
    from django.db import transaction
    
    faculty = request.faculty
    years = Year.objects.all()
    year_id = request.GET.get('year') or request.POST.get('year')

    if request.user.role == 'hod':
        subjects = Subject.objects.filter(branch=faculty.department, is_deleted=False).select_related('branch', 'year')
    else:
        subjects = Subject.objects.filter(faculty=faculty, is_deleted=False).select_related('branch', 'year')

    selected_subject_id = request.GET.get('subject', '')
    selected_exam_id = request.GET.get('exam', '')
    selected_section_id = request.GET.get('section', '')

    # Validate parameters based on selected year
    if year_id:
        if selected_subject_id and not subjects.filter(id=selected_subject_id, year_id=year_id).exists():
            selected_subject_id = ''
        if selected_exam_id and not Exam.objects.filter(id=selected_exam_id, year_id=year_id).exists():
            selected_exam_id = ''
        if selected_section_id and not Section.objects.filter(id=selected_section_id, year_id=year_id).exists():
            selected_section_id = ''
    else:
        selected_subject_id = ''
        selected_exam_id = ''
        selected_section_id = ''

    # Apply year filtering
    if year_id:
        subjects = subjects.filter(year_id=year_id)
        branch_ids = subjects.values_list('branch_id', flat=True).distinct()
        exams = Exam.objects.filter(branch_id__in=branch_ids, year_id=year_id).exclude(exam_type='final').order_by('-date')
    else:
        subjects = Subject.objects.none()
        exams = Exam.objects.none()

    selected_subject = None
    selected_exam = None
    selected_section = None
    sections = []
    students = []
    current_results = {}
    
    if selected_subject_id:
        if request.user.role == 'hod':
            selected_subject = get_object_or_404(Subject, id=selected_subject_id, branch=faculty.department)
            sections = Section.objects.filter(branch=faculty.department, year=selected_subject.year).distinct()
        else:
            selected_subject = get_object_or_404(Subject, id=selected_subject_id, faculty=faculty)
            sections = Section.objects.filter(timetable_entries__subject=selected_subject).distinct()
        
    if selected_exam_id:
        selected_exam = get_object_or_404(Exam, id=selected_exam_id)
        if selected_exam.exam_type == 'final':
            messages.error(request, "Only the Administrator is authorized to upload Semester Final exam results.")
            return redirect('faculty:upload_marks')
        
    if selected_section_id and selected_subject and selected_exam:
        if request.user.role == 'hod':
            selected_section = get_object_or_404(Section, id=selected_section_id, branch=faculty.department)
        else:
            selected_section = get_object_or_404(Section, id=selected_section_id)
        students = Student.objects.filter(section=selected_section, is_active=True, user__is_deleted=False).select_related('user').order_by('roll_number')
        
        # Load existing results for these students, exam, and subject
        results_qs = Result.objects.filter(
            student__in=students,
            exam=selected_exam,
            subject=selected_subject
        )
        current_results = {r.student_id: r for r in results_qs}
        
    if request.method == 'POST':
        subj_id = request.POST.get('subject')
        ex_id = request.POST.get('exam')
        sec_id = request.POST.get('section')
        
        # Resolve objects
        if request.user.role == 'hod':
            subj = get_object_or_404(Subject, id=subj_id, branch=faculty.department)
            sec = get_object_or_404(Section, id=sec_id, branch=faculty.department)
        else:
            subj = get_object_or_404(Subject, id=subj_id, faculty=faculty)
            sec = get_object_or_404(Section, id=sec_id)
            
        ex = get_object_or_404(Exam, id=ex_id)
        if ex.exam_type == 'final':
            messages.error(request, "Only the Administrator is authorized to upload Semester Final exam results.")
            return redirect(f"{request.path}?subject={subj_id}&exam={ex_id}&section={sec_id}")
            
        sec_students = Student.objects.filter(section=sec, is_active=True, user__is_deleted=False)
        
        # Check action type: CSV upload or Manual entry
        action = request.POST.get('action')
        
        if action == 'csv':
            if 'csv_file' not in request.FILES:
                messages.error(request, "Please upload a CSV file.")
                return redirect(f"{request.path}?subject={subj_id}&exam={ex_id}&section={sec_id}")
                
            csv_file = request.FILES['csv_file']
            if not csv_file.name.endswith('.csv'):
                messages.error(request, "Please upload a valid .csv file.")
                return redirect(f"{request.path}?subject={subj_id}&exam={ex_id}&section={sec_id}")
                
            try:
                data_set = csv_file.read().decode('utf-8-sig')
                io_string = io.StringIO(data_set)
                next(io_string, None) # skip header
                
                reader = csv.reader(io_string, delimiter=',', quotechar='"')
                success_count = 0
                errors = []
                
                with transaction.atomic():
                    for row_idx, row in enumerate(reader, start=2):
                        if not row or not row[0].strip():
                            continue
                        if len(row) < 2:
                            errors.append(f"Row {row_idx}: Missing columns.")
                            continue
                            
                        roll = row[0].strip().upper()
                        marks_str = row[1].strip()
                        max_str = row[2].strip() if len(row) > 2 and row[2].strip() else '100'
                        
                        try:
                            marks_obt = float(marks_str)
                            max_mks = float(max_str)
                        except ValueError:
                            errors.append(f"Row {row_idx}: Invalid marks format for {roll}.")
                            continue
                            
                        try:
                            # Verify student exists and belongs to the selected section
                            student = sec_students.get(roll_number=roll)
                            
                            Result.objects.update_or_create(
                                student=student,
                                exam=ex,
                                subject=subj,
                                defaults={
                                    'marks_obtained': marks_obt,
                                    'max_marks': max_mks,
                                    'grade': ''  # cleared so save() will auto-recompute
                                }
                            )
                            success_count += 1
                        except Student.DoesNotExist:
                            errors.append(f"Row {row_idx}: Student {roll} not found in section {sec}.")
                            
                if errors:
                    for err in errors[:5]:
                        messages.error(request, err)
                    if len(errors) > 5:
                        messages.error(request, f"...and {len(errors) - 5} more errors.")
                if success_count > 0:
                    messages.success(request, f"Successfully uploaded marks for {success_count} students in {sec}.")
                    
            except Exception as e:
                messages.error(request, f"Error uploading CSV: {e}")
                
        elif action == 'manual':
            try:
                success_count = 0
                max_marks_default = float(request.POST.get('max_marks_default', '100'))
                
                with transaction.atomic():
                    for stu in sec_students:
                        marks_input = request.POST.get(f"marks_{stu.id}", '').strip()
                        if marks_input == '':
                            continue
                            
                        try:
                            marks_obt = float(marks_input)
                        except ValueError:
                            messages.error(request, f"Invalid marks for student {stu.roll_number}.")
                            return redirect(f"{request.path}?subject={subj_id}&exam={ex_id}&section={sec_id}")
                            
                        Result.objects.update_or_create(
                            student=stu,
                            exam=ex,
                            subject=subj,
                            defaults={
                                'marks_obtained': marks_obt,
                                'max_marks': max_marks_default,
                                'grade': ''  # cleared so save() will auto-recompute
                            }
                        )
                        success_count += 1
                        
                messages.success(request, f"Successfully saved marks for {success_count} students in {sec}.")
            except Exception as e:
                messages.error(request, f"Error saving marks: {e}")
                
        if success_count > 0 and request.user.role == 'hod':
            try:
                from core.models import Notification
                Notification.objects.create(
                    title="HOD Marks Uploaded",
                    message=f"HOD {request.user.get_full_name() or request.user.username} uploaded marks for {subj.code} in section {sec.name} for exam {ex.name}.",
                    notif_type=Notification.TYPE_SYSTEM,
                    priority=Notification.PRIORITY_HIGH,
                    target_all=False,
                    target_role='admin',
                    created_by=request.user
                )
            except Exception:
                pass

        return redirect(f"{request.path}?year={year_id}&subject={subj_id}&exam={ex_id}&section={sec_id}")
        
    context = {
        'years':               years,
        'year_id':             year_id,
        'subjects':            subjects,
        'exams':               exams,
        'selected_subject_id': selected_subject_id,
        'selected_exam_id':    selected_exam_id,
        'selected_section_id': selected_section_id,
        'selected_subject':    selected_subject,
        'selected_exam':       selected_exam,
        'selected_section':    selected_section,
        'sections':            sections,
        'students':            students,
        'current_results':     current_results,
    }
    return render(request, 'faculty/upload_marks.html', context)


@faculty_required
def add_achievement(request):
    faculty = request.faculty
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        category = request.POST.get('category', '').strip()
        date_str = request.POST.get('date_achieved', '').strip()

        if not (title and description and category and date_str):
            messages.error(request, "All fields are required.")
        else:
            try:
                date_achieved = datetime.date.fromisoformat(date_str)
                Achievement.objects.create(
                    user=request.user,
                    title=title,
                    description=description,
                    category=category,
                    date_achieved=date_achieved
                )
                messages.success(request, "Achievement submitted successfully. Pending HOD verification.")
                return redirect('faculty:add_achievement')
            except ValueError:
                messages.error(request, "Invalid date format.")
            except Exception as e:
                messages.error(request, f"Error saving achievement: {e}")

    achievements = Achievement.objects.filter(user=request.user).order_by('-date_achieved')
    return render(request, 'faculty/add_achievement.html', {
        'faculty': faculty,
        'achievements': achievements,
    })


