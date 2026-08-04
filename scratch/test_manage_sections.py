import os
import sys
import django

# Setup Django Environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'VVITU_Portal.settings')
django.setup()

from django.test import RequestFactory
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.backends.db import SessionStore
from accounts.models import User
from core.models import Branch, Year, Section
from admin_dashboard.views import manage_sections, delete_section

def make_req(factory, method, path, data=None):
    if method == 'POST':
        req = factory.post(path, data or {})
    else:
        req = factory.get(path, data or {})
    req.session = SessionStore()
    setattr(req, '_messages', FallbackStorage(req))
    return req

def test_admin_manage_sections():
    print("--- Testing Admin Custom Section Management ---")
    factory = RequestFactory()
    admin_user = User.objects.filter(role='admin').first()
    assert admin_user is not None, "Admin user required for test"

    branch = Branch.objects.first()
    year = Year.objects.filter(year=3).first() or Year.objects.first()

    # 1. Test GET manage_sections
    req = make_req(factory, 'GET', '/admin-portal/sections/')
    req.user = admin_user
    res = manage_sections(req)
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    print("[SUCCESS] Manage Sections page loads successfully!")

    # 2. Test POST create custom section
    custom_sec_name = "SECTION_X"
    # Cleanup if exists
    Section.objects.filter(branch=branch, year=year, name=custom_sec_name).delete()

    req = make_req(factory, 'POST', '/admin-portal/sections/', {
        'branch': branch.id,
        'year': year.id,
        'name': custom_sec_name
    })
    req.user = admin_user
    res = manage_sections(req)
    assert res.status_code == 302, f"Expected 302 redirect after section creation, got {res.status_code}"

    created_sec = Section.objects.filter(branch=branch, year=year, name=custom_sec_name).first()
    assert created_sec is not None, "Custom section was not created!"
    print(f"[SUCCESS] Custom Section created successfully: {created_sec}")

    # 3. Test Delete section
    req = make_req(factory, 'POST', f'/admin-portal/sections/{created_sec.id}/delete/')
    req.user = admin_user
    res = delete_section(req, created_sec.id)
    assert res.status_code == 302, f"Expected 302 redirect after deletion, got {res.status_code}"
    assert not Section.objects.filter(id=created_sec.id).exists(), "Section deletion failed!"
    print(f"[SUCCESS] Custom Section deleted successfully!")

    print("--- ALL SECTION MANAGEMENT TESTS PASSED SUCCESSFULLY! ---")

if __name__ == '__main__':
    test_admin_manage_sections()
