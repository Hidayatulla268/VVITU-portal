import os
import sys
import django

# Setup Django Environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'VVITU_Portal.settings')
django.setup()

from accounts.models import User, Student
from core.models import Branch, Year, Section, Subject, Exam, Result
from core.sms_utils import send_result_notifications, build_result_email_body

def test_email_format():
    roll_num = "24BQ1A4901"
    student = Student.objects.filter(roll_number=roll_num).first()
    if not student:
        print("Student not found")
        return

    exam = Exam.objects.filter(branch=student.branch, year=student.year, exam_type='final').first()
    if not exam:
        print("Exam not found")
        return

    results_list = list(Result.objects.filter(student=student, exam=exam))
    
    print("============================================================")
    print("  GENERATED FORMATTED RESULT EMAIL BODY")
    print("============================================================")
    body = build_result_email_body(student, exam, results_list)
    print(body)
    print("============================================================")

    # Trigger full dispatch
    send_result_notifications(student=student, exam=exam, results_list=results_list)

if __name__ == '__main__':
    test_email_format()
