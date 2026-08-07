import os
import sys
import django

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + '/..'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'VVITU_Portal.settings')
django.setup()

from django.test import Client
from accounts.models import User

client = Client()
results = []

# 1. Test role dashboards
roles = ['admin', 'hod', 'faculty', 'student', 'deo']
for role in roles:
    user = User.objects.filter(role=role, is_deleted=False).first()
    if not user:
        print(f"[SKIP] No active user found for role: {role}")
        continue

    client.force_login(user)
    dash_url = user.get_dashboard_url()
    resp = client.get(dash_url)
    if resp.status_code == 200:
        print(f"[PASS] {role.upper()} Dashboard ({dash_url}) -> 200 OK")
        results.append((role, dash_url, 200))
    else:
        print(f"[FAIL] {role.upper()} Dashboard ({dash_url}) -> {resp.status_code}")
        results.append((role, dash_url, resp.status_code))

# 2. Test specific faculty pages
fac_user = User.objects.filter(role='faculty', is_deleted=False).first()
if fac_user:
    client.force_login(fac_user)
    fac_urls = [
        '/faculty/mark-attendance/',
        '/faculty/my-attendance/',
        '/faculty/transfer-class/',
        '/faculty/reports/',
        '/faculty/counselled-students/',
        '/faculty/student-results/',
        '/faculty/upload-marks/',
    ]
    for url in fac_urls:
        resp = client.get(url)
        if resp.status_code == 200:
            print(f"[PASS] FACULTY View ({url}) -> 200 OK")
            results.append(('faculty', url, 200))
        else:
            print(f"[FAIL] FACULTY View ({url}) -> {resp.status_code}")
            results.append(('faculty', url, resp.status_code))

print("\n=========================================")
failures = [r for r in results if r[2] != 200]
if failures:
    print(f"FAILED: {len(failures)} HTTP view failures!")
    for r in failures:
        print(f"  - {r[0]}: {r[1]} -> {r[2]}")
else:
    print("SUCCESS: All key views & dashboards loaded with HTTP 200 OK!")
print("=========================================")
