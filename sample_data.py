"""
VVIT Portal - Sample Data Setup Script
Run with:  python manage.py shell -c "exec(open('sample_data.py').read())"
"""

import os
import sys
import datetime
import random

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vvit_portal.settings')

from django.utils import timezone
from accounts.models import User, Student, Faculty
from core.models import (
    Branch, Year, Section, Subject, Timetable,
    Attendance, Exam, Result, AcademicCalendar
)

print("=" * 55)
print("  VVIT Portal - Loading Sample Data")
print("=" * 55)

# BRANCHES
cse, _ = Branch.objects.get_or_create(name='Computer Science and Engineering', code='CSE')
ece, _ = Branch.objects.get_or_create(name='Electronics and Communication Engineering', code='ECE')
eee, _ = Branch.objects.get_or_create(name='Electrical and Electronics Engineering', code='EEE')
print("[OK] Branches created")

# YEARS
y1, _ = Year.objects.get_or_create(year=1)
y2, _ = Year.objects.get_or_create(year=2)
y3, _ = Year.objects.get_or_create(year=3)
y4, _ = Year.objects.get_or_create(year=4)
print("[OK] Years created")

# SECTIONS
s_cse2a, _ = Section.objects.get_or_create(name='A', branch=cse, year=y2)
s_cse2b, _ = Section.objects.get_or_create(name='B', branch=cse, year=y2)
s_ece3a, _ = Section.objects.get_or_create(name='A', branch=ece, year=y3)
s_eee1a, _ = Section.objects.get_or_create(name='A', branch=eee, year=y1)
print("[OK] Sections created")

# ADMIN USER
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser(
        username='admin', password='vvit@1234',
        email='admin@vvit.net',
        first_name='Portal', last_name='Admin',
        role='admin',
    )
print("[OK] Admin user: admin / vvit@1234")

# FACULTY
def make_faculty(emp_id, fname, lname, dept, role='faculty', phone='9000000001'):
    if User.objects.filter(username=emp_id).exists():
        return Faculty.objects.get(employee_id=emp_id)
    u = User.objects.create_user(
        username=emp_id, password='vvit@1234',
        first_name=fname, last_name=lname,
        email=emp_id + '@vvit.net', role=role, phone=phone,
    )
    return Faculty.objects.create(
        user=u, employee_id=emp_id, department=dept,
        designation='Associate Professor'
    )

f_rajesh  = make_faculty('EMP001', 'Rajesh',  'Kumar',  cse, phone='9876543210')
f_sunitha = make_faculty('EMP002', 'Sunitha', 'Reddy',  cse, phone='9876543211')
f_prasad  = make_faculty('EMP003', 'Prasad',  'Varma',  ece, phone='9876543212')
print("[OK] Faculty created (password: vvit@1234)")

# SUBJECTS
def make_subject(code, name, branch, year, semester, faculty, is_lab=False):
    obj, _ = Subject.objects.get_or_create(
        code=code,
        defaults=dict(name=name, branch=branch, year=year,
                      semester=semester, faculty=faculty, is_lab=is_lab)
    )
    return obj

dsa  = make_subject('CS301', 'Data Structures and Algorithms', cse, y2, 3, f_rajesh)
os_  = make_subject('CS302', 'Operating Systems',             cse, y2, 3, f_sunitha)
dbms = make_subject('CS303', 'Database Management Systems',   cse, y2, 3, f_rajesh)
cn   = make_subject('CS304', 'Computer Networks',             cse, y2, 3, f_sunitha)
lab  = make_subject('CS391', 'DS Lab',                        cse, y2, 3, f_rajesh, is_lab=True)
sig  = make_subject('EC301', 'Signals and Systems',           ece, y3, 5, f_prasad)
print("[OK] Subjects created")

# TIMETABLE
slots = [
    ('Monday',    1, dsa,  f_rajesh),
    ('Monday',    2, os_,  f_sunitha),
    ('Monday',    3, dbms, f_rajesh),
    ('Tuesday',   1, cn,   f_sunitha),
    ('Tuesday',   2, dsa,  f_rajesh),
    ('Tuesday',   3, os_,  f_sunitha),
    ('Wednesday', 1, dbms, f_rajesh),
    ('Wednesday', 2, cn,   f_sunitha),
    ('Wednesday', 3, lab,  f_rajesh),
    ('Thursday',  1, dsa,  f_rajesh),
    ('Thursday',  2, os_,  f_sunitha),
    ('Thursday',  3, cn,   f_sunitha),
    ('Friday',    1, dbms, f_rajesh),
    ('Friday',    2, dsa,  f_rajesh),
    ('Friday',    3, lab,  f_rajesh),
]
for day, period, subj, fac in slots:
    Timetable.objects.get_or_create(
        section=s_cse2a, day=day, period=period,
        defaults={'subject': subj, 'faculty': fac}
    )
print("[OK] Timetable: " + str(len(slots)) + " slots for CSE-II-A")

# STUDENTS
student_data = [
    ('24BQ1A4901', 'Arjun',   'Sharma',    s_cse2a, '9111111101'),
    ('24BQ1A4902', 'Bhavana', 'Reddy',     s_cse2a, '9111111102'),
    ('24BQ1A4903', 'Charan',  'Kumar',     s_cse2a, '9111111103'),
    ('24BQ1A4904', 'Divya',   'Patel',     s_cse2a, '9111111104'),
    ('24BQ1A4905', 'Eswar',   'Naidu',     s_cse2b, '9111111105'),
    ('24BQ1A4906', 'Fathima', 'Sheikh',    s_cse2b, '9111111106'),
    ('24BQ1A4942', 'Ganesh',  'Vasireddy', s_cse2a, '9111111142'),
]

students = []
for roll, fname, lname, section, phone in student_data:
    if User.objects.filter(username=roll).exists():
        stu = Student.objects.get(roll_number=roll)
    else:
        u = User.objects.create_user(
            username=roll, password='vvit@1234',
            first_name=fname, last_name=lname,
            email=roll + '@vvit.net', role='student', phone=phone,
        )
        stu = Student.objects.create(
            user=u, roll_number=roll,
            branch=section.branch, year=section.year,
            section=section,
            class_teacher=f_rajesh,
            counsellor=f_sunitha,
            admission_year=2024,
        )
    students.append(stu)

print("[OK] " + str(len(students)) + " students created (password: vvit@1234)")

# ATTENDANCE - last 45 days
today     = timezone.localdate()
days_back = 45
att_count = 0
tt_slots  = list(Timetable.objects.filter(section=s_cse2a))
cse2a_students = [s for s in students if s.section == s_cse2a]

for day_offset in range(days_back, 0, -1):
    att_date = today - datetime.timedelta(days=day_offset)
    day_name = att_date.strftime('%A')
    day_slots = [t for t in tt_slots if t.day == day_name]
    if not day_slots:
        continue
    for slot in day_slots:
        for i, stu in enumerate(cse2a_students):
            threshold = 55 if i == 2 else 80
            status = 'P' if random.randint(1, 100) <= threshold else 'A'
            Attendance.objects.get_or_create(
                student=stu,
                timetable_entry=slot,
                date=att_date,
                defaults={'status': status, 'marked_by': slot.faculty}
            )
            att_count += 1

print("[OK] " + str(att_count) + " attendance records generated")

# EXAMS AND RESULTS
mid1, _ = Exam.objects.get_or_create(
    name='Mid Term 1', exam_type='mid1', semester=3,
    year=y2, branch=cse,
    defaults={'date': today - datetime.timedelta(days=30)}
)
mid2, _ = Exam.objects.get_or_create(
    name='Mid Term 2', exam_type='mid2', semester=3,
    year=y2, branch=cse,
    defaults={'date': today - datetime.timedelta(days=5)}
)

result_subjects = [dsa, os_, dbms, cn]
for stu in cse2a_students:
    for subj in result_subjects:
        marks = random.randint(55, 95)
        Result.objects.get_or_create(
            student=stu, exam=mid1, subject=subj,
            defaults={'marks_obtained': marks, 'max_marks': 100}
        )

print("[OK] Exams and results created")

# ACADEMIC CALENDAR
events = [
    ('Diwali Holiday',             'Holiday - college closed',      today + datetime.timedelta(days=5),  'holiday'),
    ('Mid Term 2 Examinations',    'Mid-term 2 for all branches',   today + datetime.timedelta(days=14), 'exam'),
    ('Technical Fest Innovista',   'Annual technical festival',     today + datetime.timedelta(days=30), 'event'),
    ('Semester End Examinations',  'Final theory exams begin',      today + datetime.timedelta(days=60), 'exam'),
    ('Sports Day',                 'Annual athletic meet',          today + datetime.timedelta(days=22), 'event'),
    ('Last Date Fee Payment',      'Last date to pay semester fee', today + datetime.timedelta(days=10), 'deadline'),
]
for title, desc, date, etype in events:
    AcademicCalendar.objects.get_or_create(
        title=title, date=date,
        defaults={'description': desc, 'event_type': etype}
    )
print("[OK] " + str(len(events)) + " academic calendar events created")

print("")
print("=" * 55)
print("  Sample data loaded successfully!")
print("=" * 55)
print("")
print("Test login credentials (all passwords: vvit@1234)")
print("  Admin   : admin")
print("  Faculty : EMP001, EMP002, EMP003")
print("  Students: 24BQ1A4901 to 24BQ1A4906, 24BQ1A4942")
print("")
print("Run: python manage.py runserver")
print("URL: http://127.0.0.1:8000")
print("=" * 55)
