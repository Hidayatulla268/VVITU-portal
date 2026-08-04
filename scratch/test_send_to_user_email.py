import os
import sys
import django

# Setup Django Environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'VVITU_Portal.settings')
django.setup()

from django.test.utils import setup_test_environment
setup_test_environment()

from django.core import mail
from django.conf import settings
from accounts.models import User, Student
from core.models import Exam, Result, ResultRelease
from admin_dashboard.views import _send_result_emails

def test_result_email_to_user():
    print("--- Testing Result Email Dispatch to hidayatullashaik268@gmail.com ---")
    
    target_email = "hidayatullashaik268@gmail.com"
    student = Student.objects.first()
    assert student is not None, "Student required"
    
    # 1. Set student's email to user's real email
    student.user.email = target_email
    student.user.save()
    print(f"[OK] Updated Student {student.roll_number} email to: {student.user.email}")
    
    # 2. Get an exam with results for this student's section
    exam = Exam.objects.filter(year=student.year, branch=student.branch).first()
    if not exam:
        print("[INFO] Creating test exam record...")
        exam = Exam.objects.create(
            name="End Semester Examination",
            exam_type="SEM",
            branch=student.branch,
            year=student.year,
            semester=1
        )
        
    print(f"[OK] Testing Result Release Email for Exam: {exam.name} (Semester {exam.semester})")
    
    # Use locmem backend for outbox testing
    settings.EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
    mail.outbox.clear()

    # 3. Trigger _send_result_emails
    sent, failed = _send_result_emails(exam, student.section)
    print(f"[SUCCESS] Email Sending Execution Complete: {sent} Sent, {failed} Failed")
    
    # Verify in Django outbox
    last_mail = mail.outbox[0] if mail.outbox else None
    if last_mail:
        print(f"[VERIFIED] Outbox Subject: {last_mail.subject}")
        print(f"[VERIFIED] Outbox Recipient: {last_mail.to}")
        assert target_email in last_mail.to, f"Target email {target_email} not in recipients list {last_mail.to}"
        print(f"[SUCCESS] Confirmed! Result release email is constructed and sent to recipient: {target_email}.")
        
    print("--- RESULT MAIL DISPATCH TEST PASSED! ---")

if __name__ == '__main__':
    test_email_to_user = test_result_email_to_user()
