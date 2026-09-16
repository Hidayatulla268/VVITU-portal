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
    Includes BOTH:
    1. Conducted sessions where student attendance was marked.
    2. Scheduled/transferred sessions (Proxies & Substituted Sessions) even before attendance is posted.
    Allows searching by faculty name, subject code, employee ID, section name, and date range.
    Can be filtered by branch (for HOD = specific branch, for Admin = all or specific branch).
    """
    from core.models import Attendance, ClassTransfer, Timetable
    from accounts.models import Faculty
    from django.db.models import Q, Count

    if not date_from and not date_to and not search_query:
        from django.utils import timezone
        date_from = timezone.localdate() - datetime.timedelta(days=30)

    # 1. Fetch Class Transfers matching filters
    ct_qs = ClassTransfer.objects.select_related(
        'timetable_entry__subject',
        'timetable_entry__section__branch',
        'timetable_entry__section__year',
        'timetable_entry__section',
        'timetable_entry__faculty__user',
        'original_faculty__user',
        'original_faculty__department',
        'substitute_faculty__user',
        'substitute_faculty__department',
        'assigned_by',
    )
    if branch:
        ct_qs = ct_qs.filter(timetable_entry__section__branch=branch)
    if faculty:
        if isinstance(faculty, Faculty):
            ct_qs = ct_qs.filter(Q(original_faculty=faculty) | Q(substitute_faculty=faculty))
        else:
            ct_qs = ct_qs.filter(Q(original_faculty_id=faculty) | Q(substitute_faculty_id=faculty))
    if date_from:
        ct_qs = ct_qs.filter(date__gte=date_from)
    if date_to:
        ct_qs = ct_qs.filter(date__lte=date_to)
    if search_query:
        sq = search_query.strip()
        ct_qs = ct_qs.filter(
            Q(substitute_faculty__user__first_name__icontains=sq) |
            Q(substitute_faculty__user__last_name__icontains=sq) |
            Q(substitute_faculty__employee_id__icontains=sq) |
            Q(original_faculty__user__first_name__icontains=sq) |
            Q(original_faculty__user__last_name__icontains=sq) |
            Q(original_faculty__employee_id__icontains=sq) |
            Q(timetable_entry__subject__code__icontains=sq) |
            Q(timetable_entry__subject__name__icontains=sq) |
            Q(timetable_entry__section__name__icontains=sq)
        )

    transfers_list = list(ct_qs)
    transfers_map = {(ct.timetable_entry_id, ct.date): ct for ct in transfers_list}

    # 2. Fetch Attendance sessions matching filters

    att_filter_q = Q()
    if branch:
        att_filter_q &= Q(timetable_entry__section__branch=branch)
    if faculty:
        if isinstance(faculty, Faculty):
            att_filter_q &= (Q(marked_by=faculty) | Q(timetable_entry__faculty=faculty))
        else:
            att_filter_q &= (Q(marked_by_id=faculty) | Q(timetable_entry__faculty_id=faculty))
    if date_from:
        att_filter_q &= Q(date__gte=date_from)
    if date_to:
        att_filter_q &= Q(date__lte=date_to)
    if search_query:
        sq = search_query.strip()
        att_filter_q &= (
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

    # Fetch lightweight dictionary records (100x faster than full ORM model trees)
    att_rows = list(Attendance.objects.filter(att_filter_q).values(
        'timetable_entry_id', 'date', 'status', 'marked_by_id', 'last_modified'
    ))

    # Bulk-load distinct marked_by faculty profiles in a single query
    marked_by_ids = {a['marked_by_id'] for a in att_rows if a['marked_by_id']}
    faculty_lookup = {
        f.id: f
        for f in Faculty.objects.filter(id__in=marked_by_ids).select_related('user', 'department')
    }

    # Accumulate Attendance records cleanly per (timetable_entry_id, date)
    session_map = {}
    for att in att_rows:
        key = (att['timetable_entry_id'], att['date'])
        if key not in session_map:
            session_map[key] = {
                'timetable_entry_id': att['timetable_entry_id'],
                'date': att['date'],
                'marked_by': faculty_lookup.get(att['marked_by_id']),
                'present_cnt': 0,
                'absent_cnt': 0,
                'total_cnt': 0,
                'last_modified': att['last_modified'],
            }
        s = session_map[key]
        s['total_cnt'] += 1
        if att['status'] == 'P':
            s['present_cnt'] += 1
        elif att['status'] == 'A':
            s['absent_cnt'] += 1
        if att['marked_by_id'] and not s['marked_by']:
            s['marked_by'] = faculty_lookup.get(att['marked_by_id'])
        if att['last_modified'] and (not s['last_modified'] or att['last_modified'] > s['last_modified']):
            s['last_modified'] = att['last_modified']

    all_keys = set(session_map.keys()) | set(transfers_map.keys())
    all_tt_ids = {k[0] for k in all_keys}

    tt_map = {
        tt.id: tt
        for tt in Timetable.objects.filter(id__in=all_tt_ids).select_related(
            'subject', 'section__branch', 'section__year', 'section', 'faculty__user'
        )
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
    for (tt_id, date_val) in all_keys:
        tt = tt_map.get(tt_id)
        if not tt:
            continue

        s = session_map.get((tt_id, date_val))
        ct = transfers_map.get((tt_id, date_val))

        marked_by_fac = s['marked_by'] if s else None
        orig_fac = ct.original_faculty if ct else tt.faculty

        # If proxy is accepted or completed, substitute conducted/is conducting; otherwise original faculty
        if ct and ct.status in ['accepted', 'completed']:
            actual_conducted_fac = ct.substitute_faculty
        else:
            actual_conducted_fac = marked_by_fac or orig_fac
        
        is_transferred = (ct is not None and ct.status in ['accepted', 'completed']) or (marked_by_fac and orig_fac and marked_by_fac.id != orig_fac.id)
        is_proxy = (ct.is_proxy if ct else False) or (marked_by_fac and orig_fac and marked_by_fac.id != orig_fac.id and not ct)
        is_substitution = (ct.is_substitution if ct else False) and not is_proxy
        type_label = ct.type_label if ct else ("Proxy" if is_proxy else "Regular Class")

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
            'substitute_faculty': ct.substitute_faculty if ct else None,
            'original_faculty': orig_fac,
            'is_transferred': is_transferred,
            'is_proxy': is_proxy,
            'is_substitution': is_substitution,
            'type_label': type_label,
            'transfer': ct,
            'transfer_status': ct.status if ct else None,
            'transfer_status_label': ct.status_label if ct else None,
            'transfer_status_badge': ct.status_badge_class if ct else None,
            'is_pending': ct.is_pending if ct else False,
            'is_accepted': ct.is_accepted if ct else False,
            'is_rejected': ct.is_rejected if ct else False,
            'is_completed': ct.is_completed if ct else False,
            'present_count': s['present_cnt'] if s else 0,
            'absent_count': s['absent_cnt'] if s else 0,
            'total_students': s['total_cnt'] if s else 0,
            'is_marked': s is not None and s['total_cnt'] > 0,
            'marked_at_time': s['last_modified'] if s else None,
        })

    records.sort(key=lambda r: (r['date'], r['period']), reverse=True)
    return records


