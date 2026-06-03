"""
VVIT Portal — Student Views

All views protected by the student_required decorator.
Querysets use select_related / prefetch_related throughout to stay
efficient at 300,000+ student scale.  The academic_calendar view uses
Django's cache framework (5-minute TTL) so simultaneous page loads
hit the DB only once per branch/year combination.
"""

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.core.cache import cache
from django.utils import timezone
from django.db.models import Q
from django.contrib import messages

from accounts.models import Student, Achievement
from core.models import (
    Timetable, Attendance, Result, Exam,
    AcademicCalendar, QuestionPaper, Subject,
)

import datetime
from functools import wraps


# ── Decorator ────────────────────────────────────────────────────────────────

def student_required(view_func):
    """Ensures the visitor is an authenticated student with a valid profile."""
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if request.user.role != 'student':
            messages.error(request, "This page is for students only.")
            return redirect(request.user.get_dashboard_url())
        try:
            request.student = request.user.student_profile
        except Student.DoesNotExist:
            messages.error(request, "Student profile not found — please contact admin.")
            return redirect('accounts:login')
        return view_func(request, *args, **kwargs)
    return wrapper


# ── Helpers ───────────────────────────────────────────────────────────────────

def _attendance_stats(student):
    """Return a per-subject list of {code, name, total, present, percentage}."""
    records = (
        Attendance.objects
        .filter(student=student)
        .select_related('timetable_entry__subject')
    )
    stats = {}
    for rec in records:
        subj = rec.timetable_entry.subject
        key  = subj.code
        if key not in stats:
            stats[key] = {'name': subj.name, 'code': key, 'total': 0, 'present': 0}
        stats[key]['total'] += 1
        if rec.status == 'P':
            stats[key]['present'] += 1
    for s in stats.values():
        t = s['total']
        s['percentage'] = round(s['present'] / t * 100, 1) if t else 0
    return list(stats.values())


def _overall_attendance(stats):
    total   = sum(s['total']   for s in stats)
    present = sum(s['present'] for s in stats)
    return round(present / total * 100, 1) if total else 0


def _predict_attendance(student):
    """
    Linear regression prediction of semester-end attendance.
    Returns None gracefully if scikit-learn is absent or data is sparse.
    """
    try:
        import numpy as np
        from sklearn.linear_model import LinearRegression
    except ImportError:
        return None

    today  = timezone.localdate()
    start  = today - datetime.timedelta(days=60)
    rows   = list(
        Attendance.objects
        .filter(student=student, date__gte=start)
        .order_by('date')
        .values('date', 'status')
    )
    if len(rows) < 5:
        return None

    dates = sorted(set(r['date'] for r in rows))
    idx   = {d: i for i, d in enumerate(dates)}
    tot   = {d: 0 for d in dates}
    pre   = {d: 0 for d in dates}
    for r in rows:
        tot[r['date']] += 1
        if r['status'] == 'P':
            pre[r['date']] += 1

    ct = cp = 0
    X, y = [], []
    for d in dates:
        ct += tot[d]
        cp += pre[d]
        if ct:
            X.append([idx[d]])
            y.append(cp / ct * 100)

    if len(X) < 3:
        return None

    np_X = np.array(X)
    np_y = np.array(y)
    m    = LinearRegression().fit(np_X, np_y)
    pred = float(m.predict([[120]])[0])

    return {
        'predicted_pct': round(max(0.0, min(100.0, pred)), 1),
        'trend':         'rising' if m.coef_[0] > 0 else 'falling',
        'r2':            round(float(m.score(np_X, np_y)), 2),
    }


# ── Views ─────────────────────────────────────────────────────────────────────

@student_required
def dashboard(request):
    student = request.student
    stats   = _attendance_stats(student)
    overall = _overall_attendance(stats)

    today      = timezone.localdate()
    week_start = today - datetime.timedelta(days=6)
    daily_recs = (
        Attendance.objects
        .filter(student=student, date__gte=week_start)
        .select_related('timetable_entry__subject')
        .order_by('date', 'timetable_entry__period')
    )
    daily = {}
    for r in daily_recs:
        daily.setdefault(r.date.strftime('%d %b'), []).append(r)

    class_teacher = student.class_teacher.user if student.class_teacher else None
    counsellor    = student.counsellor.user    if student.counsellor    else None
    cgpa          = student.calculate_cgpa()

    return render(request, 'student/dashboard.html', {
        'student':       student,
        'stats':         stats,
        'overall':       overall,
        'daily':         daily,
        'class_teacher': class_teacher,
        'counsellor':    counsellor,
        'cgpa':          cgpa,
        'ai_prediction': _predict_attendance(student),
        'chart_labels':  [s['code'] for s in stats],
        'chart_data':    [s['percentage'] for s in stats],
    })


@student_required
def timetable(request):
    student = request.student
    section = student.section

    if not section:
        return render(request, 'student/timetable.html', {'no_section': True})

    entries = (
        Timetable.objects
        .filter(section=section)
        .select_related('subject', 'faculty__user')
        .order_by('day', 'period')
    )
    days    = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
    periods = list(range(1, 9))
    grid    = {day: {p: None for p in periods} for day in days}
    for e in entries:
        if e.day in grid:
            grid[e.day][e.period] = e

    return render(request, 'student/timetable.html', {
        'section': section,
        'days':    days,
        'periods': periods,
        'grid':    grid,
    })


@student_required
def results(request):
    student = request.student
    semester = request.GET.get('semester', '')

    # Guard: student must have branch and year assigned
    if not student.branch or not student.year:
        return render(request, 'student/results.html', {
            'student':        student,
            'selected_sem':   1,
            'semesters':      range(1, 9),
            'subject_report': [],
            'sgpa':           0.0,
            'cgpa':           0.0,
            'pass_status':    '—',
            'exams':          [],
        })

    if not semester:
        # Default to the student's current year & semester level
        semester = (student.year.year * 2) - 1

    try:
        semester = int(semester)
    except ValueError:
        semester = 1
    
    # Fetch all subjects for this student's branch, year, and selected semester
    subjects = Subject.objects.filter(branch=student.branch, year=student.year, semester=semester).order_by('name')
    
    # Fetch all results for this student for exams in the selected semester
    results_qs = Result.objects.filter(
        student=student, 
        subject__semester=semester
    ).select_related('exam', 'subject')
    
    # Release check: Only show grades/marks if released by Admin or HOD
    from core.models import ResultRelease
    released_exams = set(ResultRelease.objects.filter(released=True).values_list('exam_id', flat=True))

    # Align results by subject code
    subject_report = []
    grade_points = {
        'S': 10, 'A': 9, 'B': 8, 'C': 7, 'D': 6, 'E': 5,
        'F': 0, 'Ab': 0
    }
    total_points = 0
    total_credits = 0
    has_fail = False
    has_any_final = False
    
    for subj in subjects:
        subj_results = results_qs.filter(subject=subj)
        mid1 = subj_results.filter(exam__exam_type='mid1').first()
        mid2 = subj_results.filter(exam__exam_type='mid2').first()
        final = subj_results.filter(exam__exam_type='final').first()
        
        # Check if exam results are released
        show_mid1 = (mid1.exam.id in released_exams) if mid1 else False
        show_mid2 = (mid2.exam.id in released_exams) if mid2 else False
        show_final = (final.exam.id in released_exams) if final else False
        
        mid1_res = mid1 if show_mid1 else None
        mid2_res = mid2 if show_mid2 else None
        final_res = final if show_final else None
        if final_res:
            has_any_final = True
        
        report_item = {
            'subject': subj,
            'mid1': mid1_res,
            'mid2': mid2_res,
            'final': final_res,
        }
        subject_report.append(report_item)
        
        if final_res and final_res.grade:
            g = final_res.grade
            if g in ['CP', 'NCP']:
                if g == 'NCP':
                    has_fail = True
                continue
            if g in ['F', 'Ab']:
                has_fail = True
            credits = subj.credits
            points = grade_points.get(g, 0)
            total_points += points * credits
            total_credits += credits
        elif final_res:
            has_fail = True

    sgpa = round(total_points / total_credits, 2) if total_credits > 0 else 0.0
    cgpa = student.calculate_cgpa()
    pass_status = "Fail" if has_fail else "Pass" if has_any_final else "—"

    # We still keep the original list of exams in case they want it
    exams = Exam.objects.filter(branch=student.branch, year=student.year).order_by('-date')

    return render(request, 'student/results.html', {
        'student':           student,
        'selected_sem':      semester,
        'semesters':         range(1, 9),
        'subject_report':    subject_report,
        'sgpa':              sgpa,
        'cgpa':              cgpa,
        'pass_status':       pass_status,
        'exams':             exams,
    })


@student_required
def academic_calendar(request):
    student   = request.student
    today     = timezone.localdate()
    branch_id = student.branch.id if student.branch else 0
    year_id   = student.year.id   if student.year   else 0
    cache_key = "acal_{}_{}".format(branch_id, year_id)

    events = cache.get(cache_key)
    if events is None:
        events = list(
            AcademicCalendar.objects
            .filter(date__gte=today - datetime.timedelta(days=30))
            .filter(Q(branch=student.branch) | Q(branch__isnull=True))
            .order_by('date')
        )
        cache.set(cache_key, events, timeout=300)

    return render(request, 'student/academic_calendar.html', {
        'upcoming': [e for e in events if e.date >= today],
        'past':     [e for e in events if e.date <  today],
        'today':    today,
    })


@student_required
def question_papers(request):
    student = request.student
    qs = (
        QuestionPaper.objects
        .filter(subject__branch=student.branch)
        .select_related('subject')
        .order_by('-year', '-semester')
    )
    subj_id  = request.GET.get('subject',  '')
    yr       = request.GET.get('year',     '')
    semester = request.GET.get('semester', '')
    if subj_id:
        qs = qs.filter(subject_id=subj_id)
    if yr:
        qs = qs.filter(year=yr)
    if semester:
        qs = qs.filter(semester=semester)

    papers_page = Paginator(qs, 12).get_page(request.GET.get('page', 1))

    return render(request, 'student/question_papers.html', {
        'papers_page':   papers_page,
        'subjects':      Subject.objects.filter(branch=student.branch).order_by('name'),
        'selected_subj': subj_id,
        'selected_year': yr,
        'selected_sem':  semester,
        'semesters':     range(1, 9),
        'years':         range(2018, timezone.now().year + 1),
    })


@student_required
def add_achievement(request):
    student = request.student
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
                return redirect('student:add_achievement')
            except ValueError:
                messages.error(request, "Invalid date format.")
            except Exception as e:
                messages.error(request, f"Error saving achievement: {e}")

    # Fetch existing achievements for this user
    achievements = Achievement.objects.filter(user=request.user).order_by('-date_achieved')
    return render(request, 'student/add_achievement.html', {
        'student': student,
        'achievements': achievements,
    })

