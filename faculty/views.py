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

from accounts.models import Faculty, Student
from core.models import (
    Section, Timetable, Attendance, Subject
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
    student_count = Student.objects.filter(section__in=sections).count()

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
        .filter(section_id=section_id, is_active=True)
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
        students_in_section = Student.objects.filter(section_id=section_id, is_active=True)

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
    subjects = Subject.objects.filter(faculty=faculty).select_related('branch', 'year')

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
            d['low']    = d['pct'] < settings.LOW_ATTENDANCE_THRESHOLD
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
        'threshold':   settings.LOW_ATTENDANCE_THRESHOLD,
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
# COUNSELLED STUDENTS
# ─────────────────────────────────────────────
@faculty_required
def counselled_students(request):
    """
    List all students for whom this faculty member is the designated counsellor.
    Shows roll number, name, branch, year, section, and phone.
    """
    faculty  = request.faculty
    students = (
        Student.objects
        .filter(counsellor=faculty, is_active=True)
        .select_related('user', 'branch', 'year', 'section')
        .order_by('roll_number')
    )

    context = {
        'faculty':  faculty,
        'students': students,
    }
    return render(request, 'faculty/counselled_students.html', context)
