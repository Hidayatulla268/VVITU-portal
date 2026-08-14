"""
VVITU Portal — Class Transfer Utilities & Free Faculty Calculation Engine
"""

import logging
import datetime
from django.db.models import Q
from accounts.models import Faculty, FacultyLeaveRequest
from core.models import Timetable, ClassTransfer

logger = logging.getLogger(__name__)


def parse_flexible_date(date_val):
    """
    Safely parses ISO dates (2026-08-14), Flatpickr formatted dates (Fri, 14 Aug 2026),
    and standard date formats into a datetime.date object.
    """
    if not date_val:
        return None
    if isinstance(date_val, datetime.date):
        return date_val
    if isinstance(date_val, datetime.datetime):
        return date_val.date()

    date_str = str(date_val).strip()
    if not date_str:
        return None

    # 1. Try ISO format (2026-08-14)
    try:
        return datetime.date.fromisoformat(date_str)
    except (ValueError, TypeError):
        pass

    # 2. Try common formats (including Flatpickr display formats)
    formats = [
        '%a, %d %b %Y',  # Fri, 14 Aug 2026
        '%A, %d %B %Y',  # Friday, 14 August 2026
        '%d %b %Y',      # 14 Aug 2026
        '%d-%b-%Y',      # 14-Aug-2026
        '%d/%m/%Y',      # 14/08/2026
        '%Y/%m/%d',      # 2026/08/14
        '%d-%m-%Y',      # 14-08-2026
        '%B %d, %Y',     # August 14, 2026
        '%b %d, %Y',     # Aug 14, 2026
    ]
    for fmt in formats:
        try:
            return datetime.datetime.strptime(date_str, fmt).date()
        except (ValueError, TypeError):
            continue

    # 3. Fallback to dateutil parser if present
    try:
        from dateutil import parser
        return parser.parse(date_str).date()
    except Exception:
        pass

    return None



def get_free_faculty_for_period(date, period, department=None, exclude_faculty=None):
    """
    Return a queryset of Faculty members who are 100% FREE during a specific date and period.
    
    Checks:
    1. Excludes faculty who have a scheduled class in Timetable for (day_of_week, period).
    2. Excludes faculty who are already assigned as a proxy/substitute in ClassTransfer for (date, period).
    3. Excludes faculty who are on approved or pending leave on date.
    4. Excludes exclude_faculty (e.g. the original faculty member applying for leave).
    """
    day_name = date.strftime('%A')
    
    # Base Faculty Queryset (Active faculty)
    faculty_qs = Faculty.objects.filter(is_active=True, user__is_deleted=False).select_related('user', 'department')
    
    if department:
        faculty_qs = faculty_qs.filter(department=department)
        
    if exclude_faculty:
        if isinstance(exclude_faculty, Faculty):
            faculty_qs = faculty_qs.exclude(id=exclude_faculty.id)
        else:
            faculty_qs = faculty_qs.exclude(id=exclude_faculty)

    # 1. Faculty busy with their own scheduled classes on this day & period
    busy_timetable_ids = set(
        Timetable.objects.filter(
            day__iexact=day_name,
            period=period
        ).values_list('faculty_id', flat=True)
    )

    # 2. Faculty busy taking another proxy class on this date & period
    busy_proxy_ids = set(
        ClassTransfer.objects.filter(
            date=date,
            timetable_entry__period=period,
            status__in=['accepted', 'pending', 'completed']
        ).values_list('substitute_faculty_id', flat=True)
    )

    # 3. Faculty on leave (approved or pending) on this date
    busy_leave_ids = set(
        FacultyLeaveRequest.objects.filter(
            start_date__lte=date,
            end_date__gte=date,
            status__in=['approved', 'pending']
        ).values_list('faculty_id', flat=True)
    )

    all_busy_ids = busy_timetable_ids | busy_proxy_ids | busy_leave_ids
    
    return faculty_qs.exclude(id__in=all_busy_ids).order_by('user__first_name', 'employee_id')


def get_conducted_class_history(branch=None, faculty=None, search_query=None, date_from=None, date_to=None):
    """
    Returns a unified, sorted list of class conduct records across attendance and class transfers.
    Allows searching by faculty name, subject code, employee ID, section name, and date range.
    Can be filtered by branch (for HOD = specific branch, for Admin = all or specific branch).
    """
    from core.models import Attendance, ClassTransfer, Timetable
    from accounts.models import Faculty
    from django.db.models import Q, Count

    att_qs = Attendance.objects.select_related(
        'timetable_entry__subject',
        'timetable_entry__section__branch',
        'timetable_entry__section__year',
        'timetable_entry__section',
        'timetable_entry__faculty__user',
        'marked_by__user',
        'marked_by__department'
    )

    if branch:
        att_qs = att_qs.filter(timetable_entry__section__branch=branch)

    if faculty:
        if isinstance(faculty, Faculty):
            att_qs = att_qs.filter(Q(marked_by=faculty) | Q(timetable_entry__faculty=faculty))
        else:
            att_qs = att_qs.filter(Q(marked_by_id=faculty) | Q(timetable_entry__faculty_id=faculty))

    if search_query:
        sq = search_query.strip()
        att_qs = att_qs.filter(
            Q(marked_by__user__first_name__icontains=sq) |
            Q(marked_by__user__last_name__icontains=sq) |
            Q(marked_by__employee_id__icontains=sq) |
            Q(timetable_entry__faculty__user__first_name__icontains=sq) |
            Q(timetable_entry__faculty__user__last_name__icontains=sq) |
            Q(timetable_entry__faculty__employee_id__icontains=sq) |
            Q(timetable_entry__subject__code__icontains=sq) |
            Q(timetable_entry__subject__name__icontains=sq) |
            Q(timetable_entry__section__name__icontains=sq)
        )

    if date_from:
        att_qs = att_qs.filter(date__gte=date_from)
    if date_to:
        att_qs = att_qs.filter(date__lte=date_to)

    # Aggregate by (timetable_entry_id, date)
    sessions = (
        att_qs.values('timetable_entry_id', 'date', 'marked_by_id')
        .annotate(
            present_cnt=Count('id', filter=Q(status='P')),
            absent_cnt=Count('id', filter=Q(status='A')),
            total_cnt=Count('id')
        )
        .order_by('-date', 'timetable_entry__period')
    )

    # Pre-fetch timetable entries and transfers for fast lookup
    tt_ids = {s['timetable_entry_id'] for s in sessions}
    tt_map = {
        tt.id: tt
        for tt in Timetable.objects.filter(id__in=tt_ids).select_related(
            'subject', 'section__branch', 'section__year', 'section', 'faculty__user'
        )
    }

    fac_ids = {s['marked_by_id'] for s in sessions if s['marked_by_id']}
    for tt in tt_map.values():
        if tt.faculty_id:
            fac_ids.add(tt.faculty_id)

    fac_map = {
        f.id: f
        for f in Faculty.objects.filter(id__in=fac_ids).select_related('user', 'department')
    }

    # Fetch relevant class transfers for proxy details
    transfers_map = {
        (ct.timetable_entry_id, ct.date): ct
        for ct in ClassTransfer.objects.filter(timetable_entry_id__in=tt_ids).select_related('original_faculty__user', 'substitute_faculty__user')
    }

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

    records = []
    for s in sessions:
        tt = tt_map.get(s['timetable_entry_id'])
        if not tt:
            continue

        date_val = s['date']
        marked_by_fac = fac_map.get(s['marked_by_id'])
        orig_fac = tt.faculty
        ct = transfers_map.get((tt.id, date_val))

        actual_conducted_fac = marked_by_fac or (ct.substitute_faculty if ct else orig_fac)
        is_proxy = (ct is not None) or (actual_conducted_fac and orig_fac and actual_conducted_fac.id != orig_fac.id)

        start_t = tt.start_time.strftime("%I:%M %p") if getattr(tt, 'start_time', None) else None
        end_t   = tt.end_time.strftime("%I:%M %p") if getattr(tt, 'end_time', None) else None
        timing_str = f"{start_t} - {end_t}" if (start_t and end_t) else period_timings.get(tt.period, f"Period {tt.period}")

        records.append({
            'date': date_val,
            'period': tt.period,
            'timing': timing_str,
            'subject': tt.subject,
            'section': tt.section,
            'branch': tt.section.branch if tt.section else None,
            'year': tt.section.year if tt.section else None,
            'conducted_by': actual_conducted_fac,
            'original_faculty': orig_fac,
            'is_proxy': is_proxy,
            'transfer': ct,
            'present_count': s['present_cnt'],
            'absent_count': s['absent_cnt'],
            'total_students': s['total_cnt'],
        })

    return records

