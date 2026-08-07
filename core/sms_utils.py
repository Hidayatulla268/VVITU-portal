"""
VVIT Portal — SMS Notification Utility

Handles dispatching SMS notifications to parents for:
  1. Student Absence notifications when marked absent in a class.
  2. Exam Results release notifications with subject marks and percentage.
"""

import logging
from django.conf import settings

logger = logging.getLogger(__name__)


def send_sms(phone_number, message):
    """
    Simulate/Dispatch SMS notification to specified mobile number.
    In development/testing environments, logs the SMS message content cleanly.
    """
    if not phone_number:
        logger.warning("SMS Dispatch Skipped: Parent phone number missing.")
        return False

    cleaned_number = str(phone_number).strip()
    print(f"\n[SMS SENT] -> To: {cleaned_number}")
    print(f"Content: {message}\n")

    logger.info(f"SMS successfully dispatched to {cleaned_number}")
    return True


def send_absent_sms_to_parent(student, timetable_entry, date):
    """
    Dispatches an SMS notification to the student's parent when marked absent.
    """
    if not student or not student.parent_mobile:
        return False

    parent_name = student.parent_name or "Parent/Guardian"
    subject_code = timetable_entry.subject.code if (timetable_entry and timetable_entry.subject) else "Subject"
    subject_name = timetable_entry.subject.name if (timetable_entry and timetable_entry.subject) else "Class"
    period = timetable_entry.period if timetable_entry else ""
    date_str = date.strftime('%d-%b-%Y') if hasattr(date, 'strftime') else str(date)

    msg = (
        f"Dear {parent_name}, your ward {student.full_name} ({student.roll_number}) "
        f"was ABSENT for period {period} ({subject_code} - {subject_name}) on {date_str}. "
        f"- VVIT College Management"
    )

    return send_sms(student.parent_mobile, msg)


def send_result_sms_to_parent(student, exam, results_list):
    """
    Dispatches an SMS notification to the student's parent when exam results are published.
    """
    if not student or not student.parent_mobile:
        return False

    parent_name = student.parent_name or "Parent/Guardian"
    exam_name = exam.name if exam else "Exam"

    marks_summary = []
    total_obtained = 0
    total_max = 0
    for r in results_list:
        code = r.subject.code if r.subject else "SUB"
        obtained = float(r.marks_obtained)
        max_m = float(r.max_marks)
        total_obtained += obtained
        total_max += max_m
        marks_summary.append(f"{code}:{int(obtained)}/{int(max_m)}")

    pct = round(total_obtained / total_max * 100, 1) if total_max > 0 else 0
    marks_str = ", ".join(marks_summary)

    msg = (
        f"Dear {parent_name}, results released for {student.full_name} ({student.roll_number}) for {exam_name}. "
        f"Marks: {marks_str}. Overall: {pct}%. - VVIT Examination Cell"
    )

    return send_sms(student.parent_mobile, msg)
