"""
VVITU Academic Portal — Tier 3: Functional Testing
Validates end-to-end functionality of views, dashboards, listings, and form rendering
across all 5 user roles: Admin, Student, Faculty, HOD, and DEO.
"""

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from accounts.models import Student, Faculty, DEOProfile
from core.models import Branch, Year, Section, Subject, Timetable, Attendance, ExamSchedule, AcademicCalendar

User = get_user_model()


class FunctionalPortalViewsTest(TestCase):
    """Functional tests verifying complete view rendering and data context for all roles."""

    def setUp(self):
        self.client = Client()

        # Branch, Year, Section, Subject
        self.branch = Branch.objects.create(name="Computer Science & Business Systems", code="CSBS")
        self.year = Year.objects.get(year=2)
        self.section = Section.objects.get(branch=self.branch, year=self.year, name="A")

        # 1. Admin User
        self.admin_user = User.objects.create_user(username="func_admin", password="password123", role="admin")

        # 2. Faculty User
        self.fac_user = User.objects.create_user(username="func_faculty", password="password123", role="faculty")
        self.faculty = Faculty.objects.create(user=self.fac_user, employee_id="FAC_F01", department=self.branch)

        # 3. Student User
        self.stud_user = User.objects.create_user(username="24BQ1A3201", password="password123", role="student")
        self.student = Student.objects.create(
            user=self.stud_user, roll_number="24BQ1A3201", branch=self.branch, year=self.year, section=self.section, class_teacher=self.faculty, is_first_login=False
        )

        # 4. HOD User
        self.hod_user = User.objects.create_user(username="func_hod", password="password123", role="hod")
        self.hod_faculty = Faculty.objects.create(user=self.hod_user, employee_id="HOD_CSBS", department=self.branch, designation="HOD")

        # 5. DEO User
        self.deo_user = User.objects.create_user(username="func_deo", password="password123", role="deo")
        self.deo_profile = DEOProfile.objects.create(user=self.deo_user, employee_id="DEO_01", branch=self.branch)

        # Subject & Timetable
        self.subject = Subject.objects.create(
            name="Data Structures & Algorithms", code="CSB201", branch=self.branch, year=self.year, semester=3, faculty=self.faculty
        )
        self.tt = Timetable.objects.create(
            section=self.section, day="Monday", period=1, subject=self.subject, faculty=self.faculty
        )

    def test_admin_functional_endpoints(self):
        self.client.force_login(self.admin_user)

        # Dashboard
        resp = self.client.get(reverse('admin_dashboard:dashboard'))
        self.assertEqual(resp.status_code, 200)

        # Exam Milestones & Schedules
        resp = self.client.get(reverse('admin_dashboard:manage_exam_schedules'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Exam Milestones")

        # Academic Calendar
        resp = self.client.get(reverse('admin_dashboard:academic_calendar'))
        self.assertEqual(resp.status_code, 200)

        # Manage Students
        resp = self.client.get(reverse('admin_dashboard:manage_students'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "24BQ1A3201")

        self.client.logout()

    def test_student_functional_endpoints(self):
        self.client.force_login(self.stud_user)

        # Student Dashboard
        resp = self.client.get(reverse('student:dashboard'))
        self.assertEqual(resp.status_code, 200)

        # Attendance Log
        resp = self.client.get(reverse('student:attendance'))
        self.assertEqual(resp.status_code, 200)

        # Timetable
        resp = self.client.get(reverse('student:timetable'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Class Timetable")

        # Academic Calendar
        resp = self.client.get(reverse('student:academic_calendar'))
        self.assertEqual(resp.status_code, 200)

        self.client.logout()

    def test_faculty_functional_endpoints(self):
        self.client.force_login(self.fac_user)

        # Faculty Dashboard
        resp = self.client.get(reverse('faculty:dashboard'))
        self.assertEqual(resp.status_code, 200)

        # Mark Attendance view
        resp = self.client.get(reverse('faculty:mark_attendance'))
        self.assertEqual(resp.status_code, 200)

        # Class Diary
        resp = self.client.get(reverse('faculty:class_diary'))
        self.assertEqual(resp.status_code, 200)

        # Timetable
        resp = self.client.get(reverse('faculty:my_timetable'))
        self.assertEqual(resp.status_code, 200)

        self.client.logout()

    def test_hod_functional_endpoints(self):
        self.client.force_login(self.hod_user)

        # HOD Dashboard
        resp = self.client.get(reverse('hod:dashboard'))
        self.assertEqual(resp.status_code, 200)

        # Manage Students in branch
        resp = self.client.get(reverse('hod:manage_students'))
        self.assertEqual(resp.status_code, 200)

        self.client.logout()

    def test_deo_functional_endpoints(self):
        self.client.force_login(self.deo_user)

        # DEO Dashboard
        resp = self.client.get(reverse('deo:dashboard'))
        self.assertEqual(resp.status_code, 200)

        # DEO Students
        resp = self.client.get(reverse('deo:manage_students'))
        self.assertEqual(resp.status_code, 200)

        self.client.logout()
