import os
import sys
import django

# Setup Django Environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'VVITU_Portal.settings')
django.setup()

from django.test import RequestFactory
from accounts.models import User, Faculty
from core.models import Branch, Year, Section, Timetable, ensure_sections_for_all_branches
from admin_dashboard.views import manage_timetable as admin_manage_timetable
from hod.views import manage_timetable as hod_manage_timetable

def test_branch_timetable_creation():
    print("--- Testing Branch Creation & Timetable Availability ---")
    
    # 1. Create a brand new branch
    branch_name = "Artificial Intelligence and Data Science"
    branch_code = "AIDS"
    
    # Remove if existing from prior test
    Branch.objects.filter(code=branch_code).delete()
    
    # Create the branch
    new_branch = Branch.objects.create(name=branch_name, code=branch_code)
    print(f"[OK] Created new Branch: {new_branch.code} — {new_branch.name}")
    
    # 2. Verify sections were automatically created
    sections = Section.objects.filter(branch=new_branch)
    print(f"[OK] Found {sections.count()} sections automatically created for {new_branch.code}.")
    assert sections.count() >= 8, f"Expected at least 8 sections (A & B for 4 years), found {sections.count()}"
    
    for s in sections:
        print(f"   -> Section initialized: {s}")
        
    # 3. Test Admin Timetable View
    factory = RequestFactory()
    admin_user = User.objects.filter(role='admin').first()
    if admin_user:
        req = factory.get('/admin-portal/timetable/')
        req.user = admin_user
        res = admin_manage_timetable(req)
        assert res.status_code == 200, f"Admin manage_timetable failed with {res.status_code}"
        print("[SUCCESS] Admin manage_timetable loaded successfully with new branch sections!")

    # 4. Test HOD Timetable View
    hod_user = User.objects.filter(role='hod').first()
    if hod_user and hasattr(hod_user, 'faculty_profile'):
        hod_user.faculty_profile.department = new_branch
        hod_user.faculty_profile.save()
        
        req = factory.get('/hod/timetable/')
        req.user = hod_user
        req.faculty = hod_user.faculty_profile
        req.department = new_branch
        res = hod_manage_timetable(req)
        assert res.status_code == 200, f"HOD manage_timetable failed with {res.status_code}"
        print(f"[SUCCESS] HOD manage_timetable loaded successfully for branch {new_branch.code}!")

    print("--- ALL BRANCH & TIMETABLE TESTS PASSED SUCCESSFULLY! ---")

if __name__ == '__main__':
    test_branch_timetable_creation()
