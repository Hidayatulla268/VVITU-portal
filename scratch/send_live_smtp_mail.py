import os
import sys
import django

# Setup Django Environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'VVITU_Portal.settings')
django.setup()

from django.conf import settings
from django.core.mail import send_mail

def test_live_smtp_send():
    sender = os.environ.get('EMAIL_HOST_USER') or "hidayatullashaik2006@gmail.com"
    app_password = os.environ.get('EMAIL_HOST_PASSWORD') or os.environ.get('EMAIL_PASSWORD')
    recipient = "hidayatullashaik268@gmail.com"

    print("============================================================")
    print("  VVITU Portal — Live SMTP Email Dispatcher")
    print("============================================================")
    print(f"Sender Email  : {sender}")
    print(f"Recipient Mail: {recipient}")
    
    if not app_password:
        print("\n[NOTE] Gmail App Password (EMAIL_HOST_PASSWORD) is not set in environment.")
        print("To send live emails to your inbox via Google SMTP:")
        print("1. Visit https://myaccount.google.com/apppasswords")
        print("2. Generate a 16-character App Password for 'hidayatullashaik2006@gmail.com'")
        print("3. Set EMAIL_HOST_PASSWORD in your .env file or environment.")
        return

    # Configure SMTP Backend dynamically
    settings.EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    settings.EMAIL_HOST = 'smtp.gmail.com'
    settings.EMAIL_PORT = 587
    settings.EMAIL_USE_TLS = True
    settings.EMAIL_HOST_USER = sender
    settings.EMAIL_HOST_PASSWORD = app_password
    settings.DEFAULT_FROM_EMAIL = f"VVITU Examination Cell <{sender}>"

    subject = "[VVITU Portal] Official Exam Results Released — Shaik Hidayatulla (24BQ1A4901)"
    body = """Dear Shaik Hidayatulla,

Your results for Semester End Examinations (Regular) have been released by the Examination Cell.

Student Name : Shaik Hidayatulla
Roll Number  : 24BQ1A4901
Exam         : Semester End Examinations (Regular)
Branch       : CSE — Computer Science and Engineering
Year         : Year 2 | Semester : 3

--------------------------------------------------
SUBJECT RESULTS
--------------------------------------------------
  - CS304      | Computer Networks                      |  92/100 | Grade: O
  - CS391      | DS Lab                                 |  88/100 | Grade: A+
  - CS301      | Data Structures and Algorithms         |  95/100 | Grade: O
  - CS303      | Database Management Systems            |  90/100 | Grade: O
  - CS302      | Operating Systems                      |  91/100 | Grade: O
--------------------------------------------------
Overall Marks      : 456.00 / 500.00
Overall Percentage : 91.20%
--------------------------------------------------

You can also view your detailed grade card by logging into the VVITU Portal:
https://www.vvitu.ac.in/student/results/

For any queries, please contact your class teacher or the controller of examinations.

Regards,
Controller of Examinations
Vasireddy Venkatadri International Technological University
Nambur, Guntur District, Andhra Pradesh
"""

    print(f"\nConnecting to Google SMTP (smtp.gmail.com:587) and dispatching live email...")
    try:
        sent_count = send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient],
            fail_silently=False
        )
        print(f"\n[SUCCESS] Live email sent to {recipient}! Check your inbox now!")
    except Exception as e:
        print(f"\n[ERROR] SMTP Connection failed: {e}")

if __name__ == '__main__':
    test_live_smtp_send()
