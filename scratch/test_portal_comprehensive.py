import os
import sys
import django
import traceback

sys.path.append('c:/Users/HP/OneDrive/Desktop/vvitu/vvitu-portal/vvitu_portal')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'VVITU_Portal.settings')
django.setup()

from django.test import Client
from accounts.models import User, Student, Faculty

def test_portal():
    client = Client()
    print("=" * 60)
    print("  VVIT Portal Comprehensive Views & Button Testing  ")
    print("=" * 60)

    from core.models import Section
    section = Section.objects.first()
    sec_id = section.id if section else 1

    roles_to_test = {
        'admin': {
            'username': 'admin',
            'urls': [
                '/admin-portal/',
                '/admin-portal/students/',
                '/admin-portal/students/add/',
                '/admin-portal/faculty/',
                '/admin-portal/faculty/add/',
                '/admin-portal/assign-class-teacher/',
                '/admin-portal/assign-counsellor/',
                '/admin-portal/timetable/',
                '/admin-portal/bulk-upload-results/',
                '/admin-portal/add-results/',
                '/admin-portal/release-results/',
                '/admin-portal/attendance/',
                '/admin-portal/attendance/report/',
                '/admin-portal/subjects/',
                '/admin-portal/subjects/add/',
                '/admin-portal/backups/',
                '/admin-portal/export/database-pdf/',
                '/admin-portal/export/results-pdf/',
                '/chat/context/',
                '/notifications/',
                '/notifications/api/',
                '/notifications/count/',
                '/notifications/manage/',
                '/notifications/create/',
            ]
        },
        'hod': {
            'username': 'HOD001',
            'urls': [
                '/hod/',
                '/hod/notice/create/',
                '/hod/assign-teacher/',
                '/hod/subject-mapping/',
                '/hod/timetable/',
                '/hod/verify-achievements/',
                '/hod/students/',
                '/hod/students/add/',
                '/hod/faculty/',
                '/hod/faculty/add/',
                '/hod/attendance/',
                '/hod/release-results/',
                '/hod/subjects/',
                '/hod/subjects/add/',
                '/chat/context/',
                '/notifications/',
                '/notifications/api/',
                '/notifications/count/',
                '/notifications/manage/',
                '/notifications/create/',
            ]
        },
        'deo': {
            'username': 'DEO001',
            'urls': [
                '/deo/',
                '/deo/students/',
                '/deo/students/add/',
                '/deo/attendance/',
                '/deo/upload-marks/',
                '/chat/context/',
                '/notifications/',
                '/notifications/api/',
                '/notifications/count/',
                '/notifications/manage/',
                '/notifications/create/',
            ]
        },
        'faculty': {
            'username': 'EMP001',
            'urls': [
                '/faculty/',
                '/faculty/mark-attendance/',
                '/faculty/reports/',
                '/faculty/counselled-students/',
                '/faculty/student-results/',
                '/faculty/upload-marks/',
                '/faculty/achievements/add/',
                f'/faculty/ajax/students/?section_id={sec_id}',
                f'/faculty/ajax/timetable/?section_id={sec_id}&day=Monday',
                '/chat/context/',
                '/notifications/',
                '/notifications/api/',
                '/notifications/count/',
            ]
        },
        'student': {
            'username': '24BQ1A4901',
            'urls': [
                '/student/',
                '/student/timetable/',
                '/student/results/',
                '/student/academic-calendar/',
                '/student/question-papers/',
                '/student/achievements/add/',
                '/chat/context/',
                '/notifications/',
                '/notifications/api/',
                '/notifications/count/',
            ]
        }
    }

    total_passed = 0
    total_failed = 0

    for role, config in roles_to_test.items():
        print(f"\n--- Testing Role: {role.upper()} (User: {config['username']}) ---")
        
        # If student, handle is_first_login flag
        original_first_login = None
        if role == 'student':
            student_profile = Student.objects.get(roll_number=config['username'])
            original_first_login = student_profile.is_first_login
            # Set to False so it does not force redirect to set-password
            student_profile.is_first_login = False
            student_profile.save()
            print("[INFO] Set is_first_login to False for testing dashboard access.")

        # Perform login
        login_success = client.login(username=config['username'], password='vvit@1234')
        if not login_success:
            print(f"[FAIL] Login failed for user {config['username']}")
            total_failed += 1
            # Restore if needed
            if original_first_login is not None:
                student_profile.is_first_login = original_first_login
                student_profile.save()
            continue

        print(f"[OK] Login successful for user {config['username']}")
        total_passed += 1

        # Test each URL
        for url in config['urls']:
            try:
                response = client.get(url)
                if response.status_code == 200:
                    print(f"  [OK]  {url} -> 200 OK")
                    total_passed += 1
                elif response.status_code == 302:
                    print(f"  [WARN] {url} -> 302 Redirect to {response['Location']}")
                    # If it's a redirect, check if redirect target succeeds or redirects correctly
                    target_response = client.get(response['Location'])
                    if target_response.status_code == 200:
                        print(f"    -> [OK] Redirect Target {response['Location']} -> 200 OK")
                        total_passed += 1
                    else:
                        print(f"    -> [FAIL] Redirect Target {response['Location']} -> {target_response.status_code}")
                        total_failed += 1
                else:
                    print(f"  [FAIL] {url} -> status {response.status_code}")
                    total_failed += 1
            except Exception as e:
                print(f"  [CRASH] {url} crashed with exception:")
                traceback.print_exc()
                total_failed += 1

        # Logout
        client.logout()

        # Restore student's is_first_login flag if modified
        if original_first_login is not None:
            student_profile.is_first_login = original_first_login
            student_profile.save()
            print("[INFO] Restored original is_first_login flag.")

    print("\n" + "=" * 60)
    print(f"  Portal View Check Summary: {total_passed} PASSED, {total_failed} FAILED")
    print("=" * 60)

    if total_failed > 0:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    test_portal()
