"""
VVITU Academic Portal — Tier 6: Performance Testing
Tests query count efficiency, N+1 query prevention, and page response latency benchmarks.
"""

import time
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from accounts.models import Student, Faculty
from core.models import Branch, Year, Section, Subject, Timetable, ExamSchedule

User = get_user_model()


class ResponseLatencyAndQueryPerformanceTest(TestCase):
    """Measures endpoint execution durations and verifies optimized SQL execution."""

    def setUp(self):
        self.client = Client()
        self.branch = Branch.objects.create(name="Artificial Intelligence & Data Science", code="AIDS")
        self.year = Year.objects.get(year=3)
        self.section = Section.objects.get(branch=self.branch, year=self.year, name="A")

        self.admin_user = User.objects.create_user(username="perf_admin", password="password123", role="admin")

        self.fac_user = User.objects.create_user(username="perf_fac", password="password123", role="faculty")
        self.faculty = Faculty.objects.create(user=self.fac_user, employee_id="AI_F01", department=self.branch)

        self.stud_user = User.objects.create_user(username="24BQ1A5401", password="password123", role="student")
        self.student = Student.objects.create(
            user=self.stud_user, roll_number="24BQ1A5401", branch=self.branch, year=self.year, section=self.section, is_first_login=False
        )

        # Populate sample subjects and timetables
        for i in range(1, 6):
            subj = Subject.objects.create(
                name=f"Advanced AI Subject {i}",
                code=f"AI30{i}",
                branch=self.branch,
                year=self.year,
                semester=5,
                faculty=self.faculty
            )
            Timetable.objects.create(
                section=self.section,
                day="Monday",
                period=i,
                subject=subj,
                faculty=self.faculty
            )

    def test_admin_exam_schedules_response_latency(self):
        """Ensures the Exam Schedules page renders within acceptable latency (< 500ms)."""
        self.client.force_login(self.admin_user)
        start_time = time.time()
        resp = self.client.get(reverse('admin_dashboard:manage_exam_schedules'))
        duration = (time.time() - start_time) * 1000  # in ms

        self.assertEqual(resp.status_code, 200)
        self.assertLess(duration, 500.0, f"Page load took {duration:.2f}ms, target is < 500ms")
        self.client.logout()

    def test_student_dashboard_response_latency(self):
        """Ensures Student Dashboard renders within acceptable latency (< 500ms)."""
        self.client.force_login(self.stud_user)
        start_time = time.time()
        resp = self.client.get(reverse('student:dashboard'))
        duration = (time.time() - start_time) * 1000

        self.assertEqual(resp.status_code, 200)
        self.assertLess(duration, 500.0, f"Student dashboard took {duration:.2f}ms, target is < 500ms")
        self.client.logout()

    def test_query_efficiency_on_timetable(self):
        """Verifies student timetable does not execute excessive runaway queries."""
        from django.test.utils import CaptureQueriesContext
        from django.db import connection

        self.client.force_login(self.stud_user)
        with CaptureQueriesContext(connection) as ctx:
            resp = self.client.get(reverse('student:timetable'))
            self.assertEqual(resp.status_code, 200)
            self.assertLess(len(ctx.captured_queries), 35, f"Executed {len(ctx.captured_queries)} queries, target < 35")
        self.client.logout()
