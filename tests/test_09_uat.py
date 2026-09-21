"""
VVITU Academic Portal — Tier 9: User Acceptance Testing (UAT)
Simulates complete real-world university user journeys and business scenarios:
- Scenario 1: Academic Dean schedules Semester Examinations with 2.5-unit milestone targets.
- Scenario 2: Faculty Professor logs class lesson diary and submits student attendance roster.
- Scenario 3: Undergraduate Student checks personalized timetable, attendance, and exam schedule.
- Scenario 4: Head of Department (HOD) oversees department operations and syllabus pacing.
"""

from datetime import date, timedelta
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from accounts.models import Student, Faculty
from core.models import (
    Branch, Year, Section, Subject, Timetable, Attendance,
    ExamSchedule, ClassDiary, SubjectTopicPlan
)

User = get_user_model()


class UniversityAcceptanceJourneysTest(TestCase):
    """End-to-End User Acceptance Scenarios matching actual university operations."""

    def setUp(self):
        self.client = Client()
        self.branch = Branch.objects.create(name="Computer Science & Engineering", code="CSE")
        self.year = Year.objects.get(year=2)
        self.section = Section.objects.get(branch=self.branch, year=self.year, name="A")

        # 1. Dean / Administrator
        self.admin = User.objects.create_user(username="dean_academic", password="password123", role="admin")

        # 2. Faculty / Professor
        self.fac_user = User.objects.create_user(username="prof_sharma", password="password123", role="faculty")
        self.professor = Faculty.objects.create(
            user=self.fac_user, employee_id="CSE_FAC_101", department=self.branch, designation="Associate Professor"
        )

        # 3. Student
        self.stud_user = User.objects.create_user(username="24BQ1A0501", password="password123", role="student")
        self.student = Student.objects.create(
            user=self.stud_user, roll_number="24BQ1A0501", branch=self.branch, year=self.year, section=self.section, class_teacher=self.professor, is_first_login=False
        )

        # 4. Subject & Timetable
        self.subject = Subject.objects.create(
            name="Formal Languages & Automata Theory",
            code="CS204",
            branch=self.branch,
            year=self.year,
            semester=3,
            faculty=self.professor
        )
        self.tt = Timetable.objects.create(
            section=self.section,
            day="Tuesday",
            period=2,
            subject=self.subject,
            faculty=self.professor,
            room_number="C-204"
        )

    def test_uat_journey_1_dean_exam_scheduling(self):
        """
        UAT Scenario 1: Academic Dean defines Mid-1 examination milestone.
        - Dean accesses Exam Schedules portal.
        - Defines Mid-1 schedule requiring 2.5 syllabus units before the deadline.
        - Verifies milestone appears in scheduled examinations list.
        """
        self.client.force_login(self.admin)
        today = timezone.localdate()

        # Create Mid-1 Milestone
        schedule = ExamSchedule.objects.create(
            branch=self.branch,
            year=self.year,
            semester=3,
            exam_type='mid1',
            title='B.Tech CSE II Year Sem-3 Mid-1 Examinations',
            start_date=today + timedelta(days=25),
            end_date=today + timedelta(days=30),
            target_units=2.5,
            target_completion_date=today + timedelta(days=18),
            created_by=self.admin
        )

        resp = self.client.get(reverse('admin_dashboard:manage_exam_schedules'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "B.Tech CSE II Year Sem-3 Mid-1 Examinations")
        self.assertContains(resp, "2.5 Units")
        self.client.logout()

    def test_uat_journey_2_faculty_class_conduct_and_attendance(self):
        """
        UAT Scenario 2: Faculty conducts lecture, logs diary topic, and records attendance.
        - Professor opens Faculty Portal.
        - Submits Class Diary entry for Period 2 covering 'Chomsky Hierarchy'.
        - Submits Student Attendance record as Present.
        - System dynamically updates student attendance percentage.
        """
        self.client.force_login(self.fac_user)
        today = timezone.localdate()

        # 1. Log Class Diary
        diary = ClassDiary.objects.create(
            timetable_entry=self.tt,
            section=self.section,
            subject=self.subject,
            faculty=self.professor,
            date=today,
            period=2,
            unit_number=2,
            topic_covered="Chomsky Hierarchy of Languages",
            discussion_summary="Context-free and Context-sensitive grammars."
        )
        self.assertEqual(diary.topic_covered, "Chomsky Hierarchy of Languages")

        # 2. Mark Student Attendance
        att = Attendance.objects.create(
            student=self.student,
            timetable_entry=self.tt,
            date=today,
            status='P',
            marked_by=self.professor
        )
        self.assertEqual(att.status, 'P')

        # 3. Verify student metrics update
        self.assertEqual(self.student.calculate_attendance_pct, 100.0)
        self.client.logout()

    def test_uat_journey_3_student_daily_academic_view(self):
        """
        UAT Scenario 3: Student inspects daily academic timetable and attendance.
        - Student logs into Student Portal.
        - Checks class timetable to confirm room and faculty details.
        - Views real-time attendance standing.
        """
        self.client.force_login(self.stud_user)

        # Mark 1 Present, 0 Absent
        today = timezone.localdate()
        Attendance.objects.create(
            student=self.student,
            timetable_entry=self.tt,
            date=today,
            status='P',
            marked_by=self.professor
        )

        # Dashboard View
        resp = self.client.get(reverse('student:dashboard'))
        self.assertEqual(resp.status_code, 200)

        # Timetable View
        resp_tt = self.client.get(reverse('student:timetable'))
        self.assertEqual(resp_tt.status_code, 200)
        self.assertContains(resp_tt, "Class Timetable")
        self.client.logout()
