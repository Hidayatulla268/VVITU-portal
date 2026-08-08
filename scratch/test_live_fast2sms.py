import os
import sys
import django

# Setup Django Environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'VVITU_Portal.settings')
django.setup()

from accounts.models import Student
from core.models import Exam, Result
from core.sms_utils import send_result_notifications, send_sms

def test_live_sms():
    print("============================================================")
    print("  VVITU Portal — Live Fast2SMS Dispatcher Test")
    print("============================================================")

    mobile = "8121654552"
    msg = "VVITU Portal: Testing Live SMS Gateway integration. Semester Final Results released."

    print(f"[TEST 1] Direct Fast2SMS dispatch to {mobile}...")
    res = send_sms(mobile, msg)
    print(f"Direct send_sms result: {res}")

    print("\n[TEST 2] Full Result Notification dispatch to student 24BQ1A4942...")
    student = Student.objects.filter(roll_number="24BQ1A4942").first()
    if student:
        student.parent_mobile = mobile
        student.save()
        exam = Exam.objects.filter(branch=student.branch, year=student.year, exam_type='final').first()
        results_list = list(Result.objects.filter(student=student, exam=exam))
        if exam and results_list:
            dispatch_res = send_result_notifications(student, exam, results_list)
            print(f"send_result_notifications result: {dispatch_res}")

    print("============================================================")

if __name__ == '__main__':
    test_live_sms()
