"""
VVIT Portal — Notification & Communication Utility

Handles dispatching SMS and Email notifications:
  1. Absent alerts: Parent SMS (absent only) + Student SMS & Email.
  2. Exam Results:
     - Semester Final Results: Parent SMS (Grades + CGPA only) + Student SMS & Email.
     - Mid-Term Results: Student SMS & Email (Mid marks obtained). Parents do NOT receive Mid SMS.
  3. Low Attendance Alerts: Student SMS & Email.
  4. General Notices: Student SMS & Email.
"""

import logging
from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


def send_sms(phone_number, message):
    """
    Simulate/Dispatch SMS notification to specified mobile number.
    In development/testing environments, logs the SMS message content cleanly.
    """
    if not phone_number:
        logger.warning("SMS Dispatch Skipped: Phone number missing.")
        return False

    cleaned_number = str(phone_number).strip()
    print(f"\n[SMS DISPATCHED] -> To: {cleaned_number}")
    print(f"Content: {message}\n")

    logger.info(f"SMS successfully dispatched to {cleaned_number}")
    return True


def send_email_to_student(student, subject, body):
    """
    Dispatches an email notification to the student's institutional email address.
    """
    if not student or not student.user or not student.user.email:
        logger.warning("Email Dispatch Skipped: Student email missing.")
        return False

    email_addr = student.user.email.strip()
    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'VVITU Portal <noreply@vvitu.ac.in>'),
            recipient_list=[email_addr],
            fail_silently=True,
        )
        print(f"\n[EMAIL SENT] -> To: {email_addr}")
        print(f"Subject: {subject}\nBody: {body}\n")
        return True
    except Exception as e:
        logger.error(f"Email dispatch error for {email_addr}: {e}")
        return False


def send_absent_notifications(student, timetable_entry, date):
    """
    Dispatches absent notifications:
      - Parent SMS: Strictly sent to student.parent_mobile.
      - Student SMS & Email: Sent to student's personal mobile and email.
    """
    if not student:
        return False

    parent_name = student.parent_name or "Parent/Guardian"
    subject_code = timetable_entry.subject.code if (timetable_entry and timetable_entry.subject) else "Subject"
    subject_name = timetable_entry.subject.name if (timetable_entry and timetable_entry.subject) else "Class"
    period = timetable_entry.period if timetable_entry else ""
    date_str = date.strftime('%d-%b-%Y') if hasattr(date, 'strftime') else str(date)

    # 1. Parent SMS (Absent Alert)
    if student.parent_mobile:
        parent_msg = (
            f"Dear {parent_name}, your ward {student.full_name} ({student.roll_number}) "
            f"was marked ABSENT for period {period} ({subject_code} - {subject_name}) on {date_str}. "
            f"- VVITU College Management"
        )
        send_sms(student.parent_mobile, parent_msg)

    # 2. Student Personal SMS & Email (Absent Alert)
    student_msg = (
        f"Dear {student.full_name}, you were marked ABSENT for period {period} "
        f"({subject_code} - {subject_name}) on {date_str}. If this is an error, contact your class teacher."
    )
    student_phone = student.personal_mobile or student.phone
    if student_phone:
        send_sms(student_phone, student_msg)

    send_email_to_student(
        student=student,
        subject=f"[Attendance Alert] Absent for {subject_code} on {date_str}",
        body=student_msg
    )
    return True


def send_result_notifications(student, exam, results_list):
    """
    Dispatches result notifications based on exam type:
      - Semester Final Results:
          * Parent SMS: Sent ONLY Grades + CGPA (no raw marks).
          * Student SMS & Email: Grades + CGPA overview.
      - Mid-Term Results (Mid 1, Mid 2):
          * Student SMS & Email: Mid marks obtained per subject.
          * Parent SMS: Skipped (Parents only receive absent alerts & sem final results).
    """
    if not student or not exam or not results_list:
        return False

    is_final = (exam.exam_type == 'final')
    cgpa = student.calculate_cgpa()

    if is_final:
        # Semester Final Result: Grades + CGPA
        grades_summary = [f"{r.subject.code}:{r.grade or 'N/A'}" for r in results_list if r.subject]
        grades_str = ", ".join(grades_summary)

        # Parent SMS (Grades + CGPA only)
        if student.parent_mobile:
            parent_name = student.parent_name or "Parent/Guardian"
            parent_msg = (
                f"Dear {parent_name}, Semester Final results for {student.full_name} ({student.roll_number}): "
                f"Grades: [{grades_str}], CGPA: {cgpa}. - VVITU Examination Cell"
            )
            send_sms(student.parent_mobile, parent_msg)

        # Student SMS & Email
        student_msg = (
            f"Dear {student.full_name} ({student.roll_number}), your Semester Final results for {exam.name} "
            f"have been published. Grades: [{grades_str}], CGPA: {cgpa}. Log in to view details."
        )
        student_phone = student.personal_mobile or student.phone
        if student_phone:
            send_sms(student_phone, student_msg)

        send_email_to_student(
            student=student,
            subject=f"[Exam Results Published] {exam.name} Semester Results",
            body=student_msg
        )

    else:
        # Mid-Term Results: Mid Marks obtained
        marks_summary = [f"{r.subject.code}:{int(r.marks_obtained)}/{int(r.max_marks)}" for r in results_list if r.subject]
        marks_str = ", ".join(marks_summary)

        # Mid results sent to Student SMS & Email ONLY (Parents do not receive mid results)
        student_msg = (
            f"Dear {student.full_name} ({student.roll_number}), your Mid-Term marks for {exam.name} "
            f"are released. Marks: [{marks_str}]. Log in to your portal for performance insights."
        )
        student_phone = student.personal_mobile or student.phone
        if student_phone:
            send_sms(student_phone, student_msg)

        send_email_to_student(
            student=student,
            subject=f"[Exam Results Published] {exam.name} Mid Marks",
            body=student_msg
        )

    return True


def send_low_attendance_alert(student, attendance_pct):
    """
    Dispatches low attendance alerts (<75%) to student's personal mobile and email.
    """
    if not student:
        return False

    msg = (
        f"Dear {student.full_name} ({student.roll_number}), your overall attendance is currently {attendance_pct}%, "
        f"which is below the mandatory 75% threshold. Please meet your counsellor immediately."
    )

    student_phone = student.personal_mobile or student.phone
    if student_phone:
        send_sms(student_phone, msg)

    send_email_to_student(
        student=student,
        subject="[Important] Low Attendance Alert (<75%)",
        body=msg
    )
    return True


# Backward-compatibility function aliases
send_absent_sms_to_parent = send_absent_notifications
send_result_sms_to_parent = send_result_notifications

