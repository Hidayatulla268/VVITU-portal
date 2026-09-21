"""
VVITU Academic Portal — Tier 2: Integration Testing
Tests cross-app workflows: Authentication routing, Attendance to Student Metrics pipeline,
Class Transfer & Proxy lifecycle, and Exam Milestone integration.
"""

from datetime import date, timedelta
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from accounts.models import Student, Faculty, DEOProfile
from core.models import (
    Branch, Year, Section, Subject, Timetable, Attendance,
    ExamSchedule, ClassTransfer, AcademicCalendar
)

User = get_user_model()


class AuthAndRoleRoutingIntegrationTest(TestCase):
    """Tests authentication redirection across all 5 university roles."""

    def setUp(self):
        self.client = Client()
        self.users = {}
        roles = ['admin', 'student', 'faculty', 'hod', 'deo']
        for r in roles:
            self.users[r] = User.objects.create_user(
                username=f"int_{r}",
                password="vvit@1234",
                role=r
            )

    def test_role_redirect_workflow(self):
        expected_endpoints = {
            'admin': '/admin-portal/',
            'student': '/student/',
            'faculty': '/faculty/',
            'hod': '/hod/',
            'deo': '/deo/',
        }
        for role, expected_url in expected_endpoints.items():
            self.client.force_login(self.users[role])
            response = self.client.get(reverse('accounts:redirect'), follow=False)
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.url, expected_url)
            self.client.logout()


class AttendanceAndStudentMetricsIntegrationTest(TestCase):
    """Tests the end-to-end data pipeline from Faculty Attendance marking to Student Dashboard metrics."""

    def setUp(self):
        self.branch = Branch.objects.create(name="Civil Engineering", code="CIVIL")
        self.year = Year.objects.get(year=2)
        self.section = Section.objects.get(branch=self.branch, year=self.year, name="A")

        self.fac_user = User.objects.create_user(username="fac_civ", role="faculty")
        self.faculty = Faculty.objects.create(user=self.fac_user, employee_id="CIV01", department=self.branch)

        self.stud_user = User.objects.create_user(username="24BQ1A0101", role="student")
        self.student = Student.objects.create(
            user=self.stud_user, roll_number="24BQ1A0101", branch=self.branch, year=self.year, section=self.section
        )

        self.subject = Subject.objects.create(
            name="Structural Analysis", code="CE201", branch=self.branch, year=self.year, semester=3, faculty=self.faculty
        )
        self.tt = Timetable.objects.create(
            section=self.section, day="Wednesday", period=3, subject=self.subject, faculty=self.faculty
        )

    def test_attendance_marking_updates_student_standing(self):
        # Starts at 0%
        self.assertEqual(self.student.calculate_attendance_pct, 0.0)

        # Faculty submits 5 consecutive lecture attendances (4 Present, 1 Absent)
        today = timezone.localdate()
        for i in range(4):
            Attendance.objects.create(
                student=self.student,
                timetable_entry=self.tt,
                date=today - timedelta(days=i + 1),
                status='P',
                marked_by=self.faculty
            )
        Attendance.objects.create(
            student=self.student,
            timetable_entry=self.tt,
            date=today,
            status='A',
            marked_by=self.faculty
        )

        # Refreshed student standing: 4/5 = 80.0%
        self.assertEqual(self.student.calculate_attendance_pct, 80.0)
        self.assertFalse(self.student.is_detained)


class ClassTransferAndProxyIntegrationTest(TestCase):
    """Tests the proxy class assignment and substitution acceptance lifecycle."""

    def setUp(self):
        self.branch = Branch.objects.create(name="Electrical & Electronics Engineering", code="EEE")
        self.year = Year.objects.get(year=3)
        self.section = Section.objects.get(branch=self.branch, year=self.year, name="A")

        # Faculty A (Original instructor)
        self.user_a = User.objects.create_user(username="prof_a", role="faculty")
        self.faculty_a = Faculty.objects.create(user=self.user_a, employee_id="EEE_FA", department=self.branch)

        # Faculty B (Substitute instructor)
        self.user_b = User.objects.create_user(username="prof_b", role="faculty")
        self.faculty_b = Faculty.objects.create(user=self.user_b, employee_id="EEE_FB", department=self.branch)

        self.subject = Subject.objects.create(
            name="Power Systems", code="EE301", branch=self.branch, year=self.year, semester=5, faculty=self.faculty_a
        )
        self.tt = Timetable.objects.create(
            section=self.section, day="Thursday", period=4, subject=self.subject, faculty=self.faculty_a
        )

    def test_class_transfer_workflow(self):
        today = timezone.localdate()

        # 1. Faculty A initiates substitution to Faculty B
        transfer = ClassTransfer.objects.create(
            original_faculty=self.faculty_a,
            substitute_faculty=self.faculty_b,
            timetable_entry=self.tt,
            date=today + timedelta(days=1),
            reason="Attending National Conference",
            status='pending',
            transfer_type='substitution',
            assigned_by_role='faculty'
        )
        self.assertTrue(transfer.is_pending)
        self.assertEqual(transfer.type_label, "Substituted Session")

        # 2. Faculty B accepts the transfer
        transfer.status = 'accepted'
        transfer.responded_at = timezone.now()
        transfer.save()

        self.assertTrue(transfer.is_accepted)
        self.assertFalse(transfer.is_pending)
