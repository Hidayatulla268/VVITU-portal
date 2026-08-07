import os
import sys
import django

# Setup Django Environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'VVITU_Portal.settings')
django.setup()

from accounts.models import User, Student
from core.models import Branch, Year, Section, Subject, Exam, Result, ResultRelease
from core.sms_utils import send_result_notifications

def dispatch_results_to_parent():
    print("============================================================")
    print("  VVITU Portal — Parent Result SMS Dispatcher")
    print("============================================================")

    roll_num = "24BQ1A4942"
    parent_mobile = "8121654552"

    # 1. Update / Create Student Account
    student = Student.objects.filter(roll_number__iexact=roll_num).first()

    if not student:
        user_obj = User.objects.filter(username__iexact=roll_num).first()
        if not user_obj:
            user_obj = User.objects.create_user(
                username=roll_num,
                email=f"{roll_num.lower()}@vvitu.net",
                first_name="Student",
                last_name=roll_num,
                role='student',
                password='vvit@1234'
            )
        branch = Branch.objects.filter(code='CSE').first() or Branch.objects.first()
        year = Year.objects.filter(year=2).first() or Year.objects.first()
        section = Section.objects.filter(branch=branch, year=year, name='A').first() or Section.objects.first()

        student = Student.objects.create(
            user=user_obj,
            roll_number=roll_num,
            branch=branch,
            year=year,
            section=section,
            parent_name="Parent of " + roll_num,
            parent_mobile=parent_mobile,
            personal_mobile=parent_mobile
        )
    else:
        student.parent_mobile = parent_mobile
        if not student.parent_name:
            student.parent_name = "Parent of " + roll_num
        student.save()

    print(f"[OK] Student Found/Configured:")
    print(f"     Student Name  : {student.user.get_full_name()}")
    print(f"     Roll Number   : {student.roll_number}")
    print(f"     Parent Mobile : {student.parent_mobile}")
    print(f"     Branch/Year   : {student.branch.code} — {student.year}")

    # 2. Get or Create Exam & Results
    exam = Exam.objects.filter(branch=student.branch, year=student.year, exam_type='final').first()
    if not exam:
        exam, _ = Exam.objects.get_or_create(
            name="Final Semester Examination 2026",
            exam_type="final",
            branch=student.branch,
            year=student.year,
            semester=3
        )

    # Ensure results exist for this student
    subjects = Subject.objects.filter(branch=student.branch, year=student.year)[:5]
    if not subjects.exists():
        subjects = Subject.objects.filter(branch=student.branch)[:5]

    for idx, sub in enumerate(subjects):
        marks = 85 + (idx * 3)
        grade = 'S' if marks >= 90 else ('A' if marks >= 80 else 'B')
        Result.objects.update_or_create(
            student=student,
            exam=exam,
            subject=sub,
            defaults={
                'marks_obtained': marks,
                'max_marks': 100,
                'grade': grade,
                'grade_points': 10 if grade == 'S' else (9 if grade == 'A' else 8)
            }
        )

    print(f"\n[OK] Exam Results Configured for {exam.name}")

    # 3. Mark Exam Results as Released
    ResultRelease.objects.update_or_create(
        exam=exam,
        defaults={'released': True, 'released_by': student.user}
    )

    # 4. Dispatch Result Notifications (Parent receives SMS with Grades & CGPA only!)
    print("\n[DISPATCHING RESULT NOTIFICATIONS]...")
    results_list = list(Result.objects.filter(student=student, exam=exam))
    res = send_result_notifications(student=student, exam=exam, results_list=results_list)
    print(f"\n[SUCCESS] Result Notifications Dispatched: {res}")
    print("============================================================")

if __name__ == '__main__':
    dispatch_results_to_parent()
