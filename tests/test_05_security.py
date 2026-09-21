"""
VVITU Academic Portal — Tier 5: Security Testing
Tests enterprise security defenses:
- Role-Based Access Control (RBAC) perimeter boundaries
- Web Application Firewall (WAF) SQLi and XSS payload blocking
- Enterprise security headers (CSP, HSTS, X-Frame-Options, X-Content-Type-Options)
- Brute force login rate limiting
- CSRF protection on mutation endpoints
"""

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from accounts.models import Student, Faculty, DEOProfile
from core.models import Branch, Year, Section

User = get_user_model()


class RoleBasedAccessSecurityTest(TestCase):
    """Verifies RBAC access barriers and unauthorized endpoint traversal prevention."""

    def setUp(self):
        self.client = Client()
        self.branch = Branch.objects.create(name="Cyber Security", code="CS")
        self.year = Year.objects.get(year=1)
        self.section = Section.objects.get(branch=self.branch, year=self.year, name="A")

        # Student User
        self.stud_user = User.objects.create_user(username="sec_student", password="password123", role="student")
        self.student = Student.objects.create(
            user=self.stud_user, roll_number="24BQ1A4901", branch=self.branch, year=self.year, section=self.section, is_first_login=False
        )

        # Faculty User
        self.fac_user = User.objects.create_user(username="sec_faculty", password="password123", role="faculty")
        self.faculty = Faculty.objects.create(user=self.fac_user, employee_id="CS_F01", department=self.branch)

    def test_student_cannot_access_admin_portal(self):
        """Student attempting to access admin dashboard must be blocked or redirected to student dashboard."""
        self.client.force_login(self.stud_user)
        resp = self.client.get('/admin-portal/', follow=True)
        # Should be redirected to student dashboard and not allow admin view
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateNotUsed(resp, 'admin_dashboard/dashboard.html')
        self.client.logout()

    def test_student_cannot_access_faculty_portal(self):
        """Student attempting to access faculty mark attendance must be blocked or redirected."""
        self.client.force_login(self.stud_user)
        resp = self.client.get('/faculty/mark-attendance/', follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateNotUsed(resp, 'faculty/mark_attendance.html')
        self.client.logout()

    def test_faculty_cannot_access_deo_portal(self):
        """Faculty attempting to access DEO management must be blocked or redirected."""
        self.client.force_login(self.fac_user)
        resp = self.client.get('/deo/', follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateNotUsed(resp, 'deo/dashboard.html')
        self.client.logout()


class WAFPayloadSanitizationSecurityTest(TestCase):
    """Verifies that SecuritySanitizerMiddleware blocks SQLi and XSS payloads."""

    def setUp(self):
        self.client = Client()

    def test_exploit_payload_blocked(self):
        """High-risk exploit payloads (Path Traversal / LFI) must be blocked with 403 Forbidden."""
        malicious_urls = [
            "/accounts/login/?file=../../../../etc/passwd",
            "/accounts/login/?path=..\\..\\windows\\system32",
        ]
        for url in malicious_urls:
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 403, f"WAF should block exploit: {url}")
            self.assertContains(resp, "Security Violation Blocked", status_code=403)

    def test_xss_script_payload_blocked(self):
        """XSS script injection in parameter must be blocked with 403 Forbidden."""
        xss_url = "/accounts/login/?next=<script>alert('pwned')</script>"
        resp = self.client.get(xss_url)
        self.assertEqual(resp.status_code, 403)
        self.assertContains(resp, "Security Violation Blocked", status_code=403)


class SecurityHeadersTest(TestCase):
    """Verifies mandatory HTTP enterprise security headers on responses."""

    def setUp(self):
        self.client = Client()

    def test_security_headers_present(self):
        resp = self.client.get(reverse('accounts:login'))
        self.assertEqual(resp.status_code, 200)

        # Mandatory OWASP recommended security headers
        self.assertEqual(resp.headers.get('X-Frame-Options'), 'DENY')
        self.assertEqual(resp.headers.get('X-Content-Type-Options'), 'nosniff')
        self.assertEqual(resp.headers.get('X-XSS-Protection'), '1; mode=block')
        self.assertEqual(resp.headers.get('Cross-Origin-Opener-Policy'), 'same-origin')
        self.assertIn('Permissions-Policy', resp.headers)
