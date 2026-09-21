"""
VVITU Portal — Welcome Credentials & Notification Utilities
Dispatches welcome email and credentials instructions to new students.
"""
import logging
from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


def send_welcome_credentials_email(user, temp_password, roll_number=None, request=None):
    """
    Sends welcome email with temporary credentials and login instructions.
    Gracefully handles local development when SMTP is not configured.
    """
    if not user.email:
        return False

    roll = roll_number or user.username
    full_name = user.get_full_name() or roll
    
    # Determine portal login URL
    portal_url = "https://portal.vvitu.ac.in/accounts/login/"
    if request:
        try:
            portal_url = request.build_absolute_uri('/accounts/login/')
        except Exception:
            pass

    subject = f"Welcome to VVITU Portal — Your Login Credentials ({roll})"
    message = f"""Dear {full_name},

Welcome to the Vasireddy Venkatadri International Technological University (VVITU) Portal!

Your student portal account has been created. Below are your initial login credentials:

Username / Roll Number: {roll}
Temporary Password: {temp_password}

Login URL: {portal_url}

IMPORTANT SECURITY NOTICE:
When you log in for the first time, you will be required to change your password immediately to your own permanent, private password before accessing your dashboard, attendance, and exam results.

If you have any questions or require assistance, please contact the VVITU Academic Administration or your Class Teacher.

Best regards,
VVITU Portal Administration
Vasireddy Venkatadri International Technological University
"""
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@vvitu.ac.in'),
            recipient_list=[user.email],
            fail_silently=True,
        )
        logger.info(f"Welcome credentials email dispatched to {user.email} for roll {roll}.")
        return True
    except Exception as e:
        logger.warning(f"Could not send welcome email to {user.email}: {e}")
        return False
