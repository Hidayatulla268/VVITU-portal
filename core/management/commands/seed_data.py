"""
VVIT Portal — Management Command: seed_data

Seeds initial academic records (branches, sections, timetables, students, faculty, attendance, results)
idempotently. Includes safety check to skip seeding if data already exists in the database.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from accounts.models import User, Student, Faculty
from core.models import (
    Branch, Year, Section, Subject, Timetable,
    Attendance, Exam, Result, AcademicCalendar, ResultRelease
)
import datetime
import random


class Command(BaseCommand):
    help = 'Seeds sample academic data for testing.'

    def handle(self, *args, **options):
        # 1. Guard against double-running if data already exists
        if Branch.objects.exists() or Student.objects.exists():
            self.stdout.write(
                self.style.WARNING(
                    "Database already has records (Branch or Student). Seeding skipped to prevent duplicate data."
                )
            )
            return

        self.stdout.write(self.style.MIGRATE_HEADING("=" * 55))
        self.stdout.write(self.style.MIGRATE_HEADING("  VVIT Portal - Loading Sample Data"))
        self.stdout.write(self.style.MIGRATE_HEADING("=" * 55))

        # BRANCHES
        cse, _ = Branch.objects.get_or_create(name='Computer Science and Engineering', code='CSE')
        ece, _ = Branch.objects.get_or_create(name='Electronics and Communication Engineering', code='ECE')
        eee, _ = Branch.objects.get_or_create(name='Electrical and Electronics Engineering', code='EEE')
        self.stdout.write(self.style.SUCCESS("[OK] Branches created"))

        # YEARS
        y1, _ = Year.objects.get_or_create(year=1)
        y2, _ = Year.objects.get_or_create(year=2)
        y3, _ = Year.objects.get_or_create(year=3)
        y4, _ = Year.objects.get_or_create(year=4)
        self.stdout.write(self.style.SUCCESS("[OK] Years created"))

        # SECTIONS
        s_cse2a, _ = Section.objects.get_or_create(name='A', branch=cse, year=y2)
        s_cse2b, _ = Section.objects.get_or_create(name='B', branch=cse, year=y2)
        s_ece3a, _ = Section.objects.get_or_create(name='A', branch=ece, year=y3)
        s_eee1a, _ = Section.objects.get_or_create(name='A', branch=eee, year=y1)
        self.stdout.write(self.style.SUCCESS("[OK] Sections created"))

        # ADMIN USER
        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser(
                username='admin', password='vvit@1234',
                email='admin@vvit.net',
                first_name='Portal', last_name='Admin',
                role='admin',
            )
        self.stdout.write(self.style.SUCCESS("[OK] Admin user: admin / vvit@1234"))

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
        self.stdout.write(self.style.SUCCESS("[OK] Faculty created (password: vvit@1234)"))

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
        self.stdout.write(self.style.SUCCESS("[OK] Subjects created"))

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
        self.stdout.write(self.style.SUCCESS("[OK] Timetable: " + str(len(slots)) + " slots for CSE-II-A"))

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
            p_name = f"{random.choice(['Venkata', 'Srinivasa', 'Satya', 'Rama', 'Koteswara', 'Subba', 'Nageswara', 'Prasad'])} {lname}"
            p_mobile = f"9{random.randint(100000000, 999999999)}"
            if User.objects.filter(username=roll).exists():
                stu = Student.objects.get(roll_number=roll)
                stu.parent_name = p_name
                stu.parent_mobile = p_mobile
                stu.save()
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
                    parent_name=p_name,
                    parent_mobile=p_mobile,
                )
            students.append(stu)

        self.stdout.write(self.style.SUCCESS("[OK] " + str(len(students)) + " students created (password: vvit@1234)"))

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

        self.stdout.write(self.style.SUCCESS("[OK] " + str(att_count) + " attendance records generated"))

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
        final_exam, _ = Exam.objects.get_or_create(
            name='Semester Final Examinations', exam_type='final', semester=3,
            year=y2, branch=cse,
            defaults={'date': today - datetime.timedelta(days=2)}
        )

        result_subjects = [dsa, os_, dbms, cn]
        for stu in cse2a_students:
            for subj in result_subjects:
                # Seed mid1
                marks_mid1 = random.randint(55, 95)
                Result.objects.get_or_create(
                    student=stu, exam=mid1, subject=subj,
                    defaults={'marks_obtained': marks_mid1, 'max_marks': 100}
                )
                # Seed mid2
                marks_mid2 = random.randint(55, 95)
                Result.objects.get_or_create(
                    student=stu, exam=mid2, subject=subj,
                    defaults={'marks_obtained': marks_mid2, 'max_marks': 100}
                )
                # Seed semester final
                marks_final = random.randint(45, 95)
                Result.objects.get_or_create(
                    student=stu, exam=final_exam, subject=subj,
                    defaults={'marks_obtained': marks_final, 'max_marks': 100}
                )

        # Release all 3 exams automatically so they show up on the website
        for ex in [mid1, mid2, final_exam]:
            ResultRelease.objects.get_or_create(
                exam=ex,
                defaults={'released': True, 'released_at': timezone.now()}
            )

        self.stdout.write(self.style.SUCCESS("[OK] Exams, results, and result releases created"))

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
        self.stdout.write(self.style.SUCCESS("[OK] " + str(len(events)) + " academic calendar events created"))

        self.stdout.write(self.style.MIGRATE_HEADING(""))
        self.stdout.write(self.style.MIGRATE_HEADING("=" * 55))
        self.stdout.write(self.style.SUCCESS("  Sample data loaded successfully!"))
        self.stdout.write(self.style.MIGRATE_HEADING("=" * 55))
        self.stdout.write(self.style.MIGRATE_HEADING(""))
        self.stdout.write(self.style.MIGRATE_HEADING("Test login credentials (all passwords: vvit@1234)"))
        self.stdout.write(self.style.MIGRATE_HEADING("  Admin   : admin"))
        self.stdout.write(self.style.MIGRATE_HEADING("  Faculty : EMP001, EMP002, EMP003"))
        self.stdout.write(self.style.MIGRATE_HEADING("  Students: 24BQ1A4901 to 24BQ1A4906, 24BQ1A4942"))
        self.stdout.write(self.style.MIGRATE_HEADING(""))
        self.stdout.write(self.style.MIGRATE_HEADING("Run: python manage.py runserver"))
        self.stdout.write(self.style.MIGRATE_HEADING("URL: http://127.0.0.1:8000"))
        self.stdout.write(self.style.MIGRATE_HEADING("=" * 55))
