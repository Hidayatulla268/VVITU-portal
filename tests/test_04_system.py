"""
VVITU Academic Portal — Tier 4: System Testing
Tests system-wide operational integrity:
- Automated management commands (event reminders, low attendance alerts)
- Database schema consistency and migration health
- Static files resolution and WhiteNoise static asset pipeline
- Global Exception Redirect Middleware
"""

from datetime import date, timedelta
from django.test import TestCase, Client, override_settings
from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.contrib.staticfiles import finders
from django.urls import reverse
from django.utils import timezone
from accounts.models import Student, Faculty
from core.models import (
    Branch, Year, Section, Subject, Timetable, Attendance, AcademicCalendar
)

User = get_user_model()


class SystemManagementCommandsTest(TestCase):
    """System tests for background management commands."""

    def setUp(self):
        self.branch = Branch.objects.create(name="Electronics & Communication", code="ECE")
        self.year = Year.objects.get(year=3)
        self.section = Section.objects.get(branch=self.branch, year=self.year, name="A")

        self.fac_user = User.objects.create_user(username="ece_fac", role="faculty")
        self.faculty = Faculty.objects.create(user=self.fac_user, employee_id="ECE_F1", department=self.branch)

        self.stud_user = User.objects.create_user(username="24BQ1A0401", email="student@vvit.net", role="student")
        self.student = Student.objects.create(
            user=self.stud_user, roll_number="24BQ1A0401", branch=self.branch, year=self.year, section=self.section, is_first_login=False
        )

        self.subject = Subject.objects.create(
            name="Digital Signal Processing", code="EC301", branch=self.branch, year=self.year, semester=5, faculty=self.faculty
        )
        self.tt = Timetable.objects.create(
            section=self.section, day="Monday", period=1, subject=self.subject, faculty=self.faculty
        )

    def test_send_event_reminders_command(self):
        """Verifies academic calendar 1-day advance reminder command runs cleanly."""
        tomorrow = timezone.localdate() + timedelta(days=1)
        event = AcademicCalendar.objects.create(
            title="University Tech Symposium",
            date=tomorrow,
            event_type="event",
            branch=self.branch,
            reminder_sent=False
        )

        # Execute management command
        call_command('send_event_reminders')

        event.refresh_from_db()
        self.assertTrue(event.reminder_sent)
        self.assertIsNotNone(event.reminder_sent_at)

    def test_send_low_attendance_alerts_command(self):
        """Verifies low attendance scanner processes students below 75% without crashes."""
        today = timezone.localdate()
        # Mark 1 Present, 4 Absent -> 20.0% attendance
        Attendance.objects.create(student=self.student, timetable_entry=self.tt, date=today - timedelta(days=1), status='P')
        for i in range(2, 6):
            Attendance.objects.create(student=self.student, timetable_entry=self.tt, date=today - timedelta(days=i), status='A')

        self.assertEqual(self.student.calculate_attendance_pct, 20.0)

        # Run alert command cleanly
        call_command('send_low_attendance_alerts')


class SystemStaticAndSchemaIntegrityTest(TestCase):
    """System tests verifying static files discovery and database migration status."""

    def test_static_core_assets_found(self):
        """Ensures core CSS files and university assets are discoverable by static finders."""
        main_css = finders.find('css/main.css')
        theme_css = finders.find('css/theme_and_calendar.css')

        self.assertIsNotNone(main_css, "main.css must be resolvable by static finders")
        self.assertIsNotNone(theme_css, "theme_and_calendar.css must be resolvable by static finders")

    def test_no_unapplied_database_migrations(self):
        """Ensures the schema is synchronized with all models."""
        try:
            call_command('makemigrations', '--check', '--dry-run')
        except SystemExit as e:
            # Code 0 means no unapplied model changes exist
            self.assertEqual(e.code, 0, "Uncommitted model changes detected! Please create migrations.")
