"""
VVIT Portal — Student Views

All views protected by the student_required decorator.
Querysets use select_related / prefetch_related throughout to stay
efficient at 300,000+ student scale.  The academic_calendar view uses
Django's cache framework (5-minute TTL) so simultaneous page loads
hit the DB only once per branch/year combination.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse, FileResponse, Http404
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.core.cache import cache
from django.utils import timezone
from django.db.models import Q
from django.contrib import messages

import logging
import datetime
from functools import wraps

logger = logging.getLogger(__name__)

from accounts.models import Student, Achievement
from core.models import (
    Timetable, Attendance, Result, Exam,
    AcademicCalendar, QuestionPaper, Subject, ClassDiary,
    SubjectTopicPlan, ExamSchedule
)
from core.syllabus_utils import get_subject_syllabus_progress

# Pre-load ML modules at server startup to prevent request-time import lag
try:
    import numpy as np
    from sklearn.linear_model import LinearRegression
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False


# ── Decorator ────────────────────────────────────────────────────────────────

def student_required(view_func):
    """Ensures the visitor is an authenticated student with a valid profile, or gracefully routes other roles."""
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if request.user.role != 'student':
            # Smooth role redirection for timetable routes
            if 'timetable' in request.path:
                if request.user.role == 'admin':
                    return redirect('admin_dashboard:manage_timetable')
                elif request.user.role == 'hod':
                    return redirect('hod:manage_timetable')
                elif request.user.role in ['faculty', 'lab_technician']:
                    return redirect('faculty:my_timetable')
                elif request.user.role == 'deo':
                    return redirect('deo:manage_timetable')
            return redirect(request.user.get_dashboard_url())
        try:
            request.student = request.user.student_profile
        except Student.DoesNotExist:
            from django.contrib.auth import logout
            logout(request)
            messages.error(request, "Student profile not found — please contact administrator.")
            return redirect('accounts:login')
        return view_func(request, *args, **kwargs)
    return wrapper


# ── Helpers ───────────────────────────────────────────────────────────────────

def _attendance_stats(student, semester=None, year=None):
    """
    Return a per-subject list of {code, name, short_name, year, semester, total, present, absent, percentage}.
    Always calculated live on request so faculty attendance updates reflect immediately in the student's panel.
    """
    records = (
        Attendance.objects
        .filter(student=student)
        .select_related('timetable_entry__subject__year')
    )
    if semester:
        records = records.filter(timetable_entry__subject__semester=semester)
    if year:
        records = records.filter(timetable_entry__subject__year__year=year)

    stats = {}
    for rec in records:
        subj = rec.timetable_entry.subject
        key  = subj.code
        if key not in stats:
            subj_year_val = subj.year.year if hasattr(subj, 'year') and subj.year else 1
            stats[key] = {
                'name': subj.name,
                'code': key,
                'short_name': subj.short_name,
                'year': subj_year_val,
                'semester': subj.semester,
                'total': 0,
                'present': 0
            }
        stats[key]['total'] += 1
        if rec.status == 'P':
            stats[key]['present'] += 1
    for s in stats.values():
        t = s['total']
        s['percentage'] = round(s['present'] / t * 100, 1) if t else 0
        s['absent'] = s['total'] - s['present']
    return list(stats.values())


def _overall_attendance(stats):
    total   = sum(s['total']   for s in stats)
    present = sum(s['present'] for s in stats)
    return round(present / total * 100, 1) if total else 0


def _predict_attendance(student):
    """
    Linear regression prediction of semester-end attendance (60s cache).
    Returns None gracefully if scikit-learn is absent or data is sparse.
    """
    if not SKLEARN_AVAILABLE:
        return None

    cache_key = f"student_ai_pred_v2_{student.id}"
    cached_pred = cache.get(cache_key)
    if cached_pred is not None:
        return cached_pred if cached_pred != 'NONE' else None

    today  = timezone.localdate()
    start  = today - datetime.timedelta(days=60)
    rows   = list(
        Attendance.objects
        .filter(student=student, date__gte=start)
        .order_by('date')
        .values('date', 'status')
    )
    if len(rows) < 5:
        cache.set(cache_key, 'NONE', timeout=60)
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
        cache.set(cache_key, 'NONE', timeout=60)
        return None

    np_X = np.array(X)
    np_y = np.array(y)
    m    = LinearRegression().fit(np_X, np_y)
    pred = float(m.predict([[120]])[0])

    res = {
        'predicted_pct': round(max(0.0, min(100.0, pred)), 1),
        'trend':         'rising' if m.coef_[0] > 0 else 'falling',
        'r2':            round(float(m.score(np_X, np_y)), 2),
    }
    cache.set(cache_key, res, timeout=60)
    return res


# ── Views ─────────────────────────────────────────────────────────────────────

@student_required
def dashboard(request):
    """
    Student Main Dashboard with dynamic choice of viewing Current Semester
    or inspecting any past Semester/Year attendance records in real-time.
    """
    student = request.student
    
    # Semester & Year filter parameters (e.g. ?semester=3 or ?year=2)
    selected_sem_param = request.GET.get('semester', '').strip()
    selected_year_param = request.GET.get('year', '').strip()
    selected_sem = int(selected_sem_param) if selected_sem_param.isdigit() else None
    selected_year = int(selected_year_param) if selected_year_param.isdigit() else None

    stats   = _attendance_stats(student, semester=selected_sem, year=selected_year)
    overall = _overall_attendance(stats)

    # Get all semesters that have recorded attendance for this student
    recorded_sems = list(
        Attendance.objects
        .filter(student=student)
        .values_list('timetable_entry__subject__semester', flat=True)
        .distinct()
        .order_by('timetable_entry__subject__semester')
    )
    if not recorded_sems:
        year_num = student.year.year if (hasattr(student, 'year') and student.year and hasattr(student.year, 'year')) else (student.year if isinstance(student.year, int) else 2)
        current_max_sem = min(8, max(2, year_num * 2))
        recorded_sems = list(range(1, current_max_sem + 1))

    today      = timezone.localdate()
    week_start = today - datetime.timedelta(days=6)
    
    # 1. Fetch attendance records in the last 7 calendar days
    daily_base_qs = Attendance.objects.filter(student=student)
    if selected_sem:
        daily_base_qs = daily_base_qs.filter(timetable_entry__subject__semester=selected_sem)
    if selected_year:
        daily_base_qs = daily_base_qs.filter(timetable_entry__subject__year__year=selected_year)

    daily_dates = list(
        daily_base_qs
        .filter(date__gte=week_start)
        .values_list('date', flat=True)
        .distinct()
        .order_by('-date')
    )
    
    # 2. If no attendance in the last 7 calendar days (e.g. weekends/holidays), fetch the latest 7 active attendance dates
    if not daily_dates:
        daily_dates = list(
            daily_base_qs
            .values_list('date', flat=True)
            .distinct()
            .order_by('-date')[:7]
        )

    daily = {}
    if daily_dates:
        daily_recs = (
            daily_base_qs
            .filter(date__in=daily_dates)
            .select_related('timetable_entry__subject')
            .order_by('-date', 'timetable_entry__period')
        )
        for r in daily_recs:
            daily.setdefault(r.date.strftime('%d %b %Y'), []).append(r)

    class_teacher = student.class_teacher.user if student.class_teacher else None
    counsellor    = student.counsellor.user    if student.counsellor    else None
    cgpa          = student.calculate_cgpa()

    # Recent Class Discussion Logs for student's section
    recent_class_logs = []
    if student.section:
        recent_class_logs = (
            ClassDiary.objects
            .filter(section=student.section)
            .select_related('subject', 'faculty__user')
            .order_by('-date', '-period')[:5]
        )

    return render(request, 'student/dashboard.html', {
        'student':           student,
        'stats':             stats,
        'overall':           overall,
        'daily':             daily,
        'selected_sem':      selected_sem,
        'selected_year':     selected_year,
        'available_sems':    recorded_sems,
        'class_teacher':     class_teacher,
        'counsellor':        counsellor,
        'cgpa':              cgpa,
        'ai_prediction':     _predict_attendance(student),
        'chart_labels':      [s['code'] for s in stats],
        'chart_data':        [s['percentage'] for s in stats],
        'recent_class_logs': recent_class_logs,
    })


@student_required
def attendance_log(request):
    """
    Comprehensive Student Attendance History & Eligibility Center.
    Allows student to inspect full attendance history across any past semester,
    academic year, subject, status, or custom date range with live real-time sync.
    """
    import math
    student = request.student
    
    sem_param     = request.GET.get('semester', '').strip()
    year_param    = request.GET.get('year', '').strip()
    subj_param    = request.GET.get('subject', '').strip()
    status_param  = request.GET.get('status', '').strip()
    date_from     = request.GET.get('date_from', '').strip()
    date_to       = request.GET.get('date_to', '').strip()

    selected_sem  = int(sem_param) if sem_param.isdigit() else None
    selected_year = int(year_param) if year_param.isdigit() else None

    # Base query for stats
    stats = _attendance_stats(student, semester=selected_sem, year=selected_year)
    overall = _overall_attendance(stats)

    total_classes  = sum(s['total'] for s in stats)
    total_present  = sum(s['present'] for s in stats)
    total_absent   = total_classes - total_present

    # Calculate classes needed to reach 75% or classes can afford to miss
    classes_needed_for_75 = 0
    can_miss_classes = 0
    if total_classes > 0:
        if overall < 75.0:
            classes_needed_for_75 = max(0, math.ceil(3 * total_classes - 4 * total_present))
        else:
            can_miss_classes = max(0, math.floor((total_present / 0.75) - total_classes))

    # Detailed Records Query with all filters
    records_qs = (
        Attendance.objects
        .filter(student=student)
        .select_related('timetable_entry__subject__year', 'timetable_entry__faculty__user', 'marked_by__user')
        .order_by('-date', 'timetable_entry__period')
    )

    if selected_sem:
        records_qs = records_qs.filter(timetable_entry__subject__semester=selected_sem)
    if selected_year:
        records_qs = records_qs.filter(timetable_entry__subject__year__year=selected_year)
    if subj_param:
        records_qs = records_qs.filter(timetable_entry__subject_id=subj_param)
    if status_param in ('P', 'A'):
        records_qs = records_qs.filter(status=status_param)
    if date_from:
        try:
            records_qs = records_qs.filter(date__gte=datetime.date.fromisoformat(date_from))
        except ValueError:
            pass
    if date_to:
        try:
            records_qs = records_qs.filter(date__lte=datetime.date.fromisoformat(date_to))
        except ValueError:
            pass

    import calendar
    today = timezone.localdate()

    # Month & Calendar Year Filter (default to current month/year)
    month_param    = request.GET.get('month', '').strip()
    cal_year_param = request.GET.get('cal_year', '').strip()
    
    selected_month    = int(month_param) if month_param.isdigit() and 1 <= int(month_param) <= 12 else today.month
    selected_cal_year = int(cal_year_param) if cal_year_param.isdigit() and 2000 <= int(cal_year_param) <= 2100 else today.year

    num_days_in_month = calendar.monthrange(selected_cal_year, selected_month)[1]
    day_indices = list(range(1, num_days_in_month + 1))
    day_headers = [f"{d:02d}" for d in day_indices]

    # Query attendance records for the monthly sheet
    monthly_qs = (
        Attendance.objects
        .filter(student=student, date__year=selected_cal_year, date__month=selected_month)
        .select_related('timetable_entry__subject')
    )
    if selected_sem:
        monthly_qs = monthly_qs.filter(timetable_entry__subject__semester=selected_sem)
    if selected_year:
        monthly_qs = monthly_qs.filter(timetable_entry__subject__year__year=selected_year)
    if subj_param:
        monthly_qs = monthly_qs.filter(timetable_entry__subject_id=subj_param)

    # Group records by subject id
    monthly_subj_map = {}
    for att in monthly_qs:
        sid = att.timetable_entry.subject_id
        monthly_subj_map.setdefault(sid, []).append(att)

    # Get target subjects for student
    target_subjects = list(
        Subject.objects
        .filter(branch=student.branch, is_deleted=False)
        .order_by('name')
    )
    if selected_sem:
        target_subjects = [s for s in target_subjects if s.semester == selected_sem]
    elif student.section and hasattr(student, 'year') and student.year:
        year_num = student.year.year if hasattr(student.year, 'year') else student.year
        target_subjects = [s for s in target_subjects if s.id in monthly_subj_map or (hasattr(s, 'year') and s.year and (s.year == student.year or getattr(s.year, 'year', None) == year_num))]

    if not target_subjects:
        target_subjects = list(
            Subject.objects
            .filter(id__in=monthly_subj_map.keys())
            .order_by('name')
        )

    monthly_rows = []
    month_tot_p = 0
    month_tot_a = 0
    month_tot_l = 0
    month_tot_h = 0
    daily_column_totals = {d: {'p': 0, 'a': 0} for d in day_indices}

    for sub in target_subjects:
        sub_recs = monthly_subj_map.get(sub.id, [])
        if not sub_recs and monthly_subj_map and sub.id not in monthly_subj_map:
            continue

        day_cells = []
        sub_p = 0
        sub_a = 0
        sub_l = 0
        sub_h = 0

        for d in day_indices:
            d_date = datetime.date(selected_cal_year, selected_month, d)
            d_recs = [r for r in sub_recs if r.date == d_date]
            if not d_recs:
                day_cells.append({'day': d, 'day_str': f"{d:02d}", 'status': '', 'has_class': False})
            else:
                has_p = any(r.status == 'P' for r in d_recs)
                has_a = any(r.status == 'A' for r in d_recs)
                p_cnt = sum(1 for r in d_recs if r.status == 'P')
                a_cnt = sum(1 for r in d_recs if r.status == 'A')
                sub_p += p_cnt
                sub_a += a_cnt
                daily_column_totals[d]['p'] += p_cnt
                daily_column_totals[d]['a'] += a_cnt

                if has_a and not has_p:
                    status_char = 'A'
                elif has_p and not has_a:
                    status_char = 'P'
                else:
                    status_char = 'P'

                day_cells.append({
                    'day': d,
                    'day_str': f"{d:02d}",
                    'status': status_char,
                    'has_class': True,
                    'count': len(d_recs),
                    'periods': [r.timetable_entry.period for r in d_recs]
                })

        sub_tot = sub_p + sub_a
        sub_pct = round((sub_p / sub_tot * 100), 2) if sub_tot > 0 else 100.0
        pct_formatted = f"{sub_pct:.2f} %" if sub_tot > 0 else "100 %"
        if sub_pct == 100.0 or sub_pct == 100:
            pct_formatted = "100 %"

        month_tot_p += sub_p
        month_tot_a += sub_a

        monthly_rows.append({
            'subject_code': sub.code,
            'subject_name': sub.name.upper(),
            'short_name': sub.short_name,
            'day_cells': day_cells,
            'p': sub_p,
            'a': sub_a,
            'l': sub_l,
            'h': sub_h,
            'pct': pct_formatted,
            'pct_val': sub_pct,
            'total_conducted': sub_tot,
        })

    overall_month_tot = month_tot_p + month_tot_a
    overall_month_pct = round((month_tot_p / overall_month_tot * 100), 2) if overall_month_tot > 0 else 100.0
    overall_month_pct_str = f"{overall_month_pct:.2f} %" if overall_month_tot > 0 else "100 %"

    months_list = [
        (1, 'January'), (2, 'February'), (3, 'March'), (4, 'April'),
        (5, 'May'), (6, 'June'), (7, 'July'), (8, 'August'),
        (9, 'September'), (10, 'October'), (11, 'November'), (12, 'December')
    ]
    years_list = [today.year, today.year - 1, today.year - 2]

    # Build Day-Wise Period Matrix Table data
    matrix_map = {}
    for rec in records_qs:
        d_key = rec.date
        if d_key not in matrix_map:
            matrix_map[d_key] = {
                'date': rec.date,
                'day': rec.date.strftime('%A'),
                'periods': {p: None for p in range(1, 8)},
                'present': 0,
                'total': 0,
            }
        p_num = rec.timetable_entry.period
        if 1 <= p_num <= 7:
            matrix_map[d_key]['periods'][p_num] = rec
        matrix_map[d_key]['total'] += 1
        if rec.status == 'P':
            matrix_map[d_key]['present'] += 1

    matrix_list = []
    for d_key in sorted(matrix_map.keys(), reverse=True):
        entry = matrix_map[d_key]
        t = entry['total']
        entry['percentage'] = round((entry['present'] / t * 100), 1) if t else 0
        matrix_list.append(entry)

    # Paginate daily matrix (20 days per page)
    matrix_paginator = Paginator(matrix_list, 20)
    matrix_page_number = request.GET.get('matrix_page', 1)
    matrix_page_obj = matrix_paginator.get_page(matrix_page_number)

    # Paginate detailed records (30 records per page)
    paginator = Paginator(records_qs, 30)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    # Get available subjects for filter
    available_subjects = Subject.objects.filter(branch=student.branch, is_deleted=False).order_by('code')
    if selected_sem:
        available_subjects = available_subjects.filter(semester=selected_sem)
    if selected_year:
        available_subjects = available_subjects.filter(year__year=selected_year)

    # Available Semesters with records
    recorded_sems = list(
        Attendance.objects
        .filter(student=student)
        .values_list('timetable_entry__subject__semester', flat=True)
        .distinct()
        .order_by('timetable_entry__subject__semester')
    )
    if not recorded_sems:
        year_num = student.year.year if (hasattr(student, 'year') and student.year and hasattr(student.year, 'year')) else (student.year if isinstance(student.year, int) else 2)
        current_max_sem = min(8, max(2, year_num * 2))
        recorded_sems = list(range(1, current_max_sem + 1))

    view_mode = request.GET.get('view', 'monthly').strip()

    return render(request, 'student/attendance_log.html', {
        'student':                student,
        'stats':                  stats,
        'overall':                overall,
        'total_classes':          total_classes,
        'total_present':          total_present,
        'total_absent':           total_absent,
        'classes_needed_for_75':  classes_needed_for_75,
        'can_miss_classes':       can_miss_classes,
        'page_obj':               page_obj,
        'matrix_page_obj':        matrix_page_obj,
        'periods_range':          range(1, 8),
        'available_subjects':     available_subjects,
        'available_sems':         recorded_sems,
        'selected_sem':           selected_sem,
        'selected_year':          selected_year,
        'selected_subj':          subj_param,
        'selected_status':        status_param,
        'date_from':              date_from,
        'date_to':                date_to,
        'view_mode':              view_mode,
        # Monthly Matrix Table Context
        'monthly_rows':           monthly_rows,
        'day_headers':            day_headers,
        'selected_month':         selected_month,
        'selected_cal_year':      selected_cal_year,
        'selected_month_name':    calendar.month_name[selected_month],
        'months_list':            months_list,
        'years_list':             years_list,
        'month_tot_p':            month_tot_p,
        'month_tot_a':            month_tot_a,
        'month_tot_l':            month_tot_l,
        'month_tot_h':            month_tot_h,
        'overall_month_pct':      overall_month_pct,
        'overall_month_pct_str':  overall_month_pct_str,
    })


@student_required
def class_diary(request):
    """
    Displays daily class lesson & discussion logs for the student's section,
    along with syllabus progress summary per subject.
    """
    student = request.student
    section = student.section
    today   = timezone.localdate()
    from core.transfer_utils import parse_flexible_date

    if not section:
        return render(request, 'student/class_diary.html', {'no_section': True, 'entries': [], 'syllabus_summaries': []})

    search_query  = request.GET.get('search', '').strip()
    subject_id    = request.GET.get('subject_id', '').strip()
    date_from_str = request.GET.get('date_from', '').strip()
    date_to_str   = request.GET.get('date_to', '').strip()

    diary_qs = (
        ClassDiary.objects
        .filter(section=section)
        .select_related('subject', 'faculty__user', 'timetable_entry')
    )

    if search_query:
        diary_qs = diary_qs.filter(
            Q(topic_covered__icontains=search_query) |
            Q(discussion_summary__icontains=search_query) |
            Q(homework_assignment__icontains=search_query) |
            Q(subject__name__icontains=search_query) |
            Q(subject__code__icontains=search_query) |
            Q(faculty__user__first_name__icontains=search_query) |
            Q(faculty__user__last_name__icontains=search_query)
        )

    if subject_id and subject_id.isdigit():
        diary_qs = diary_qs.filter(subject_id=int(subject_id))

    date_from = parse_flexible_date(date_from_str)
    date_to   = parse_flexible_date(date_to_str)

    if date_from:
        diary_qs = diary_qs.filter(date__gte=date_from)
    if date_to:
        diary_qs = diary_qs.filter(date__lte=date_to)

    entries = diary_qs.order_by('-date', '-period')

    # Get subjects taught in this section and their syllabus progress
    section_subj_ids = Timetable.objects.filter(section=section).values_list('subject_id', flat=True).distinct()
    section_subjects = Subject.objects.filter(id__in=section_subj_ids, is_deleted=False).order_by('code')

    syllabus_summaries = []
    for subj in section_subjects:
        prog = get_subject_syllabus_progress(subj)
        syllabus_summaries.append({
            'subject': subj,
            'completion_pct': prog['completion_pct'],
            'units_completed_count': prog['units_completed_count'],
            'total_topics': prog['total_topics'],
            'completed_topics': prog['completed_topics'],
            'is_mid1_target_met': prog['is_mid1_target_met'],
            'mid1_deadline': prog['mid1_deadline'],
            'status_label': prog['status_label'],
            'status_color': prog['status_color'],
        })

    return render(request, 'student/class_diary.html', {
        'student': student,
        'section': section,
        'entries': entries,
        'section_subjects': section_subjects,
        'syllabus_summaries': syllabus_summaries,
        'search_query': search_query,
        'subject_id': int(subject_id) if subject_id and subject_id.isdigit() else '',
        'date_from': date_from_str,
        'date_to': date_to_str,
        'today': today,
    })


@student_required
def syllabus_coverage(request, subject_id=None):
    """
    Detailed view for students to see the full planned topic timetable,
    how many topics were covered per unit, upcoming topics, and Mid-1 / Mid-2 exam readiness.
    """
    student = request.student
    section = student.section
    today   = timezone.localdate()

    # Subjects for student's branch & year & current semester
    semester = (student.year.year * 2) - 1 if student.year else 1
    subjects = Subject.objects.filter(branch=student.branch, year=student.year, semester=semester, is_deleted=False).order_by('code')
    if not subjects.exists():
        subjects = Subject.objects.filter(branch=student.branch, year=student.year, is_deleted=False).order_by('code')

    selected_subject = None
    if subject_id:
        selected_subject = get_object_or_404(Subject, id=subject_id, is_deleted=False)
    elif subjects.exists():
        selected_subject = subjects.first()

    progress_data = None
    topics_by_unit = {}
    if selected_subject:
        progress_data = get_subject_syllabus_progress(selected_subject)
        all_topics = SubjectTopicPlan.objects.filter(subject=selected_subject).order_by('unit_number', 'order', 'target_date')
        for u in [1, 2, 3, 4, 5]:
            topics_by_unit[u] = [t for t in all_topics if t.unit_number == u]

    context = {
        'student': student,
        'section': section,
        'subjects': subjects,
        'selected_subject': selected_subject,
        'progress_data': progress_data,
        'topics_by_unit': topics_by_unit,
        'today': today,
    }
    return render(request, 'student/syllabus_coverage.html', context)


from core.timetable_service import get_section_timetable_context, generate_official_timetable_pdf

@student_required
def timetable(request):
    """
    Renders the student's class timetable in the official VVIT institutional layout
    with live faculty attendance status and proxy teacher alerts.
    """
    student = request.student
    section = student.section

    if not section:
        return render(request, 'student/timetable.html', {'no_section': True})

    ctx = get_section_timetable_context(section, target_date=timezone.localdate())
    ctx.update({
        'can_edit': False,
        'can_upload': False,
        'pdf_export_url': '/student/timetable/pdf/',
    })
    return render(request, 'student/timetable.html', ctx)


@student_required
def download_timetable_pdf(request):
    """
    Downloads the student's class timetable as an official A4 Landscape PDF.
    """
    student = request.student
    section = student.section

    if not section:
        messages.error(request, "No section assigned.")
        return redirect('student:timetable')

    pdf_bytes = generate_official_timetable_pdf(section)
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="VVIT_Timetable_{section.branch.code}_{section.year.year}_{section.name}.pdf"'
    return response



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
    subjects = Subject.objects.filter(branch=student.branch, year=student.year, semester=semester, is_deleted=False).order_by('name')
    
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


@login_required
def academic_calendar(request):
    today = timezone.localdate()
    branch = None
    if request.user.role == 'student':
        student = getattr(request.user, 'student_profile', None)
        if student and student.branch:
            branch = student.branch
    elif request.user.role in ['faculty', 'hod', 'lab_technician']:
        faculty = getattr(request.user, 'faculty_profile', None)
        if faculty and faculty.department:
            branch = faculty.department

    events = list(
        AcademicCalendar.objects
        .filter(date__gte=today - datetime.timedelta(days=30))
        .filter(Q(branch=branch) | Q(branch__isnull=True) if branch else Q())
        .order_by('date')
    )

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
        .order_by('-academic_year', '-semester', 'regulation')
    )
    subj_id       = request.GET.get('subject',       '')
    regulation    = request.GET.get('regulation',    '')
    academic_year = request.GET.get('academic_year', '')
    semester      = request.GET.get('semester',      '')

    if subj_id:
        qs = qs.filter(subject_id=subj_id)
    if regulation:
        qs = qs.filter(regulation=regulation)
    if academic_year:
        qs = qs.filter(academic_year=academic_year)
    if semester:
        qs = qs.filter(semester=semester)

    papers_page = Paginator(qs, 12).get_page(request.GET.get('page', 1))

    # Standard VVIT regulations and academic years
    regulations = ['R23', 'R20', 'R19', 'R16']
    academic_years = ['25 - 26', '24 - 25', '23 - 24', '22 - 23', '21 - 22', '20 - 21']

    return render(request, 'student/question_papers.html', {
        'papers_page':    papers_page,
        'subjects':       Subject.objects.filter(branch=student.branch, is_deleted=False).order_by('name'),
        'selected_subj':  subj_id,
        'selected_reg':   regulation,
        'selected_ay':    academic_year,
        'selected_sem':   semester,
        'regulations':    regulations,
        'academic_years': academic_years,
        'semesters':      range(1, 9),
    })


@student_required
def download_question_paper(request, paper_id):
    student = request.student
    paper = get_object_or_404(QuestionPaper, id=paper_id, subject__branch=student.branch)
    if not paper.file:
        messages.error(request, "Question paper PDF file is not available.")
        return redirect('student:question_papers')
    
    try:
        file_handle = paper.file.open('rb')
        response = FileResponse(file_handle, content_type='application/pdf')
        filename = f"{paper.subject.code}_{paper.regulation}_{paper.academic_year.replace(' ', '')}_Sem{paper.semester}.pdf"
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        return response
    except Exception as e:
        messages.error(request, f"Unable to read question paper file: {e}")
        return redirect('student:question_papers')


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


@student_required
def counselling_report(request):
    """
    Comprehensive student counselling dossier web report.
    """
    from core.counselling_utils import get_student_counselling_dossier
    from django.urls import reverse

    student = request.student
    dossier = get_student_counselling_dossier(student)

    context = {
        'dossier': dossier,
        'pdf_download_url': reverse('student:download_counselling_report_pdf'),
        'back_url': reverse('student:dashboard'),
    }
    return render(request, 'reports/counselling_report.html', context)


@student_required
def download_counselling_report_pdf(request):
    """
    Download official student counselling dossier as a ReportLab PDF.
    """
    from core.counselling_utils import generate_counselling_report_pdf
    from django.http import HttpResponse

    student = request.student
    pdf_bytes = generate_counselling_report_pdf(student)

    filename = f"{student.roll_number}_Counselling_Dossier.pdf"
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@student_required
def download_monthly_attendance_pdf(request):
    """
    Download official Monthly Subject Attendance Matrix as a landscape ReportLab PDF.
    """
    from core.pdf_utils import generate_monthly_attendance_pdf

    student = request.student
    now = timezone.now()
    try:
        month = int(request.GET.get('month', now.month))
        cal_year = int(request.GET.get('cal_year', now.year))
    except (ValueError, TypeError):
        month = now.month
        cal_year = now.year

    sem = request.GET.get('semester')
    try:
        sem = int(sem) if sem else None
    except (ValueError, TypeError):
        sem = None

    buf = generate_monthly_attendance_pdf(student, month, cal_year, selected_sem=sem)
    filename = f"VVITU_Attendance_{student.roll_number}_{month}_{cal_year}.pdf"
    return FileResponse(buf, as_attachment=True, filename=filename, content_type='application/pdf')


@student_required
def download_grade_card_pdf(request):
    """
    Download official Semester Grade Card & Transcript as a ReportLab PDF.
    """
    from core.pdf_utils import generate_semester_grade_card_pdf

    student = request.student
    sem = request.GET.get('semester')
    try:
        sem = int(sem) if sem else None
    except (ValueError, TypeError):
        sem = None

    buf = generate_semester_grade_card_pdf(student, selected_sem=sem)
    filename = f"VVITU_Grade_Card_{student.roll_number}.pdf"
    return FileResponse(buf, as_attachment=True, filename=filename, content_type='application/pdf')


@student_required
def apply_leave_od(request):
    """
    Student On-Duty (OD) & Medical Leave application portal.
    """
    from accounts.models import StudentLeaveRequest

    student = request.student

    if request.method == 'POST':
        leave_type = request.POST.get('leave_type', 'medical')
        start_date_str = request.POST.get('start_date')
        end_date_str = request.POST.get('end_date')
        reason = request.POST.get('reason', '').strip()
        doc_file = request.FILES.get('document')

        if not start_date_str or not end_date_str or not reason:
            messages.error(request, "Please fill in all required fields (dates and reason).")
        else:
            try:
                start_date = datetime.datetime.strptime(start_date_str, '%Y-%m-%d').date()
                end_date = datetime.datetime.strptime(end_date_str, '%Y-%m-%d').date()
                if end_date < start_date:
                    messages.error(request, "End date cannot be before start date.")
                else:
                    if doc_file:
                        from core.file_validators import validate_document_upload
                        from django.core.exceptions import ValidationError
                        try:
                            validate_document_upload(doc_file, max_size_mb=5)
                        except ValidationError as ve:
                            messages.error(request, f"Document upload rejected: {ve.message if hasattr(ve, 'message') else ve}")
                            past_requests = StudentLeaveRequest.objects.filter(student=student).order_by('-created_at')
                            return render(request, 'student/leave_apply.html', {'student': student, 'past_requests': past_requests})

                    leave_req = StudentLeaveRequest.objects.create(
                        student=student,
                        leave_type=leave_type,
                        start_date=start_date,
                        end_date=end_date,
                        reason=reason,
                        document=doc_file,
                        status='pending'
                    )
                    messages.success(request, f"Leave application ({leave_req.get_leave_type_display()}) submitted successfully for review.")
                    return redirect('student:apply_leave_od')
            except ValueError:
                messages.error(request, "Invalid date format provided.")

    past_requests = StudentLeaveRequest.objects.filter(student=student).order_by('-created_at')

    return render(request, 'student/leave_apply.html', {
        'student': student,
        'past_requests': past_requests,
    })


@student_required
def apply_readmission(request):
    """
    Readmission application for detained students (attendance shortage or credit shortage)
    requesting to repeat the year with juniors.
    """
    from accounts.models import StudentReadmissionRequest
    from core.models import Year, Section

    student = request.student

    if request.method == 'POST':
        detention_type = request.POST.get('detention_type', 'attendance')
        target_year_id = request.POST.get('target_year')
        target_section_id = request.POST.get('target_section')
        reason = request.POST.get('reason', '').strip()

        if not target_year_id or not reason:
            messages.error(request, "Please select target junior year and explain your reason.")
        else:
            try:
                target_year = Year.objects.get(id=target_year_id)
                target_section = Section.objects.get(id=target_section_id) if target_section_id else None

                readmission_req = StudentReadmissionRequest.objects.create(
                    student=student,
                    detention_type=detention_type,
                    previous_year=student.year,
                    previous_section=student.section,
                    target_junior_year=target_year,
                    target_junior_section=target_section,
                    reason=reason,
                    hod_status='pending',
                    admin_status='pending'
                )
                messages.success(request, "Readmission application submitted successfully. It will be reviewed by the HOD and Dean/Admin.")
                return redirect('student:apply_readmission')
            except Exception as e:
                messages.error(request, f"Error processing readmission request: {e}")

    past_readmissions = StudentReadmissionRequest.objects.filter(student=student).order_by('-created_at')
    available_years = Year.objects.all().order_by('year')
    available_sections = Section.objects.filter(branch=student.branch).order_by('name') if student.branch else []

    return render(request, 'student/readmission_apply.html', {
        'student': student,
        'past_readmissions': past_readmissions,
        'available_years': available_years,
        'available_sections': available_sections,
    })


# ─────────────────────────────────────────────
# STUDENT FEEDBACK FORMS & DOCUMENT WORKFLOW
# ─────────────────────────────────────────────
@student_required
def feedback_list(request):
    """
    Lists all active feedback questionnaires targeting this student's branch, year, semester, or section.
    Distinguishes between pending forms and already submitted forms.
    """
    from core.models import FeedbackForm, FeedbackSubmission
    student = request.student

    # Filter applicable forms
    forms_qs = FeedbackForm.objects.filter(is_active=True).filter(
        Q(branch__isnull=True) | Q(branch=student.branch)
    ).filter(
        Q(year__isnull=True) | Q(year=student.year)
    ).filter(
        Q(section__isnull=True) | Q(section=student.section)
    ).order_by('-created_at')

    # Submissions by this student
    student_submissions = FeedbackSubmission.objects.filter(
        student=student
    ).select_related('form')
    
    submitted_form_map = {sub.form_id: sub for sub in student_submissions}

    pending_forms = []
    completed_items = []

    for f in forms_qs:
        if f.id in submitted_form_map:
            sub = submitted_form_map[f.id]
            completed_items.append({
                'form': f,
                'submission': sub,
            })
        else:
            pending_forms.append(f)

    return render(request, 'student/feedback_list.html', {
        'student': student,
        'pending_forms': pending_forms,
        'completed_items': completed_items,
        'total_pending': len(pending_forms),
        'total_completed': len(completed_items),
    })


@student_required
def fill_feedback(request, form_id):
    """
    Interactive online feedback form view.
    Renders questions with star ratings and comments, allows downloading blank PDF for offline fill,
    and records answers on POST.
    """
    from core.models import FeedbackForm, FeedbackQuestion, FeedbackSubmission, FeedbackAnswer
    student = request.student
    form_obj = get_object_or_404(FeedbackForm, id=form_id, is_active=True)

    # Scoping check
    if form_obj.branch and form_obj.branch != student.branch:
        messages.error(request, "This feedback form is not applicable to your department.")
        return redirect('student:feedback_list')
    if form_obj.year and form_obj.year != student.year:
        messages.error(request, "This feedback form is not applicable to your academic year.")
        return redirect('student:feedback_list')
    if form_obj.section and form_obj.section != student.section:
        messages.error(request, "This feedback form is not applicable to your section.")
        return redirect('student:feedback_list')

    # Enforce online submission permission
    if not form_obj.allow_online_submission:
        messages.error(request, "Online submissions are disabled for this feedback form. Please submit a physical copy.")
        return redirect('student:feedback_list')

    # Enforce deadline check
    from django.utils import timezone
    if form_obj.deadline and form_obj.deadline < timezone.now().date():
        messages.error(request, "The submission deadline for this feedback form has passed.")
        return redirect('student:feedback_list')

    # Check if already submitted
    existing_sub = FeedbackSubmission.objects.filter(form=form_obj, student=student).first()
    if existing_sub:
        messages.info(request, "You have already submitted responses for this feedback form. Viewing your submission summary.")
        return redirect('student:feedback_summary', form_id=form_obj.id)

    # Ensure form has questions to answer
    if form_obj.questions.count() == 0:
        # Try extracting from attached document if available
        if form_obj.uploaded_document:
            try:
                from core.document_extractor import extract_feedback_form_data
                form_obj.uploaded_document.file.seek(0)
                extracted = extract_feedback_form_data(form_obj.uploaded_document.file, form_obj.uploaded_document.name)
                if extracted.get('success') and extracted.get('questions'):
                    for eq in extracted['questions']:
                        FeedbackQuestion.objects.create(
                            form=form_obj,
                            question_text=eq['question_text'],
                            question_type=eq['question_type'],
                            options=eq.get('options') or None,
                            is_required=eq.get('is_required', True),
                            order=eq.get('order', 1)
                        )
            except Exception as e:
                logger.warning(f"On-the-fly document extraction in fill_feedback failed: {e}")

        # If still no questions, fallback to standard preset template
        if form_obj.questions.count() == 0:
            from core.feedback_service import populate_preset_questions
            preset_map = {
                'faculty': 'faculty_10',
                'course': 'course_5',
                'institutional': 'infrastructure_6',
                'general': 'faculty_10'
            }
            preset_key = preset_map.get(form_obj.feedback_type, 'faculty_10')
            populate_preset_questions(form_obj, preset_key)

    questions = form_obj.questions.all().order_by('order', 'id')

    if request.method == 'POST':
        overall_comments = request.POST.get('overall_comments', '').strip()
        
        # Get client IP
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip_addr = x_forwarded_for.split(',')[0].strip()
        else:
            ip_addr = request.META.get('REMOTE_ADDR')

        # Create submission
        submission = FeedbackSubmission.objects.create(
            form=form_obj,
            student=student,
            submission_mode='online',
            overall_comments=overall_comments,
            ip_address=ip_addr
        )

        # Save answers for configured questions
        for q in questions:
            rating_val = None
            text_val = None
            choice_val = None

            if q.question_type in ['rating_5', 'rating_10']:
                r_str = request.POST.get(f'question_{q.id}')
                if r_str:
                    try:
                        rating_val = int(r_str)
                    except ValueError:
                        rating_val = 5
                elif q.is_required:
                    rating_val = 5 # Default fallback
                
                # Also check for per-question written remarks
                q_comment = request.POST.get(f'question_{q.id}_comment', '').strip()
                if q_comment:
                    text_val = q_comment
            elif q.question_type == 'choice':
                choice_val = request.POST.get(f'question_{q.id}', '').strip()
                q_comment = request.POST.get(f'question_{q.id}_comment', '').strip()
                if q_comment:
                    text_val = q_comment
            elif q.question_type == 'text':
                text_val = request.POST.get(f'question_{q.id}', '').strip()

            FeedbackAnswer.objects.create(
                submission=submission,
                question=q,
                rating_value=rating_val,
                choice_value=choice_val,
                text_value=text_val
            )

        # Save any extra written answers added by student
        extra_texts = request.POST.getlist('extra_question_text[]')
        extra_answers = request.POST.getlist('extra_question_answer[]')
        extra_ratings = request.POST.getlist('extra_question_rating[]')

        for idx, ex_t in enumerate(extra_texts):
            if ex_t.strip():
                ex_ans = extra_answers[idx] if idx < len(extra_answers) else ''
                ex_rate_str = extra_ratings[idx] if idx < len(extra_ratings) else ''
                ex_rate = None
                if ex_rate_str:
                    try:
                        ex_rate = int(ex_rate_str)
                    except ValueError:
                        pass

                # Create question and answer
                new_q = FeedbackQuestion.objects.create(
                    form=form_obj,
                    question_text=ex_t.strip(),
                    question_type='text' if not ex_rate else 'rating_5',
                    order=form_obj.questions.count() + 1
                )
                FeedbackAnswer.objects.create(
                    submission=submission,
                    question=new_q,
                    rating_value=ex_rate,
                    text_value=ex_ans.strip() if ex_ans.strip() else None
                )

        messages.success(request, f"Feedback submitted successfully! Reference No: {submission.reference_no}. You can now download or print your summary.")
        return redirect('student:feedback_summary', form_id=form_obj.id)

    return render(request, 'student/fill_feedback.html', {
        'student': student,
        'form_obj': form_obj,
        'questions': questions,
    })


@student_required
def feedback_summary(request, form_id):
    """
    Displays the authenticated submission summary and receipt for a completed feedback form.
    """
    from core.models import FeedbackForm, FeedbackSubmission
    student = request.student
    form_obj = get_object_or_404(FeedbackForm, id=form_id)
    submission = FeedbackSubmission.objects.filter(form=form_obj, student=student).first()
    if not submission:
        messages.info(request, "You have not yet submitted responses for this feedback form.")
        return redirect('student:fill_feedback', form_id=form_id)

    answers = submission.answers.select_related('question').order_by('question__order', 'id')

    return render(request, 'student/feedback_summary.html', {
        'student': student,
        'form_obj': form_obj,
        'submission': submission,
        'answers': answers,
    })


@student_required
def download_feedback_pdf(request, form_id):
    """
    Downloads the official ReportLab PDF summary and acknowledgment receipt for a student submission.
    """
    from core.models import FeedbackForm, FeedbackSubmission
    from core.pdf_utils import generate_student_feedback_summary_pdf
    
    student = request.student
    form_obj = get_object_or_404(FeedbackForm, id=form_id)
    submission = FeedbackSubmission.objects.filter(form=form_obj, student=student).first()
    if not submission:
        messages.info(request, "Please submit your feedback response before downloading the summary PDF.")
        return redirect('student:fill_feedback', form_id=form_id)

    try:
        pdf_buffer = generate_student_feedback_summary_pdf(submission)
        filename = f"VVIT_Feedback_Summary_{student.roll_number}_{form_obj.id}.pdf"
        response = HttpResponse(pdf_buffer.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    except Exception as e:
        messages.error(request, f"Failed to generate PDF summary: {e}")
        return redirect('student:feedback_summary', form_id=form_id)


@student_required
def download_blank_feedback_pdf(request, form_id):
    """
    Downloads the official blank printable PDF feedback questionnaire for offline physical filling.
    Restricted to student's department, year, and section scope.
    """
    from core.models import FeedbackForm
    from core.pdf_utils import generate_feedback_blank_printable_pdf

    student = request.student
    form_obj = get_object_or_404(FeedbackForm, id=form_id, is_active=True)

    # Scoping check
    if form_obj.branch and form_obj.branch != student.branch:
        messages.error(request, "This feedback form is not applicable to your department.")
        return redirect('student:feedback_list')
    if form_obj.year and form_obj.year != student.year:
        messages.error(request, "This feedback form is not applicable to your academic year.")
        return redirect('student:feedback_list')
    if form_obj.section and form_obj.section != student.section:
        messages.error(request, "This feedback form is not applicable to your section.")
        return redirect('student:feedback_list')

    if not form_obj.allow_offline_download:
        messages.error(request, "Blank form download is disabled for this feedback questionnaire.")
        return redirect('student:feedback_list')

    try:
        pdf_buffer = generate_feedback_blank_printable_pdf(form_obj)
        filename = f"VVIT_Blank_Feedback_Form_{form_obj.id}.pdf"
        response = HttpResponse(pdf_buffer.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    except Exception as e:
        messages.error(request, f"Failed to generate blank feedback form: {e}")
        return redirect('student:feedback_list')



