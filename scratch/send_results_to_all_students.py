import os
import sys
import django

# Setup Django Environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'VVITU_Portal.settings')
django.setup()

from accounts.models import Student
from core.models import Exam, Result, ResultRelease, Subject
from core.sms_utils import send_result_notifications

def dispatch_results_to_all():
    print("============================================================")
    print("  VVITU Portal — Mass Result Dispatcher (All Students & Parents)")
    print("============================================================")

    students = list(Student.objects.select_related('user', 'branch', 'year', 'section').all())
    print(f"[INFO] Found {len(students)} total students in database.\n")

    if not students:
        print("[WARNING] No students found in database.")
        return

    # Ensure an exam and results exist for each branch/year combo
    dispatched_count = 0

    for idx, student in enumerate(students, start=1):
        print(f"[{idx}/{len(students)}] Processing Student: {student.roll_number} ({student.full_name})")

        # 1. Fetch or create exam for student's branch/year
        exam = Exam.objects.filter(branch=student.branch, year=student.year, exam_type='final').first()
        if not exam:
            exam, _ = Exam.objects.get_or_create(
                name=f"{student.branch.code} Semester Final Exam 2026",
                exam_type="final",
                branch=student.branch,
                year=student.year,
                semester=3
            )

        # 2. Mark exam release status
        ResultRelease.objects.update_or_create(
            exam=exam,
            defaults={'released': True, 'released_by': student.user}
        )

        # 3. Ensure student has results for subjects in their branch/year
        subjects = list(Subject.objects.filter(branch=student.branch, year=student.year)[:5])
        if not subjects:
            subjects = list(Subject.objects.filter(branch=student.branch)[:5])

        for sub_idx, sub in enumerate(subjects):
            marks = 80 + ((sub_idx * 5 + idx * 3) % 20)
            grade = 'S' if marks >= 90 else ('A' if marks >= 80 else 'B')
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

        # 4. Fetch results list and dispatch notifications to student & parent
        results_list = list(Result.objects.filter(student=student, exam=exam))
        success = send_result_notifications(student=student, exam=exam, results_list=results_list)
        if success:
            dispatched_count += 1

    print("\n============================================================")
    print(f"  MASS DISPATCH COMPLETE")
    print(f"  Total Students Processed : {len(students)}")
    print(f"  Successful Dispatches    : {dispatched_count}")
    print("============================================================")

if __name__ == '__main__':
    dispatch_results_to_all()
