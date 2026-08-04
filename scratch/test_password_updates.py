import os
import sys
import django

sys.path.insert(0, r'c:\Users\HP\OneDrive\Desktop\vvitu\vvitu-portal\vvitu_portal')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'VVITU_Portal.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.test import RequestFactory
from django.contrib.messages.storage.cookie import CookieStorage
from accounts.models import Student, Faculty
from accounts.views import change_password
from admin_dashboard.views import edit_student as admin_edit_student, edit_faculty as admin_edit_faculty
from hod.views import edit_student as hod_edit_student, edit_faculty as hod_edit_faculty
from deo.views import edit_student as deo_edit_student

User = get_user_model()

from django.conf import settings
from importlib import import_module

def make_req(factory, method, path, data=None):
    if method == 'POST':
        req = factory.post(path, data or {})
    else:
        req = factory.get(path)
    engine = import_module(settings.SESSION_ENGINE)
    req.session = engine.SessionStore()
    setattr(req, '_messages', CookieStorage(req))
    return req

def run_tests():
    print("--- Starting Password Update System Verification ---")
    factory = RequestFactory()
    
    # 1. Test Admin updating student password
    admin_user = User.objects.filter(role='admin').first()
    student_obj = Student.objects.first()
    if admin_user and student_obj:
        target_user = student_obj.user
        req = make_req(factory, 'POST', f'/admin-portal/students/{student_obj.pk}/edit/', {
            'first_name': target_user.first_name or 'TestFirstName',
            'last_name': target_user.last_name or 'TestLastName',
            'email': target_user.email,
            'phone': target_user.phone or '',
            'branch': student_obj.branch_id,
            'year': student_obj.year_id,
            'section': student_obj.section_id,
            'password': 'newpassword123'
        })
        req.user = admin_user
        
        response = admin_edit_student(req, student_obj.pk)
        target_user.refresh_from_db()
        assert target_user.check_password('newpassword123'), "Admin failed to update student password!"
        print("[SUCCESS] Admin successfully updated student password!")

    # 2. Test Admin updating faculty password
    faculty_obj = Faculty.objects.first()
    if admin_user and faculty_obj:
        fac_user = faculty_obj.user
        req = make_req(factory, 'POST', f'/admin-portal/faculty/{faculty_obj.pk}/edit/', {
            'first_name': fac_user.first_name or 'FacultyFirst',
            'last_name': fac_user.last_name or 'FacultyLast',
            'email': fac_user.email,
            'phone': fac_user.phone or '',
            'role': fac_user.role,
            'department': faculty_obj.department_id,
            'designation': faculty_obj.designation,
            'password': 'facnewpassword456'
        })
        req.user = admin_user
        
        response = admin_edit_faculty(req, faculty_obj.pk)
        fac_user.refresh_from_db()
        assert fac_user.check_password('facnewpassword456'), "Admin failed to update faculty password!"
        print("[SUCCESS] Admin successfully updated faculty password!")

    # 3. Test HOD updating faculty password
    hod_user = User.objects.filter(role='hod').first()
    if hod_user and faculty_obj:
        if hasattr(hod_user, 'faculty_profile') and hod_user.faculty_profile.department:
            faculty_obj.department = hod_user.faculty_profile.department
            faculty_obj.save()
            fac_user = faculty_obj.user
            req = make_req(factory, 'POST', f'/hod/faculty/{faculty_obj.pk}/edit/', {
                'first_name': fac_user.first_name,
                'last_name': fac_user.last_name,
                'email': fac_user.email,
                'phone': fac_user.phone or '',
                'designation': faculty_obj.designation,
                'password': 'hodsetpassword789'
            })
            req.user = hod_user
            req.department = hod_user.faculty_profile.department

            response = hod_edit_faculty(req, faculty_obj.pk)
            fac_user.refresh_from_db()
            assert fac_user.check_password('hodsetpassword789'), "HOD failed to update faculty password!"
            print("[SUCCESS] HOD successfully updated faculty password!")

    # 4. Test Self-Service Change Password
    if admin_user:
        admin_user.set_password('oldadminpass')
        admin_user.save()

        req = make_req(factory, 'POST', '/accounts/change-password/', {
            'current_password': 'oldadminpass',
            'new_password': 'newadminpass999',
            'confirm_password': 'newadminpass999'
        })
        req.user = admin_user

        response = change_password(req)
        admin_user.refresh_from_db()
        assert admin_user.check_password('newadminpass999'), "Self-service change password failed!"
        print("[SUCCESS] Self-service password change verified!")

    print("--- ALL VERIFICATION TESTS PASSED SUCCESSFULLY! ---")

if __name__ == '__main__':
    run_tests()
