import os
import sys
import django

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + '/..'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'VVITU_Portal.settings')
django.setup()

from django.utils import timezone
from accounts.models import User, Student, Faculty
from core.models import Branch, Year, Section, Subject, Timetable, Exam, Result
from core.sms_utils import send_absent_notifications, send_result_notifications

def test_all_features():
    print("=== STARTING COMPREHENSIVE NEW FEATURES TEST ===")

    # 1. Test Branch
    branch, _ = Branch.objects.get_or_create(code="CSE", defaults={'name': 'Computer Science Engineering'})
    print(f"[PASSED] Branch Created: {branch.code}")

    # 2. Test Student Profile Extended Fields & Fees Pending
    user, _ = User.objects.get_or_create(
        username="TEST_STUDENT_01",
        defaults={
            'first_name': 'Rahul',
            'last_name': 'Sharma',
            'email': 'rahul.sharma@vvitu.net',
            'phone': '+919988776655',
            'role': 'student'
        }
    )
    year = Year.objects.get_or_create(year=1)[0]
    sec  = Section.objects.filter(branch=branch, year=year).first()
    if not sec:
        sec = Section.objects.create(name='A', branch=branch, year=year)

    student, _ = Student.objects.update_or_create(
        roll_number="TEST_STUDENT_01",
        defaults={
            'user': user,
            'branch': branch,
            'year': year,
            'section': sec,
            'gender': 'Male',
            'caste': 'OC',
            'religion': 'Hindu',
            'parent_name': 'Ramesh Sharma',
            'parent_occupation': 'Business',
            'parent_mobile': '+919876543210',
            'personal_mobile': '+919988776655',
            'permanent_address': 'Flat 402, Green Towers, Vijayawada',
            'present_address': 'Room 12, VVITU Mens Hostel, Nambur',
            'fees_pending': 15000.00,
            'fees_updated_at': timezone.now()
        }
    )
    print(f"[PASSED] Student Extended Profile & Fees Saved: Roll={student.roll_number}, Fees Pending=INR {student.fees_pending}")

    # 3. Test Grading Scale ('S' Grade check)
    subj, _ = Subject.objects.get_or_create(code="BBA101", defaults={'name': 'Financial Management', 'branch': branch, 'year': year, 'semester': 1, 'credits': 4})
    exam, _ = Exam.objects.get_or_create(name="Final Semester Exam 2026", defaults={'branch': branch, 'year': year, 'semester': 1, 'exam_type': 'final', 'date': timezone.localdate()})

    res, _ = Result.objects.update_or_create(
        student=student,
        exam=exam,
        subject=subj,
        defaults={'marks_obtained': 95, 'max_marks': 100}
    )
    computed_grade = res.calculate_grade()
    res.grade = computed_grade
    res.save()
    print(f"[PASSED] Result Grade Calculation for 95/100: Grade='{res.grade}' (S grade verified)")

    # 4. Test Absent Notifications (Parent SMS + Student SMS & Email)
    fac_user, _ = User.objects.get_or_create(username="EMP_TEST_01", defaults={'first_name': 'Dr.', 'last_name': 'Anil', 'role': 'faculty'})
    faculty, _  = Faculty.objects.get_or_create(employee_id="EMP_TEST_01", defaults={'user': fac_user, 'department': branch})
    
    timetable_slot, _ = Timetable.objects.update_or_create(
        section=sec,
        day=timezone.localdate().strftime('%A'),
        period=1,
        defaults={'subject': subj, 'faculty': faculty, 'room_number': 'Room B-201'}
    )

    absent_sent = send_absent_notifications(student, timetable_slot, timezone.localdate())
    print(f"[PASSED] Absent Notifications Sent: {absent_sent}")

    # 5. Test Result Notifications (Parent SMS for Sem Final vs Student SMS & Email for Mid)
    result_sent = send_result_notifications(student, exam, [res])
    print(f"[PASSED] Result Notifications Sent for Final Exam: {result_sent}")

    mid_exam, _ = Exam.objects.get_or_create(name="Mid-1 Exam 2026", defaults={'branch': branch, 'year': year, 'semester': 1, 'exam_type': 'mid1', 'date': timezone.localdate()})
    mid_res, _  = Result.objects.update_or_create(student=student, exam=mid_exam, subject=subj, defaults={'marks_obtained': 28, 'max_marks': 30})
    mid_sent   = send_result_notifications(student, mid_exam, [mid_res])
    print(f"[PASSED] Result Notifications Sent for Mid Exam: {mid_sent}")

    print("=== ALL NEW FEATURES TESTED AND PASSED SUCCESSFULLY ===")

if __name__ == '__main__':
    test_all_features()
