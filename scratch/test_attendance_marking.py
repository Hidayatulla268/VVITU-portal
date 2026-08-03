import os
import sys
import django
import datetime

sys.path.append('c:/Users/HP/OneDrive/Desktop/vvitu/vvitu-portal/vvitu_portal')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'VVITU_Portal.settings')
django.setup()

from django.test import Client
from accounts.models import Faculty, Student
from core.models import Timetable, Section, Attendance

def test_attendance():
    timetable = Timetable.objects.select_related('faculty__user', 'section').first()
    if not timetable:
        print("No timetable found")
        return
        
    faculty = timetable.faculty
    faculty_user = faculty.user
    client = Client()
    client.force_login(faculty_user)
    
    section = timetable.section
    students = Student.objects.filter(section=section, is_active=True)
    today = datetime.date.today()
    
    print(f"Testing attendance marking for Faculty {faculty_user.get_full_name()} ({students.count()} students in Section {section})...")
    
    # Mark first student Present, rest Absent
    post_data = {
        'section': section.id,
        'date': today.isoformat(),
        'slot': timetable.id,
    }
    for idx, s in enumerate(students):
        status = 'P' if idx == 0 else 'A'
        post_data[f'attendance_{s.id}'] = status
        
    resp = client.post('/faculty/mark-attendance/', post_data)
    print(f"Post status code: {resp.status_code}")
    
    # Verify in DB
    records = Attendance.objects.filter(timetable_entry=timetable, date=today)
    print(f"Saved {records.count()} records in DB.")
    p_count = records.filter(status='P').count()
    a_count = records.filter(status='A').count()
    print(f"Present count: {p_count}, Absent count: {a_count}")
    
    if p_count > 0:
        print("[SUCCESS] Backend correctly saves Present ('P') when attendance_ID=P is in POST data!")
    else:
        print("[FAILURE] All students marked absent!")

if __name__ == '__main__':
    test_attendance()
