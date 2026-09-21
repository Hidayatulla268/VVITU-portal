"""
VVIT Portal — Syllabus & Topic Plan Services

Provides syllabus progress aggregation, auto-matching with class diary logs,
milestone completion tracking (e.g. Mid-1 2.5 units target), and targeted
reminders sent strictly to Faculty and HOD (excluding Admin).
"""

import logging
import re
import datetime
from django.utils import timezone
from django.db.models import Q
from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


def get_subject_syllabus_progress(subject, faculty=None, section=None, preloaded_topics=None, preloaded_schedules=None, preloaded_diary_units=None):
    """
    Calculate comprehensive syllabus and topic schedule progress for a given subject.
    Accepts optional preloaded data to avoid N+1 queries when called in bulk.
    Returns:
      - total_topics: count of planned topics
      - completed_topics: count of completed topics
      - completion_pct: 0 to 100%
      - overdue_topics_count: count of incomplete topics past target date
      - unit_stats: detailed breakdown per Unit 1 to 5
      - units_completed_count: approximate completed units (0.0 to 5.0)
      - mid1_milestone: info about Mid-1 target (e.g. 2.5 units target)
      - mid2_milestone: info about Mid-2 target (5.0 units target)
      - is_mid1_target_met: bool
    """
    from core.models import SubjectTopicPlan, ExamSchedule, ClassDiary

    today = timezone.localdate()
    
    if preloaded_topics is not None:
        topic_plans = preloaded_topics
    else:
        topic_plans = list(SubjectTopicPlan.objects.filter(subject=subject).order_by('unit_number', 'order', 'target_date'))

    total_topics = len(topic_plans)
    completed_topics = len([t for t in topic_plans if t.is_completed])
    overdue_topics = [t for t in topic_plans if t.is_overdue]
    overdue_count = len(overdue_topics)

    # Unit-wise breakdown
    unit_stats = {}
    total_unit_weights = 0.0
    
    # Lazy-fetch diary units once if needed
    diary_units = preloaded_diary_units

    for u in [1, 2, 3, 4, 5]:
        u_topics = [t for t in topic_plans if t.unit_number == u]
        u_total = len(u_topics)
        u_done = len([t for t in u_topics if t.is_completed])
        
        if u_total > 0:
            u_pct = int(round((u_done / float(u_total)) * 100))
            u_fraction = round(u_done / float(u_total), 2)
        else:
            if diary_units is None:
                diary_units = set(ClassDiary.objects.filter(subject=subject).values_list('unit_number', flat=True).distinct())
            diary_exists = (u in diary_units)
            u_pct = 100 if diary_exists else 0
            u_fraction = 1.0 if diary_exists else 0.0
            u_total = 1 if diary_exists else 0
            u_done = 1 if diary_exists else 0

        total_unit_weights += u_fraction

        unit_stats[u] = {
            'unit_number': u,
            'unit_name': f"Unit {u}",
            'total_topics': u_total,
            'completed_topics': u_done,
            'progress_pct': u_pct,
            'fraction_done': u_fraction,
            'is_fully_done': (u_pct >= 100) and (u_total > 0),
            'has_topics': (len(u_topics) > 0),
        }

    # Units completed count (e.g., 2.5 units, 3.0 units out of 5.0)
    units_completed_count = min(5.0, round(total_unit_weights, 1))

    if total_topics > 0:
        completion_pct = int(round((completed_topics / float(total_topics)) * 100))
    else:
        completion_pct = int(round((units_completed_count / 5.0) * 100))

    # ── Exam Milestones (Mid-1 and Mid-2) ──
    if preloaded_schedules is not None:
        mid1_schedule = next((s for s in preloaded_schedules if (s.branch_id == subject.branch_id or s.branch_id is None) and s.year_id == subject.year_id and s.semester == subject.semester and s.exam_type == 'mid1'), None)
        mid2_schedule = next((s for s in preloaded_schedules if (s.branch_id == subject.branch_id or s.branch_id is None) and s.year_id == subject.year_id and s.semester == subject.semester and s.exam_type == 'mid2'), None)
    else:
        schedules = list(ExamSchedule.objects.filter(
            Q(branch=subject.branch) | Q(branch__isnull=True),
            year=subject.year,
            semester=subject.semester,
            exam_type__in=['mid1', 'mid2'],
            is_active=True
        ).order_by('-start_date'))
        mid1_schedule = next((s for s in schedules if s.exam_type == 'mid1'), None)
        mid2_schedule = next((s for s in schedules if s.exam_type == 'mid2'), None)

    mid1_target_units = float(mid1_schedule.target_units) if mid1_schedule else 2.5
    mid1_deadline = mid1_schedule.target_completion_date if mid1_schedule else None
    mid1_exam_date = mid1_schedule.start_date if mid1_schedule else None
    is_mid1_target_met = (units_completed_count >= mid1_target_units)

    mid2_target_units = float(mid2_schedule.target_units) if mid2_schedule else 5.0
    mid2_deadline = mid2_schedule.target_completion_date if mid2_schedule else None
    mid2_exam_date = mid2_schedule.start_date if mid2_schedule else None
    is_mid2_target_met = (units_completed_count >= mid2_target_units)

    # Status indicator string
    if is_mid1_target_met and (not mid2_deadline or today <= mid2_deadline):
        status_label = "On Schedule"
        status_color = "success"
    elif not is_mid1_target_met and mid1_deadline and today > mid1_deadline:
        status_label = "Mid-1 Milestone Delayed"
        status_color = "danger"
    elif overdue_count > 0:
        status_label = f"{overdue_count} Topic(s) Overdue"
        status_color = "warning"
    else:
        status_label = "In Progress"
        status_color = "info"

    # Avoid triggering lazy N+1 query if subject.faculty is not preloaded
    fac_obj = faculty
    if not fac_obj and hasattr(subject, '_state') and 'faculty' in getattr(subject._state, 'fields_cache', {}):
        fac_obj = subject.faculty

    return {
        'subject': subject,
        'faculty': fac_obj,
        'total_topics': total_topics,
        'completed_topics': completed_topics,
        'completion_pct': completion_pct,
        'overdue_topics': overdue_topics,
        'overdue_count': overdue_count,
        'unit_stats': unit_stats,
        'units_completed_count': units_completed_count,
        'mid1_schedule': mid1_schedule,
        'mid1_target_units': mid1_target_units,
        'mid1_deadline': mid1_deadline,
        'mid1_exam_date': mid1_exam_date,
        'is_mid1_target_met': is_mid1_target_met,
        'mid2_schedule': mid2_schedule,
        'mid2_target_units': mid2_target_units,
        'mid2_deadline': mid2_deadline,
        'mid2_exam_date': mid2_exam_date,
        'is_mid2_target_met': is_mid2_target_met,
        'status_label': status_label,
        'status_color': status_color,
    }


def get_batch_subject_syllabus_progress(subjects, preloaded_diaries=None, active_schedules=None):
    """
    Bulk computes syllabus progress for an iterable of subjects in only 2-3 queries total,
    returning a dictionary {subject_id: progress_dict}.
    """
    from collections import defaultdict
    from core.models import SubjectTopicPlan, ExamSchedule, ClassDiary

    subj_list = list(subjects)
    if not subj_list:
        return {}

    subj_ids = [s.id for s in subj_list]

    # 1. Fetch active exam schedules once if not provided
    if active_schedules is None:
        active_schedules = list(ExamSchedule.objects.filter(is_active=True).order_by('-start_date'))

    # 2. Fetch all topic plans for all subjects in one query
    topic_plans_all = list(
        SubjectTopicPlan.objects.filter(subject_id__in=subj_ids)
        .order_by('unit_number', 'order', 'target_date')
    )
    topic_plans_by_subj = defaultdict(list)
    for tp in topic_plans_all:
        topic_plans_by_subj[tp.subject_id].append(tp)

    # 3. Diary units lookup
    diary_units_by_subj = defaultdict(set)
    if preloaded_diaries is not None:
        for d in preloaded_diaries:
            s_id = d.get('subject_id') if isinstance(d, dict) else d.subject_id
            u_num = d.get('unit_number') if isinstance(d, dict) else d.unit_number
            diary_units_by_subj[s_id].add(u_num)
    else:
        # Check units from DB for subjects that have zero planned topics
        subjects_needing_diary = [s_id for s_id in subj_ids if len(topic_plans_by_subj[s_id]) == 0]
        if subjects_needing_diary:
            d_records = ClassDiary.objects.filter(subject_id__in=subjects_needing_diary).values('subject_id', 'unit_number')
            for r in d_records:
                diary_units_by_subj[r['subject_id']].add(r['unit_number'])

    progress_map = {}
    for subj in subj_list:
        progress_map[subj.id] = get_subject_syllabus_progress(
            subj,
            preloaded_topics=topic_plans_by_subj[subj.id],
            preloaded_schedules=active_schedules,
            preloaded_diary_units=diary_units_by_subj[subj.id]
        )

    return progress_map


def auto_match_and_complete_topic(subject, topic_text, unit_number=1, faculty=None, diary_entry=None, date=None):
    """
    Given a topic covered text and unit number from Class Diary or Attendance:
    Searches SubjectTopicPlan for an uncompleted topic matching the text or sequence,
    marks it completed, and links the class diary entry.
    """
    from core.models import SubjectTopicPlan

    if not subject or not topic_text:
        return None

    clean_text = topic_text.strip().lower()
    comp_date = date or timezone.localdate()

    # 1. Search in the specified unit first
    unit_candidates = SubjectTopicPlan.objects.filter(
        subject=subject,
        unit_number=unit_number,
        is_completed=False
    ).order_by('order', 'target_date')

    matched_topic = None

    # Check for direct or substring match
    for t in unit_candidates:
        t_name_lower = t.topic_name.lower()
        if t_name_lower in clean_text or clean_text in t_name_lower:
            matched_topic = t
            break

    # If no substring match, check keyword overlap
    if not matched_topic:
        text_words = set(re.findall(r'\w{3,}', clean_text))
        for t in unit_candidates:
            topic_words = set(re.findall(r'\w{3,}', t.topic_name.lower()))
            overlap = text_words.intersection(topic_words)
            if len(overlap) >= 2 or (len(topic_words) == 1 and len(overlap) == 1):
                matched_topic = t
                break

    # If still not matched, check across all units for exact phrase
    if not matched_topic:
        all_candidates = SubjectTopicPlan.objects.filter(
            subject=subject,
            is_completed=False
        ).order_by('unit_number', 'order')
        for t in all_candidates:
            if t.topic_name.lower() in clean_text or clean_text in t.topic_name.lower():
                matched_topic = t
                break

    if matched_topic:
        matched_topic.is_completed = True
        matched_topic.completed_date = comp_date
        if faculty:
            matched_topic.completed_by = faculty
        if diary_entry:
            matched_topic.class_diary_entry = diary_entry
        matched_topic.save()
        logger.info(f"Auto-matched and marked topic completed: '{matched_topic.topic_name}' for subject {subject.code}")
        return matched_topic

    return None


def check_and_dispatch_syllabus_reminders(subject_id=None, branch_id=None, triggered_by=None):
    """
    Scans for overdue topics and incomplete syllabus milestones.
    Dispatches notifications strictly to:
      1. Assigned Faculty
      2. Department HOD
    CRITICAL: Admin does NOT receive these routine syllabus delay notifications.
    """
    from core.models import Subject, SubjectTopicPlan, Notification, Timetable, ExamSchedule
    from accounts.models import User, Faculty
    from core.sms_utils import send_sms

    today = timezone.localdate()
    subjects_qs = Subject.objects.filter(is_deleted=False)
    if subject_id:
        subjects_qs = subjects_qs.filter(id=subject_id)
    if branch_id:
        subjects_qs = subjects_qs.filter(branch_id=branch_id)

    reminders_sent = 0
    faculty_notified = set()
    hod_notified = set()

    for subj in subjects_qs.select_related('branch', 'year', 'faculty__user'):
        dept = subj.branch
        stats = get_subject_syllabus_progress(subj)

        overdue_topics = stats['overdue_topics']
        is_mid1_behind = (not stats['is_mid1_target_met']) and stats['mid1_deadline'] and (today >= stats['mid1_deadline'] or (stats['mid1_deadline'] - today).days <= 3)

        if not overdue_topics and not is_mid1_behind:
            continue

        # Find instructors teaching this subject
        assigned_faculties = set()
        if subj.faculty:
            assigned_faculties.add(subj.faculty)
        tt_facs = Faculty.objects.filter(timetable__subject=subj, is_active=True)
        for tf in tt_facs:
            assigned_faculties.add(tf)

        # Department HODs
        hod_users = User.objects.filter(role='hod')
        if dept:
            dept_hods = hod_users.filter(faculty_profile__department=dept)
            if dept_hods.exists():
                hod_users = dept_hods

        # Build notification messages
        overdue_names = ", ".join([f"'{t.topic_name}' (U{t.unit_number})" for t in overdue_topics[:3]])
        if len(overdue_topics) > 3:
            overdue_names += f" and {len(overdue_topics) - 3} more"

        milestone_text = ""
        if is_mid1_behind:
            milestone_text = f" Required Mid-1 target is {stats['mid1_target_units']} units (currently {stats['units_completed_count']} units covered)."

        # ── 1. Dispatch to Faculty ──
        fac_title = f"⚠️ Syllabus Action Required: {subj.code} — {subj.short_name}"
        fac_msg = (
            f"Syllabus Schedule Reminder for {subj.name} ({subj.code}): "
            f"You have {len(overdue_topics)} topic(s) pending beyond their target date: {overdue_names}.{milestone_text} "
            f"Please update your daily class diary and complete the topics."
        )

        for fac in assigned_faculties:
            if not fac or not fac.user:
                continue
            fac_key = (fac.id, subj.id)
            if fac_key not in faculty_notified:
                faculty_notified.add(fac_key)
                # In-App Notification
                Notification.objects.create(
                    title=fac_title,
                    message=fac_msg,
                    notif_type=Notification.TYPE_ANNOUNCEMENT,
                    priority=Notification.PRIORITY_HIGH,
                    target_user=fac.user,
                    target_role='faculty',
                    target_all=False,
                    created_by=triggered_by
                )
                reminders_sent += 1

                # Email
                if fac.user.email:
                    try:
                        send_mail(
                            subject=f"[VVITU Syllabus Alert] {fac_title}",
                            message=fac_msg,
                            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@vvitu.ac.in'),
                            recipient_list=[fac.user.email],
                            fail_silently=True
                        )
                    except Exception as mail_err:
                        logger.warning(f"Failed to send email to faculty: {mail_err}")

                # SMS
                if fac.phone:
                    try:
                        sms_text = f"VVITU ALERT: {len(overdue_topics)} topic(s) pending for {subj.code}. Please update class diary before Mid-1 exam."
                        send_sms(fac.phone, sms_text)
                    except Exception as sms_err:
                        logger.warning(f"Failed to send SMS to faculty: {sms_err}")

        # ── 2. Dispatch to Department HOD ──
        fac_names = ", ".join([f.full_name for f in assigned_faculties if f]) or "Faculty"
        hod_title = f"⚠️ Syllabus Delay Alert: {subj.code} ({fac_names})"
        hod_msg = (
            f"Department Syllabus Alert for {dept.code} — {subj.name} ({subj.code}): "
            f"Faculty {fac_names} has {len(overdue_topics)} overdue topic(s): {overdue_names}.{milestone_text} "
            f"Overall progress: {stats['completion_pct']}% ({stats['units_completed_count']}/5.0 units)."
        )

        for hod_user in hod_users:
            hod_key = (hod_user.id, subj.id)
            if hod_key not in hod_notified:
                hod_notified.add(hod_key)
                Notification.objects.create(
                    title=hod_title,
                    message=hod_msg,
                    notif_type=Notification.TYPE_ANNOUNCEMENT,
                    priority=Notification.PRIORITY_HIGH,
                    target_user=hod_user,
                    target_role='hod',
                    target_all=False,
                    created_by=triggered_by
                )
                reminders_sent += 1

                if hod_user.email:
                    try:
                        send_mail(
                            subject=f"[VVITU HOD Alert] {hod_title}",
                            message=hod_msg,
                            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@vvitu.ac.in'),
                            recipient_list=[hod_user.email],
                            fail_silently=True
                        )
                    except Exception as mail_err:
                        logger.warning(f"Failed to send email to HOD: {mail_err}")

    logger.info(f"check_and_dispatch_syllabus_reminders dispatched {reminders_sent} notifications (strictly Faculty + HOD).")
    return reminders_sent
