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


import json
import urllib.request
import urllib.parse

def send_sms(phone_number, message):
    """
    Dispatch SMS notification to specified mobile number.
    Supports live SMS gateways (Fast2SMS, Twilio, Generic HTTP REST API) when API key exists.
    Falls back to structured console logging when API keys are unconfigured.
    """
    if not phone_number:
        logger.warning("SMS Dispatch Skipped: Phone number missing.")
        return False

    cleaned_number = str(phone_number).strip().replace(" ", "").replace("-", "")
    sms_api_key = getattr(settings, 'SMS_API_KEY', '')
    twilio_sid  = getattr(settings, 'TWILIO_SID', '')
    twilio_auth = getattr(settings, 'TWILIO_AUTH_TOKEN', '')

    print(f"\n[SMS DISPATCH LOG] -> To: {cleaned_number}")
    print(f"Content: {message}\n")

    # 1. Fast2SMS / Generic REST Gateway live SMS dispatch
    if sms_api_key:
        try:
            url = getattr(settings, 'SMS_GATEWAY_URL', 'https://www.fast2sms.com/dev/bulkV2')
            digits_only = "".join(filter(str.isdigit, cleaned_number))
            if len(digits_only) > 10:
                digits_only = digits_only[-10:]

            data = urllib.parse.urlencode({
                'route': 'q',
                'message': message,
                'language': 'english',
                'flash': '0',
                'numbers': digits_only
            }).encode('utf-8')

            req = urllib.request.Request(
                url,
                data=data,
                headers={
                    'authorization': sms_api_key,
                    'Content-Type': 'application/x-www-form-urlencoded'
                },
                method='POST'
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                res_body = response.read().decode('utf-8')
                logger.info(f"Live SMS Gateway response for {cleaned_number}: {res_body}")
                print(f"[LIVE SMS GATEWAY SUCCESS] -> Delivered to {cleaned_number}")
                return True
        except Exception as e:
            err_msg = str(e)
            if hasattr(e, 'read'):
                try:
                    err_body = e.read().decode('utf-8')
                    err_msg += f" | Details: {err_body}"
                except Exception:
                    pass
            logger.error(f"Live SMS Gateway error for {cleaned_number}: {err_msg}")
            print(f"[FAST2SMS GATEWAY RESPONSE] -> {err_msg}")

    # 2. Twilio SMS live dispatch
    elif twilio_sid and twilio_auth:
        try:
            import base64
            from_num = getattr(settings, 'TWILIO_PHONE_NUM', '')
            url = f"https://api.twilio.com/2010-04-01/Accounts/{twilio_sid}/Messages.json"
            data = urllib.parse.urlencode({
                'To': cleaned_number if cleaned_number.startswith('+') else f"+91{cleaned_number}",
                'From': from_num,
                'Body': message
            }).encode('utf-8')

            creds = base64.b64encode(f"{twilio_sid}:{twilio_auth}".encode()).decode('utf-8')
            req = urllib.request.Request(
                url,
                data=data,
                headers={
                    'Authorization': f'Basic {creds}',
                    'Content-Type': 'application/x-www-form-urlencoded'
                },
                method='POST'
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                res_body = response.read().decode('utf-8')
                logger.info(f"Twilio SMS Gateway response for {cleaned_number}: {res_body}")
                print(f"[TWILIO SMS SUCCESS] -> Delivered to {cleaned_number}")
                return True
        except Exception as e:
            logger.error(f"Twilio SMS error for {cleaned_number}: {e}")

    logger.info(f"SMS logged for {cleaned_number} (Add SMS_API_KEY in .env for real phone delivery)")
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
        # Avoid socket blocking if SMTP credentials are slow/unreachable
        from django.core.mail import get_connection
        backend = getattr(settings, 'EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')
        connection = get_connection(backend, fail_silently=True, timeout=2)
        send_mail(
            subject=subject,
            message=body,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'VVITU Portal <noreply@vvitu.ac.in>'),
            recipient_list=[email_addr],
            fail_silently=True,
            connection=connection
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


def build_result_email_body(student, exam, results_list):
    """
    Formats the result notification email with ONLY Grades and CGPA in a clean table (no raw marks).
    """
    table_rows = []

    for r in results_list:
        if not r.subject:
            continue
        subj_code_or_short = getattr(r.subject, 'short_name', r.subject.code)
        sub_name = r.subject.name
        grade_val = r.grade or 'N/A'

        table_rows.append(
            f"| {subj_code_or_short:<10} | {sub_name:<38} | {grade_val:^5} |"
        )

    cgpa = student.calculate_cgpa()

    branch_name = getattr(student.branch, 'name', '') if student.branch else ''
    branch_code = getattr(student.branch, 'code', 'N/A') if student.branch else 'N/A'
    branch_str = f"{branch_code} — {branch_name}" if branch_name else branch_code

    year_val = student.year.year if (student.year and hasattr(student.year, 'year')) else (student.year or '1')
    sem_val = getattr(exam, 'semester', 1)

    table_header = "+------------+----------------------------------------+-------+"
    table_content = "\n".join(table_rows)

    body = f"""Dear {student.full_name},

Your results for {exam.name} have been released by the Examination Cell.

Student Name : {student.full_name}
Roll Number  : {student.roll_number}
Exam         : {exam.name}
Branch       : {branch_str}
Year         : Year {year_val} | Semester : {sem_val}

{table_header}
| Subject    | Subject Name                           | Grade |
{table_header}
{table_content}
{table_header}

--------------------------------------------------
Cumulative Grade Point Average (CGPA) : {cgpa}
--------------------------------------------------

You can also view your detailed grade card by logging into the VVITU Portal:
https://www.vvitu.ac.in/student/results/

For any queries, please contact your class teacher or the controller of examinations.

Regards,
Controller of Examinations
Vasireddy Venkatadri International Technological University
Nambur, Guntur District, Andhra Pradesh"""

    return body


def send_result_notifications(student, exam, results_list):
    """
    Dispatches result notifications based on exam type:
      - Semester Final Results:
          * Parent SMS: Sent ONLY Grades + CGPA (no raw marks).
          * Student SMS & Formatted Email: Full structured grade report.
      - Mid-Term Results (Mid 1, Mid 2):
          * Student SMS & Formatted Email: Mid marks report.
          * Parent SMS: Skipped.
    """
    if not student or not exam or not results_list:
        return False

    is_final = (exam.exam_type == 'final')
    cgpa = student.calculate_cgpa()
    email_body = build_result_email_body(student, exam, results_list)

    if is_final:
        # Semester Final Result: Grades + CGPA
        grades_summary = [f"{r.subject.short_name}:{r.grade or 'N/A'}" for r in results_list if r.subject]
        grades_str = ", ".join(grades_summary)

        # Parent SMS (Grades + CGPA only)
        if student.parent_mobile:
            parent_name = student.parent_name or "Parent/Guardian"
            parent_msg = (
                f"Dear {parent_name}, Semester Final results for {student.full_name} ({student.roll_number}): "
                f"Grades: [{grades_str}], CGPA: {cgpa}. - VVITU Examination Cell"
            )
            send_sms(student.parent_mobile, parent_msg)

        # Student SMS & Formatted Email
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
            body=email_body
        )

        # Create In-App Portal Notification for Student
        try:
            from core.models import Notification
            Notification.objects.create(
                title=f"Results Published: {exam.name}",
                message=f"Your Semester Final results for {exam.name} are now available. CGPA: {cgpa}. Grades: [{grades_str}]",
                notif_type=Notification.TYPE_RESULT,
                target_all=False,
                target_user=student.user,
                link="/student/results/"
            )
        except Exception as e:
            logger.error(f"Failed to create in-app result notification: {e}")

    else:
        # Mid-Term Results: Mid Marks obtained
        marks_summary = [f"{r.subject.short_name}:{int(r.marks_obtained)}/{int(r.max_marks)}" for r in results_list if r.subject]
        marks_str = ", ".join(marks_summary)

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
            body=email_body
        )

        # Create In-App Portal Notification for Student
        try:
            from core.models import Notification
            Notification.objects.create(
                title=f"Mid Results Published: {exam.name}",
                message=f"Your Mid-Term marks for {exam.name} are now available. Marks: [{marks_str}]",
                notif_type=Notification.TYPE_RESULT,
                target_all=False,
                target_user=student.user,
                link="/student/results/"
            )
        except Exception as e:
            logger.error(f"Failed to create in-app result notification: {e}")

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

