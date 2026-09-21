"""
VVITU Academic Portal — Tier 1: Unit Testing
Tests individual models, business logic properties, methods, string representations,
template tags, and context processors in complete isolation.
"""

from datetime import date, timedelta
from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from django.utils import timezone
from accounts.models import Student, Faculty, DEOProfile
from core.models import (
    Branch, Year, Section, Subject, Timetable, Attendance,
    Exam, Result, AcademicCalendar, ClassDiary, ExamSchedule,
    SubjectTopicPlan
)
from core.context_processors import app_version, active_theme
from core.templatetags import core_tags

User = get_user_model()


class UserModelUnitTest(TestCase):
    """Unit tests for custom User model and role-based logic."""

    def test_create_user_with_roles(self):
        roles = ['admin', 'student', 'faculty', 'hod', 'deo']
        for r in roles:
            u = User.objects.create_user(
                username=f"test_{r}",
                password="vvit@1234",
                role=r,
                first_name=r.capitalize(),
                last_name="User"
            )
            self.assertEqual(u.role, r)
            self.assertIn(r, str(u))

    def test_user_dashboard_urls(self):
        role_expected = {
            'admin': '/admin-portal/',
            'student': '/student/',
            'faculty': '/faculty/',
            'hod': '/hod/',
            'deo': '/deo/',
        }
        for role, url in role_expected.items():
            u = User.objects.create_user(username=f"dash_{role}", role=role)
            self.assertEqual(u.get_dashboard_url(), url)


class AcademicStructureModelUnitTest(TestCase):
    """Unit tests for Branch, Year, Section, and Subject models."""

    def setUp(self):
        self.branch = Branch.objects.create(name="Computer Science & Engineering", code="CSE")
        self.year = Year.objects.get(year=2)

    def test_branch_auto_generates_sections(self):
        # Branch save automatically generates Sections A and B for years 1-4
        sections = Section.objects.filter(branch=self.branch, year=self.year)
        sec_names = set(sections.values_list('name', flat=True))
        self.assertTrue({'A', 'B'}.issubset(sec_names))
        self.assertIn("CSE", str(self.branch))

    def test_section_str(self):
        sec = Section.objects.get(branch=self.branch, year=self.year, name="A")
        self.assertEqual(str(sec), "CSE-2-A")

    def test_subject_short_name_property(self):
        subj1 = Subject.objects.create(
            name="Database Management Systems",
            code="CS201",
            branch=self.branch,
            year=self.year,
            semester=3,
            credits=4,
            is_lab=False
        )
        self.assertEqual(subj1.short_name, "DMS")

        subj2 = Subject.objects.create(
            name="Operating Systems Laboratory",
            code="CS202L",
            branch=self.branch,
            year=self.year,
            semester=3,
            credits=2,
            is_lab=True
        )
        self.assertTrue(subj2.short_name.endswith("LAB"))


class StudentAndFacultyModelUnitTest(TestCase):
    """Unit tests for Student, Faculty, Attendance, and Performance metrics."""

    def setUp(self):
        self.branch = Branch.objects.create(name="Information Technology", code="IT")
        self.year = Year.objects.get(year=3)
        self.section = Section.objects.get(branch=self.branch, year=self.year, name="A")

        # Faculty
        self.fac_user = User.objects.create_user(
            username="faculty_unit_01",
            first_name="Alan",
            last_name="Turing",
            role="faculty"
        )
        self.faculty = Faculty.objects.create(
            user=self.fac_user,
            employee_id="IT_FAC_001",
            department=self.branch,
            designation="Assistant Professor",
            monthly_leave_limit=2.0
        )

        # Student
        self.stud_user = User.objects.create_user(
            username="24BQ1A1201",
            first_name="Ada",
            last_name="Lovelace",
            role="student"
        )
        self.student = Student.objects.create(
            user=self.stud_user,
            roll_number="24BQ1A1201",
            branch=self.branch,
            year=self.year,
            section=self.section,
            class_teacher=self.faculty
        )

        # Subject & Timetable
        self.subject = Subject.objects.create(
            name="Computer Networks",
            code="IT301",
            branch=self.branch,
            year=self.year,
            semester=5,
            credits=3,
            faculty=self.faculty
        )
        self.tt = Timetable.objects.create(
            section=self.section,
            day="Monday",
            period=1,
            subject=self.subject,
            faculty=self.faculty,
            room_number="IT-304"
        )

    def test_student_str_and_properties(self):
        self.assertIn("24BQ1A1201", str(self.student))
        self.assertEqual(self.student.full_name, "Ada Lovelace")

    def test_student_attendance_calculation(self):
        # 0 records initially
        self.assertEqual(self.student.calculate_attendance_pct, 0.0)

        today = timezone.localdate()
        # Mark 3 Present, 1 Absent
        Attendance.objects.create(student=self.student, timetable_entry=self.tt, date=today - timedelta(days=3), status='P')
        Attendance.objects.create(student=self.student, timetable_entry=self.tt, date=today - timedelta(days=2), status='P')
        Attendance.objects.create(student=self.student, timetable_entry=self.tt, date=today - timedelta(days=1), status='P')
        Attendance.objects.create(student=self.student, timetable_entry=self.tt, date=today, status='A')

        # 3/4 = 75.0%
        self.assertEqual(self.student.calculate_attendance_pct, 75.0)

    def test_faculty_leave_balance_properties(self):
        self.assertEqual(self.faculty.get_monthly_leaves_taken(), 0.0)
        self.assertEqual(self.faculty.get_monthly_leaves_remaining(), 2.0)
        self.assertFalse(self.faculty.is_leave_limit_reached())


class ExaminationAndMilestoneModelUnitTest(TestCase):
    """Unit tests for ExamSchedule, SubjectTopicPlan, and ClassDiary models."""

    def setUp(self):
        self.branch = Branch.objects.create(name="Mechanical Engineering", code="MECH")
        self.year = Year.objects.get(year=4)
        self.section = Section.objects.get(branch=self.branch, year=self.year, name="A")
        self.fac_user = User.objects.create_user(username="mech_fac", role="faculty")
        self.faculty = Faculty.objects.create(user=self.fac_user, employee_id="MECH01", department=self.branch)
        self.subject = Subject.objects.create(
            name="Thermodynamics", code="ME401", branch=self.branch, year=self.year, semester=7
        )
        self.tt = Timetable.objects.create(
            section=self.section, day="Tuesday", period=2, subject=self.subject, faculty=self.faculty
        )

    def test_exam_schedule_milestones(self):
        today = timezone.localdate()
        schedule = ExamSchedule.objects.create(
            branch=self.branch,
            year=self.year,
            semester=7,
            exam_type='mid1',
            title='B.Tech MECH IV Year Sem-7 Mid-1 Examinations',
            start_date=today + timedelta(days=20),
            end_date=today + timedelta(days=25),
            target_units=2.5,
            target_completion_date=today + timedelta(days=15)
        )
        self.assertTrue(schedule.is_upcoming)
        self.assertFalse(schedule.is_deadline_passed)
        self.assertIn("2.5 Units", str(schedule))

    def test_subject_topic_plan_overdue_logic(self):
        today = timezone.localdate()
        topic = SubjectTopicPlan.objects.create(
            subject=self.subject,
            unit_number=1,
            topic_name="First Law of Thermodynamics",
            target_date=today - timedelta(days=5),
            target_milestone='mid1',
            is_completed=False
        )
        self.assertTrue(topic.is_overdue)
        self.assertEqual(topic.days_overdue, 5)

        # Mark completed
        topic.is_completed = True
        topic.completed_date = today
        topic.save()
        self.assertFalse(topic.is_overdue)

    def test_class_diary_entry(self):
        today = timezone.localdate()
        diary = ClassDiary.objects.create(
            timetable_entry=self.tt,
            section=self.section,
            subject=self.subject,
            faculty=self.faculty,
            date=today,
            period=2,
            unit_number=2,
            topic_covered="Carnot Cycle & Efficiency",
            discussion_summary="Analyzed PV and TS diagrams."
        )
        self.assertEqual(diary.unit_label, "Unit 2")
        self.assertIn("Carnot Cycle", str(diary))


class ContextProcessorsAndTemplateTagsUnitTest(TestCase):
    """Unit tests for context processors and core custom template tags."""

    def setUp(self):
        self.factory = RequestFactory()

    def test_app_version_context_processor(self):
        req = self.factory.get('/')
        ctx = app_version(req)
        self.assertIn('APP_VERSION', ctx)
        self.assertEqual(ctx['APP_VERSION'], '3.3.0')

    def test_active_theme_context_processor(self):
        # Default
        req = self.factory.get('/')
        self.assertEqual(active_theme(req)['ACTIVE_THEME'], 'dark')

        # Cookie set to light
        req.COOKIES['vvit_theme'] = 'light'
        self.assertEqual(active_theme(req)['ACTIVE_THEME'], 'light')

    def test_core_tags(self):
        test_dict = {'CS101': 85, 'CS102': 92}
        self.assertEqual(core_tags.get_item(test_dict, 'CS101'), 85)
        self.assertEqual(core_tags.dict_get(test_dict, 'CS102'), 92)
        self.assertIsNone(core_tags.get_item(test_dict, 'UNKNOWN'))

        # Split and arithmetic filters
        self.assertEqual(core_tags.split("Mon,Tue,Wed", ","), ["Mon", "Tue", "Wed"])
        self.assertEqual(core_tags.subtract(10, 4), 6)
        self.assertEqual(list(core_tags.to_range(3)), [0, 1, 2])

        # Subject icon filter
        self.assertEqual(core_tags.subject_icon("Data Structures"), "fas fa-code")
        self.assertEqual(core_tags.subject_icon("Database Systems"), "fas fa-database")
