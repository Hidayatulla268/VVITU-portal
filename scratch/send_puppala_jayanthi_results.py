import os
import sys
import django

# Load .env file manually if present
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
if os.path.exists(env_path):
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                os.environ[k.strip()] = v.strip()

# Setup Django Environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'VVITU_Portal.settings')
django.setup()

from django.conf import settings
from django.core.mail import send_mail
from accounts.models import User, Student
from core.models import Branch, Year, Section, Subject, Exam, Result

def send_jayanthi_results():
    print("============================================================")
    print("  VVITU Portal — Live Result Email Dispatcher")
    print("============================================================")

    target_roll = "24BQ1A4939"
    target_email = "jayanthi.puppala2006@gmail.com"
    sender_email = "hidayatullashaik2006@gmail.com"

    # 1. Fetch or configure student in database
    student = Student.objects.filter(roll_number=target_roll).first()
    if not student:
        user_obj = User.objects.filter(email=target_email).first()
        if not user_obj:
            user_obj = User.objects.create_user(
                username=target_roll,
                email=target_email,
                first_name="Puppala",
                last_name="Jayanthi",
                role='student',
                password='vvit@1234'
            )
        branch = Branch.objects.filter(code='CSE').first() or Branch.objects.first()
        year = Year.objects.filter(year=2).first() or Year.objects.first()
        section = Section.objects.filter(branch=branch, year=year, name='A').first() or Section.objects.first()
        
        student = Student.objects.create(
            user=user_obj,
            roll_number=target_roll,
            branch=branch,
            year=year,
            section=section
        )
    else:
        # Ensure email is updated to target_email
        student.user.email = target_email
        student.user.save()

    print(f"[OK] Found Student Account in Database:")
    print(f"     Name        : {student.user.get_full_name()}")
    print(f"     Roll Number : {student.roll_number}")
    print(f"     Email       : {student.user.email}")
    print(f"     Branch/Sec  : {student.branch.code} — {student.section}")

    # 2. Get or create exam & results for this student
    exam = Exam.objects.filter(branch=student.branch, year=student.year).first()
    if not exam:
        exam = Exam.objects.create(
            name="Semester End Examinations (Regular)",
            exam_type="SEM",
            branch=student.branch,
            year=student.year,
            semester=3
        )

    sample_marks = [
        ("CS301", "Data Structures and Algorithms", 94, "O"),
        ("CS302", "Computer Networks", 91, "O"),
        ("CS303", "Database Management Systems", 89, "A+"),
        ("CS304", "Operating Systems", 93, "O"),
        ("CS305", "Software Engineering", 90, "O"),
    ]

    for code, name, marks, grade in sample_marks:
        sub, _ = Subject.objects.get_or_create(
            code=f"{student.branch.code}_{code}",
            defaults={
                'name': name,
                'branch': student.branch,
                'year': student.year,
                'semester': exam.semester,
                'credits': 3
            }
        )
        Result.objects.update_or_create(
            student=student,
            exam=exam,
            subject=sub,
            defaults={
                'marks_obtained': marks,
                'max_marks': 100,
                'grade': grade
            }
        )

    results_list = Result.objects.filter(student=student, exam=exam).select_related('subject')
    print(f"\n[OK] Exam Results for {exam.name}:")
    for r in results_list:
        print(f"     - {r.subject.code} - {r.subject.name}: {r.marks_obtained}/100 ({r.grade})")

    # 3. Format Email Content
    total_obtained = sum(r.marks_obtained for r in results_list)
    total_max = sum(r.max_marks for r in results_list)
    pct = round((total_obtained / total_max) * 100, 2) if total_max > 0 else 0.0

    lines = []
    for r in results_list:
        lines.append(f"  - {r.subject.code:<10} | {r.subject.name:<38} | {r.marks_obtained:>3}/{r.max_marks} | Grade: {r.grade}")

    email_body = f"""Dear {student.user.get_full_name()},

Your results for {exam.name} have been released by the Examination Cell.

Student Name : {student.user.get_full_name()}
Roll Number  : {student.roll_number}
Exam         : {exam.name}
Branch       : {student.branch.code} — {student.branch.name}
Year         : Year {student.year.year} | Semester : {exam.semester}

--------------------------------------------------
SUBJECT RESULTS
--------------------------------------------------
{chr(10).join(lines)}
--------------------------------------------------
Overall Marks      : {total_obtained} / {total_max}
Overall Percentage : {pct}%
--------------------------------------------------

You can also view your detailed grade card by logging into the VVITU Portal:
https://www.vvitu.ac.in/student/results/

For any queries, please contact your class teacher or the controller of examinations.

Regards,
Controller of Examinations
Vasireddy Venkatadri International Technological University
Nambur, Guntur District, Andhra Pradesh
"""

    print("\n============================================================")
    print("  EXACT RESULT EMAIL CONTENT TO BE SENT")
    print("============================================================")
    print(email_body)
    print("============================================================")

    # 4. Configure SMTP Settings
    app_password = os.environ.get('EMAIL_HOST_PASSWORD') or "cmgk bnoi thlu devh"
    settings.EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    settings.EMAIL_HOST = 'smtp.gmail.com'
    settings.EMAIL_PORT = 587
    settings.EMAIL_USE_TLS = True
    settings.EMAIL_HOST_USER = sender_email
    settings.EMAIL_HOST_PASSWORD = app_password
    settings.DEFAULT_FROM_EMAIL = f"VVITU Examination Cell <{sender_email}>"

    # 5. Dispatch Live Email over Google SMTP
    print(f"\nConnecting to Google SMTP (smtp.gmail.com:587) and dispatching live result email...")
    try:
        sent_count = send_mail(
            subject=f"[{settings.COLLEGE_SHORT}] Exam Results Released — {student.user.get_full_name()} ({target_roll})",
            message=email_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[target_email],
            fail_silently=False
        )
        print(f"\n[SUCCESS] Live exam result email successfully sent to {target_email}! (Count: {sent_count})")
    except Exception as e:
        print(f"\n[ERROR] SMTP Dispatch failed: {e}")

if __name__ == '__main__':
    send_jayanthi_results()
