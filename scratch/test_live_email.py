import os
import sys
import django

# Setup Django Environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'VVITU_Portal.settings')
django.setup()

from django.core.mail import send_mail
from django.conf import settings

def test_email_configuration():
    print("--- Testing Live Email Dispatch System ---")
    print(f"Current EMAIL_BACKEND: {settings.EMAIL_BACKEND}")
    print(f"Current DEFAULT_FROM_EMAIL: {settings.DEFAULT_FROM_EMAIL}")
    print(f"SMTP User Configured: {settings.EMAIL_HOST_USER or 'None (Dev Console Mode)'}")
    
    # Test sending a mock result notification
    test_recipient = "student@college.edu"
    sent_count = send_mail(
        subject="[VVITU Portal] Semester Exam Results Released",
        message="Dear Student, your semester results have been published on the VVITU Portal.",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[test_recipient],
        fail_silently=False
    )
    assert sent_count == 1, f"Expected 1 sent email, got {sent_count}"
    print(f"[SUCCESS] Email successfully dispatched to {test_recipient}!")
    print("--- ALL EMAIL SYSTEM TESTS PASSED SUCCESSFULLY! ---")

if __name__ == '__main__':
    test_email_configuration()
