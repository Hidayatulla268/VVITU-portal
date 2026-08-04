import os
import sys
import django

# Setup Django Environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'VVITU_Portal.settings')
django.setup()

from django.conf import settings
from django.core.mail import send_mail
from accounts.models import User, Student
from core.models import Branch, Year, Section, Subject, Exam, Result, ResultRelease
from admin_dashboard.views import _send_result_emails

def dispatch_shaik_hidayatulla_results():
    print("============================================================")
    print("  VVITU Portal — Student Result Mail Dispatcher")
    print("============================================================")

    sender_email = "hidayatullashaik2006@gmail.com"
    recipient_email = "hidayatullashaik268@gmail.com"
    first_name = "Shaik"
    last_name = "Hidayatulla"
    roll_num = "24BQ1A4901"

    # 1. Update / Create Student Account
    user_obj = User.objects.filter(username=roll_num).first()
    if not user_obj:
        user_obj = User.objects.filter(email=recipient_email).first()

    if user_obj:
        user_obj.first_name = first_name
        user_obj.last_name = last_name
        user_obj.email = recipient_email
        user_obj.role = 'student'
        user_obj.save()
    else:
        user_obj = User.objects.create_user(
            username=roll_num,
            email=recipient_email,
            first_name=first_name,
            last_name=last_name,
            role='student',
            password='vvit@1234'
        )

    branch = Branch.objects.filter(code='CSE').first() or Branch.objects.first()
    year = Year.objects.filter(year=2).first() or Year.objects.first()
    section = Section.objects.filter(branch=branch, year=year, name='A').first() or Section.objects.first()

    student_profile, _ = Student.objects.get_or_create(
        user=user_obj,
        defaults={
            'roll_number': roll_num,
            'branch': branch,
            'year': year,
            'section': section,
            'is_first_login': False
        }
    )
    student_profile.roll_number = roll_num
    student_profile.branch = branch
    student_profile.year = year
    student_profile.section = section
    student_profile.is_first_login = False
    student_profile.save()

    print(f"[OK] Student Account Configured:")
    print(f"     Name        : {user_obj.get_full_name()}")
    print(f"     Roll Number : {student_profile.roll_number}")
    print(f"     Email       : {user_obj.email}")
    print(f"     Section     : {student_profile.section}")

    # 2. Configure Exam & Realistic Academic Results
    exam, _ = Exam.objects.get_or_create(
        name="Semester End Examinations (Regular)",
        exam_type="SEM",
        branch=branch,
        year=year,
        semester=3
    )

    subjects = Subject.objects.filter(branch=branch, year=year, semester=3)
    if not subjects.exists():
        subjects = Subject.objects.filter(branch=branch, year=year)[:5]

    sample_marks = [
        ("Data Structures & Algorithms", 92, "O"),
        ("Computer Organization & Architecture", 88, "A+"),
        ("Database Management Systems", 95, "O"),
        ("Discrete Mathematical Structures", 90, "O"),
        ("Object Oriented Programming with Java", 91, "O"),
    ]

    for idx, sub in enumerate(subjects[:5]):
        sub_title, marks, grade = sample_marks[idx % len(sample_marks)]
        Result.objects.update_or_create(
            student=student_profile,
            exam=exam,
            subject=sub,
            defaults={
                'marks_obtained': marks,
                'max_marks': 100,
                'grade': grade
            }
        )

    print(f"\n[OK] Marks & Grades Configured for {exam.name}:")
    results = Result.objects.filter(student=student_profile, exam=exam).select_related('subject')
    for r in results:
        print(f"     - {r.subject.code} - {r.subject.name}: {r.marks_obtained}/100 ({r.grade})")

    # 3. Configure Sender Email
    settings.DEFAULT_FROM_EMAIL = f"VVITU Examination Cell <{sender_email}>"
    if not getattr(settings, 'EMAIL_HOST_USER', None):
        settings.EMAIL_HOST_USER = sender_email

    print(f"\n[OK] Sender Configuration:")
    print(f"     From        : {settings.DEFAULT_FROM_EMAIL}")
    print(f"     EMAIL_HOST  : {settings.EMAIL_HOST}:{settings.EMAIL_PORT}")
    print(f"     Backend     : {settings.EMAIL_BACKEND}")

    # 4. Construct & Display Email Body
    results_list = Result.objects.filter(student=student_profile, exam=exam).select_related('subject')
    total_obtained = sum(r.marks_obtained for r in results_list)
    total_max = sum(r.max_marks for r in results_list)
    pct = round((total_obtained / total_max) * 100, 2) if total_max > 0 else 0.0

    lines = []
    for r in results_list:
        lines.append(f"  - {r.subject.code:<10} | {r.subject.name:<38} | {r.marks_obtained:>3}/{r.max_marks} | Grade: {r.grade}")

    email_body = f"""Dear {user_obj.get_full_name()},

Your results for {exam.name} have been released by the Examination Cell.

Student Name : {user_obj.get_full_name()}
Roll Number  : {student_profile.roll_number}
Exam         : {exam.name}
Branch       : {branch.code} — {branch.name}
Year         : Year {year.year} | Semester : {exam.semester}

--------------------------------------------------
SUBJECT RESULTS
--------------------------------------------------
{chr(10).join(lines)}
--------------------------------------------------
Overall Marks      : {total_obtained} / {total_max}
Overall Percentage : {pct}%
--------------------------------------------------

You can also view your detailed grade card by logging into the VVITU Portal:
{settings.COLLEGE_WEBSITE}/student/results/

For any queries, please contact your class teacher or the controller of examinations.

Regards,
Controller of Examinations
{settings.COLLEGE_NAME}
{settings.COLLEGE_LOCATION}
"""

    print("\n============================================================")
    print("  EXACT RESULT EMAIL CONTENT GENERATED")
    print("============================================================")
    print(email_body)
    print("============================================================")

    # 5. Send Email via send_mail
    print(f"\nAttempting email dispatch from {sender_email} to {recipient_email}...")
    try:
        sent_count = send_mail(
            subject=f"[{settings.COLLEGE_SHORT}] Exam Results Released — {user_obj.get_full_name()} ({roll_num})",
            message=email_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient_email],
            fail_silently=False
        )
        print(f"[SUCCESS] Email successfully dispatched to {recipient_email}! (Count: {sent_count})")
    except Exception as e:
        print(f"[NOTE] Email prepared & rendered cleanly. (SMTP dispatch status: {e})")
        print(f"[TIP] To send live email over Google SMTP server, ensure EMAIL_HOST_PASSWORD (Gmail App Password) is provided in .env.")

if __name__ == '__main__':
    dispatch_shaik_hidayatulla_results()
