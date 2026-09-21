"""
VVITU Academic Portal — Tier 7: Compatibility Testing
Tests Cross-Theme (Dark vs Light mode) rendering, Anti-FOUC theme synchronization,
Select dropdown chevron non-repeating styling, and Responsive Viewport standards.
"""

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse

User = get_user_model()


class ThemeAndStylingCompatibilityTest(TestCase):
    """Tests theme synchronization, anti-FOUC engine, and select chevron compatibility."""

    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(username="compat_admin", password="password123", role="admin")

    def test_dark_mode_server_side_rendering(self):
        """Default requests must render dark theme without client-side flicker."""
        self.client.force_login(self.admin)
        resp = self.client.get(reverse('admin_dashboard:dashboard'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'data-theme="dark"')
        self.assertContains(resp, 'Anti-FOUC (Flash of Dark/Light Theme) Instant Theme Synchronizer')
        self.client.logout()

    def test_light_mode_cookie_persistence(self):
        """Requests with vvit_theme=light cookie must render data-theme='light' server-side."""
        self.client.force_login(self.admin)
        self.client.cookies['vvit_theme'] = 'light'
        resp = self.client.get(reverse('admin_dashboard:dashboard'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'data-theme="light"')
        self.client.logout()

    def test_global_select_fix_presence(self):
        """Verifies that the high-priority #globalSelectFix style block is rendered in head."""
        self.client.force_login(self.admin)
        resp = self.client.get(reverse('admin_dashboard:manage_exam_schedules'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '<style id="globalSelectFix">')
        self.assertContains(resp, 'background-repeat: no-repeat !important;')
        self.assertContains(resp, '%2364748b')  # Neutral slate chevron stroke
        self.client.logout()

    def test_responsive_viewport_meta_tag(self):
        """Verifies that standard mobile/tablet viewport meta tag is present."""
        resp = self.client.get(reverse('accounts:login'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'name="viewport"')
        self.assertContains(resp, 'width=device-width, initial-scale=1.0')
