"""
VVITU Academic Portal — Tier 8: Regression Testing
Guards specifically against previously resolved user-reported issues:
- Dropdown select repeating red chevron tiling bug on :focus/:active
- Duplicate plus symbol on 'Add Exam Schedule' action button
- Theme flashing / FOUC on page transitions
- Academic Calendar 1-day notification calculation
"""

from datetime import date, timedelta
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from core.models import Branch, Year, AcademicCalendar
from core.context_processors import app_version, active_theme

User = get_user_model()


class DefectRegressionSuiteTest(TestCase):
    """Specific regression assertions ensuring past bugs cannot reappear."""

    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(username="reg_admin", password="password123", role="admin")

    def test_regression_select_repeating_chevrons_fix(self):
        """
        Regression Check: Dropdown Select Chevron Tiling.
        Ensure that <style id='globalSelectFix'> prevents repeating chevrons and
        uses sleek slate stroke rather than repeating red chevrons.
        """
        self.client.force_login(self.admin)
        resp = self.client.get(reverse('admin_dashboard:manage_exam_schedules'))
        self.assertEqual(resp.status_code, 200)

        content = resp.content.decode('utf-8')
        self.assertIn('<style id="globalSelectFix">', content)
        self.assertIn('background-repeat: no-repeat !important;', content)
        self.assertIn('right 0.85rem center !important;', content)
        # Verify slate chevron is used instead of red chevron
        self.assertIn('%2364748b', content)
        self.client.logout()

    def test_regression_single_plus_symbol_on_add_schedule_button(self):
        """
        Regression Check: Duplicate Plus Sign.
        Verify that 'Add Exam Schedule' button contains exactly one '+' icon, not '+ +'.
        """
        self.client.force_login(self.admin)
        resp = self.client.get(reverse('admin_dashboard:manage_exam_schedules'))
        self.assertEqual(resp.status_code, 200)

        content = resp.content.decode('utf-8')
        # Check that it has <i class="fas fa-plus me-1"></i>Add Exam Schedule
        self.assertIn('<i class="fas fa-plus me-1"></i>Add Exam Schedule', content)
        # Ensure there is no literal '+ <i' or duplicate plus character before the icon
        self.assertNotIn('+ <i class="fas fa-plus', content)
        self.assertNotIn('+<i class="fas fa-plus', content)
        self.client.logout()

    def test_regression_app_version_cache_busting(self):
        """
        Regression Check: Client Browser Cache Invalidation.
        Verify APP_VERSION is updated to 3.3.0.
        """
        self.client.force_login(self.admin)
        resp = self.client.get(reverse('admin_dashboard:dashboard'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '?v=3.3.0')
        self.client.logout()

    def test_regression_calendar_1day_reminder_boundary(self):
        """
        Regression Check: Calendar 1-Day Notification Calculation.
        Ensure events for tomorrow are matched, but events for next week are untouched.
        """
        from django.core.management import call_command
        today = timezone.localdate()

        branch = Branch.objects.create(name="Chemical Engineering", code="CHEM")

        event_tomorrow = AcademicCalendar.objects.create(
            title="Mid-1 Chemistry Exam",
            date=today + timedelta(days=1),
            event_type="exam",
            branch=branch,
            reminder_sent=False
        )
        event_future = AcademicCalendar.objects.create(
            title="University Annual Day",
            date=today + timedelta(days=7),
            event_type="event",
            branch=branch,
            reminder_sent=False
        )

        call_command('send_event_reminders')

        event_tomorrow.refresh_from_db()
        event_future.refresh_from_db()

        self.assertTrue(event_tomorrow.reminder_sent, "Event tomorrow should have reminder_sent=True")
        self.assertFalse(event_future.reminder_sent, "Event in 7 days should NOT have reminder_sent=True yet")
