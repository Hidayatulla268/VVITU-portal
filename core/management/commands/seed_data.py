"""
VVIT Portal — Management Command: seed_data

Seeds initial academic records (branches, sections, timetables, students, faculty, attendance, results)
idempotently across all 8 branches (CSE, ECE, EEE, IT, CSM, CSD, CIVIL, MECH).
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from accounts.models import User, Student, Faculty, DEOProfile
from core.models import (
    Branch, Year, Section, Subject, Timetable,
    Attendance, Exam, Result, AcademicCalendar, ResultRelease
)
import datetime
import random


class Command(BaseCommand):
    help = 'Seeds sample academic data for all branches.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("=" * 60))
        self.stdout.write(self.style.MIGRATE_HEADING("  VVIT Portal - Loading Comprehensive Sample Data"))
        self.stdout.write(self.style.MIGRATE_HEADING("=" * 60))

        # 1. ADMIN USER
        admin_user = User.objects.filter(username='admin').first()
        if not admin_user:
            admin_user = User.objects.create_superuser(
                username='admin', password='vvit@1234',
                email='admin@vvit.net',
                first_name='Portal', last_name='Admin',
                role='admin',
            )
        else:
            admin_user.set_password('vvit@1234')
            admin_user.save()
        self.stdout.write(self.style.SUCCESS("[OK] Admin user: admin / vvit@1234"))

        # 2. BRANCHES
        branches_data = [
            {'code': 'CSE', 'name': 'Computer Science and Engineering', 'digit': '49'},
            {'code': 'ECE', 'name': 'Electronics and Communication Engineering', 'digit': '04'},
            {'code': 'EEE', 'name': 'Electrical and Electronics Engineering', 'digit': '02'},
            {'code': 'IT', 'name': 'Information Technology', 'digit': '12'},
            {'code': 'CSM', 'name': 'CSE (Artificial Intelligence and Machine Learning)', 'digit': '42'},
            {'code': 'CSD', 'name': 'CSE (Data Science)', 'digit': '44'},
            {'code': 'CIVIL', 'name': 'Civil Engineering', 'digit': '01'},
            {'code': 'MECH', 'name': 'Mechanical Engineering', 'digit': '03'},
        ]
        
        branch_objs = {}
        branch_digits = {}
        for b in branches_data:
            obj, _ = Branch.objects.get_or_create(code=b['code'], defaults={'name': b['name']})
            branch_objs[b['code']] = obj
            branch_digits[b['code']] = b['digit']
        self.stdout.write(self.style.SUCCESS(f"[OK] {len(branch_objs)} branches loaded"))

        # 3. YEARS
        y1, _ = Year.objects.get_or_create(year=1)
        y2, _ = Year.objects.get_or_create(year=2)
        y3, _ = Year.objects.get_or_create(year=3)
        y4, _ = Year.objects.get_or_create(year=4)
        self.stdout.write(self.style.SUCCESS("[OK] Years loaded (1 to 4)"))

        # 4. SECTIONS
        sections = {}
        for code, b_obj in branch_objs.items():
            sections[(code, 1, 'A')], _ = Section.objects.get_or_create(name='A', branch=b_obj, year=y1)
            sections[(code, 2, 'A')], _ = Section.objects.get_or_create(name='A', branch=b_obj, year=y2)
            sections[(code, 2, 'B')], _ = Section.objects.get_or_create(name='B', branch=b_obj, year=y2)
            sections[(code, 3, 'A')], _ = Section.objects.get_or_create(name='A', branch=b_obj, year=y3)
            sections[(code, 4, 'A')], _ = Section.objects.get_or_create(name='A', branch=b_obj, year=y4)
        self.stdout.write(self.style.SUCCESS(f"[OK] Sections created for all branches"))

        # Helper: Create/update Faculty profile
        def make_faculty(emp_id, fname, lname, dept, role='faculty', phone='9000000001'):
            u = User.objects.filter(username=emp_id).first()
            if u:
                u.set_password('vvit@1234')
                u.role = role
                u.phone = phone
                u.save()
                fac = Faculty.objects.filter(employee_id=emp_id).first()
                if not fac:
                    fac = Faculty.objects.create(user=u, employee_id=emp_id, department=dept, designation='Associate Professor')
                else:
                    fac.department = dept
                    fac.save()
                return fac
            u = User.objects.create_user(
                username=emp_id, password='vvit@1234',
                first_name=fname, last_name=lname,
                email=emp_id.lower() + '@vvit.net', role=role, phone=phone,
            )
            return Faculty.objects.create(
                user=u, employee_id=emp_id, department=dept,
                designation='Associate Professor'
            )

        # 5. HODs
        hod_objs = {}
        hod_map = [
            ('HOD001', 'HOD', 'CSE', 'CSE'),
            ('HOD002', 'HOD', 'ECE', 'ECE'),
            ('HOD003', 'HOD', 'EEE', 'EEE'),
            ('HOD004', 'HOD', 'IT', 'IT'),
            ('HOD005', 'HOD', 'CSM', 'CSM'),
            ('HOD006', 'HOD', 'CSD', 'CSD'),
            ('HOD007', 'HOD', 'CIVIL', 'CIVIL'),
            ('HOD008', 'HOD', 'MECH', 'MECH'),
        ]
        for idx, (username, fname, lname, bcode) in enumerate(hod_map):
            b_obj = branch_objs[bcode]
            hod_objs[bcode] = make_faculty(username, fname, lname, b_obj, role='hod', phone=f'987654320{idx+1}')
        self.stdout.write(self.style.SUCCESS(f"[OK] {len(hod_objs)} HODs loaded (HOD001 to HOD008)"))

        # 6. DEOs
        deo_objs = {}
        deo_map = [
            ('DEO001', 'Data Entry', 'CSE', 'CSE'),
            ('DEO002', 'Data Entry', 'ECE', 'ECE'),
            ('DEO003', 'Data Entry', 'EEE', 'EEE'),
            ('DEO004', 'Data Entry', 'IT', 'IT'),
            ('DEO005', 'Data Entry', 'CSM', 'CSM'),
            ('DEO006', 'Data Entry', 'CSD', 'CSD'),
            ('DEO007', 'Data Entry', 'CIVIL', 'CIVIL'),
            ('DEO008', 'Data Entry', 'MECH', 'MECH'),
        ]
        for idx, (username, fname, lname, bcode) in enumerate(deo_map):
            b_obj = branch_objs[bcode]
            deo_user = User.objects.filter(username=username).first()
            if not deo_user:
                deo_user = User.objects.create_user(
                    username=username, password='vvit@1234',
                    first_name=fname, last_name=lname,
                    email=username.lower() + '@vvit.net', role='deo', phone=f'987654321{idx+1}'
                )
            else:
                deo_user.set_password('vvit@1234')
                deo_user.role = 'deo'
                deo_user.save()
            
            deo_profile, _ = DEOProfile.objects.get_or_create(
                user=deo_user,
                defaults={'employee_id': username, 'branch': b_obj}
            )
            if deo_profile.branch != b_obj:
                deo_profile.branch = b_obj
                deo_profile.save()
            deo_objs[bcode] = deo_profile
        self.stdout.write(self.style.SUCCESS(f"[OK] {len(deo_objs)} DEOs loaded (DEO001 to DEO008)"))

        # 7. FACULTY MEMBERS (2 per branch)
        faculty_data = {
            'CSE': [
                ('EMP001', 'Rajesh', 'Kumar'),
                ('EMP002', 'Sunitha', 'Reddy'),
            ],
            'ECE': [
                ('EMP003', 'Prasad', 'Varma'),
                ('EMP004', 'Asha', 'Kiran'),
            ],
            'EEE': [
                ('EMP005', 'Kiran', 'Kumar'),
                ('EMP006', 'Vasundhara', 'Devi'),
            ],
            'IT': [
                ('EMP007', 'Suresh', 'Babu'),
                ('EMP008', 'Lakshmi', 'Prasanna'),
            ],
            'CSM': [
                ('EMP009', 'Ravi', 'Teja'),
                ('EMP010', 'Divya', 'Sri'),
            ],
            'CSD': [
                ('EMP011', 'Satish', 'Chandra'),
                ('EMP012', 'Radha', 'Krishna'),
            ],
            'CIVIL': [
                ('EMP013', 'Siva', 'Rama Krishna'),
                ('EMP014', 'Nirmala', 'Devi'),
            ],
            'MECH': [
                ('EMP015', 'Ramesh', 'Babu'),
                ('EMP016', 'Vijaya', 'Lakshmi'),
            ],
        }
        
        faculty_objs = {}
        for bcode, faculty_list in faculty_data.items():
            b_obj = branch_objs[bcode]
            faculty_objs[bcode] = []
            for emp_id, fname, lname in faculty_list:
                f_obj = make_faculty(emp_id, fname, lname, b_obj, phone=f'98765433{emp_id[-2:]}')
                faculty_objs[bcode].append(f_obj)
        self.stdout.write(self.style.SUCCESS(f"[OK] {sum(len(lst) for lst in faculty_objs.values())} Faculty members loaded (EMP001 to EMP016)"))

        # 8. SUBJECTS (Year 2 Sem 3 subjects for all branches)
        subjects_data = {
            'CSE': [
                ('CS301', 'Data Structures and Algorithms', False),
                ('CS302', 'Operating Systems', False),
                ('CS303', 'Database Management Systems', False),
                ('CS304', 'Computer Networks', False),
                ('CS391', 'DS Lab', True),
            ],
            'ECE': [
                ('EC301', 'Signals and Systems', False),
                ('EC302', 'Analog Circuits', False),
                ('EC303', 'Digital System Design', False),
                ('EC304', 'Network Analysis', False),
                ('EC391', 'Analog Circuits Lab', True),
            ],
            'EEE': [
                ('EE301', 'Electrical Circuit Analysis', False),
                ('EE302', 'Electromagnetic Fields', False),
                ('EE303', 'DC Machines and Transformers', False),
                ('EE304', 'Electrical Measurements', False),
                ('EE391', 'DC Machines Lab', True),
            ],
            'IT': [
                ('IT301', 'Software Engineering', False),
                ('IT302', 'Java Programming', False),
                ('IT303', 'Web Technologies', False),
                ('IT304', 'Data Communication', False),
                ('IT391', 'Java Lab', True),
            ],
            'CSM': [
                ('AM301', 'Python for AI & ML', False),
                ('AM302', 'Discrete Mathematics', False),
                ('AM303', 'AI Fundamentals', False),
                ('AM304', 'Introduction to Machine Learning', False),
                ('AM391', 'AI & ML Lab', True),
            ],
            'CSD': [
                ('DS301', 'Data Science Tools', False),
                ('DS302', 'Probability and Statistics', False),
                ('DS303', 'Data Warehousing & Mining', False),
                ('DS304', 'R Programming', False),
                ('DS391', 'Data Science Lab', True),
            ],
            'CIVIL': [
                ('CE301', 'Strength of Materials', False),
                ('CE302', 'Fluid Mechanics', False),
                ('CE303', 'Surveying', False),
                ('CE304', 'Concrete Technology', False),
                ('CE391', 'Surveying Lab', True),
            ],
            'MECH': [
                ('ME301', 'Thermodynamics', False),
                ('ME302', 'Metallurgy & Material Science', False),
                ('ME303', 'Mechanics of Solids', False),
                ('ME304', 'Kinematics of Machinery', False),
                ('ME391', 'Mechanics of Solids Lab', True),
            ],
        }
        
        subject_objs = {}
        def make_subject(code, name, branch, year, semester, faculty, is_lab=False):
            obj, _ = Subject.objects.get_or_create(
                code=code,
                defaults=dict(name=name, branch=branch, year=year,
                              semester=semester, faculty=faculty, is_lab=is_lab)
            )
            if obj.faculty != faculty:
                obj.faculty = faculty
                obj.save()
            return obj
            
        for bcode, subjs in subjects_data.items():
            b_obj = branch_objs[bcode]
            facs = faculty_objs[bcode]
            subject_objs[bcode] = []
            for i, (scode, sname, is_lab) in enumerate(subjs):
                fac = facs[i % len(facs)]
                s_obj = make_subject(scode, sname, b_obj, y2, 3, fac, is_lab=is_lab)
                subject_objs[bcode].append(s_obj)
        self.stdout.write(self.style.SUCCESS("[OK] Academic subjects created for all branches"))

        # 9. TIMETABLES (Year 2 Sec A slots)
        timetable_slots = [
            ('Monday',    1, 0),
            ('Monday',    2, 1),
            ('Monday',    3, 2),
            ('Tuesday',   1, 3),
            ('Tuesday',   2, 0),
            ('Tuesday',   3, 1),
            ('Wednesday', 1, 2),
            ('Wednesday', 2, 3),
            ('Wednesday', 3, 4), # lab
            ('Thursday',  1, 0),
            ('Thursday',  2, 1),
            ('Thursday',  3, 3),
            ('Friday',    1, 2),
            ('Friday',    2, 0),
            ('Friday',    3, 4), # lab
        ]
        
        for bcode, s_list in subject_objs.items():
            sec_a = sections[(bcode, 2, 'A')]
            for day, period, idx in timetable_slots:
                subj = s_list[idx]
                fac = subj.faculty
                Timetable.objects.get_or_create(
                    section=sec_a, day=day, period=period,
                    defaults={'subject': subj, 'faculty': fac}
                )
        self.stdout.write(self.style.SUCCESS("[OK] Timetables loaded for Year 2 Section A of all branches"))

        # 10. STUDENTS (Seeded across all branches/years)
        cse_student_data = [
            ('24BQ1A4901', 'Arjun',   'Sharma',    sections[('CSE', 2, 'A')], '9111111101'),
            ('24BQ1A4902', 'Bhavana', 'Reddy',     sections[('CSE', 2, 'A')], '9111111102'),
            ('24BQ1A4903', 'Charan',  'Kumar',     sections[('CSE', 2, 'A')], '9111111103'),
            ('24BQ1A4904', 'Divya',   'Patel',     sections[('CSE', 2, 'A')], '9111111104'),
            ('24BQ1A4905', 'Eswar',   'Naidu',     sections[('CSE', 2, 'B')], '9111111105'),
            ('24BQ1A4906', 'Fathima', 'Sheikh',    sections[('CSE', 2, 'B')], '9111111106'),
            ('24BQ1A4942', 'Ganesh',  'Vasireddy', sections[('CSE', 2, 'A')], '9111111142'),
        ]

        names_bank = [
            ('Kalyan', 'Bhupathi'), ('Deepika', 'Verma'), ('Nikhil', 'Gutta'), ('Sravani', 'Yadav'),
            ('Aditya', 'Rao'), ('Anjali', 'Koneru'), ('Tarun', 'Somisetty'), ('Meghana', 'Deshmukh'),
            ('Sai', 'Chowdary'), ('Hari', 'Naidu'), ('Teja', 'Verma'), ('Prasad', 'Gupta'),
            ('Rakesh', 'Singh'), ('Sandeep', 'Mishra'), ('Neha', 'Reddy'), ('Pooja', 'Joshi'),
            ('Sneha', 'Gupta'), ('Rahul', 'Kumar'), ('Vikram', 'Babu'), ('Srinivas', 'Reddy')
        ]
        
        random.seed(42)
        all_student_records = []
        
        # Load CSE students
        for roll, fname, lname, sec, phone in cse_student_data:
            all_student_records.append((roll, fname, lname, sec, phone))
            
        # Add years 1, 3, 4 for CSE
        all_student_records.append(('25BQ1A4901', 'Sai', 'Somisetty', sections[('CSE', 1, 'A')], '9111111151'))
        all_student_records.append(('23BQ1A4901', 'Rohan', 'Rao', sections[('CSE', 3, 'A')], '9111111152'))
        all_student_records.append(('22BQ1A4901', 'Anjali', 'Koneru', sections[('CSE', 4, 'A')], '9111111153'))
        
        # Load other branches students
        other_branch_codes = [b for b in branch_objs.keys() if b != 'CSE']
        for bcode in other_branch_codes:
            digit = branch_digits[bcode]
            # Year 1 Sec A
            all_student_records.append((f'25BQ1A{digit}01', 'Sai', f'{bcode}Student', sections[(bcode, 1, 'A')], f'9111112{digit}1'))
            # Year 2 Sec A (4 students)
            for i in range(1, 5):
                name_idx = (int(digit) + i) % len(names_bank)
                fname, lname = names_bank[name_idx]
                all_student_records.append((f'24BQ1A{digit}0{i}', fname, f'{lname}', sections[(bcode, 2, 'A')], f'9111113{digit}{i}'))
            # Year 2 Sec B (1 student)
            all_student_records.append((f'24BQ1A{digit}05', 'Eswar', f'{bcode}StudentB', sections[(bcode, 2, 'B')], f'9111114{digit}5'))
            # Year 3 Sec A (1 student)
            all_student_records.append((f'23BQ1A{digit}01', 'Tarun', f'{bcode}Senior', sections[(bcode, 3, 'A')], f'9111115{digit}1'))
            # Year 4 Sec A (1 student)
            all_student_records.append((f'22BQ1A{digit}01', 'Meghana', f'{bcode}Grad', sections[(bcode, 4, 'A')], f'9111116{digit}1'))

        students = []
        for roll, fname, lname, section, phone in all_student_records:
            b_obj = section.branch
            bcode = b_obj.code
            facs = faculty_objs[bcode]
            f_class_teacher = facs[0]
            f_counsellor = facs[1] if len(facs) > 1 else facs[0]
            
            p_name = f"{random.choice(['Venkata', 'Srinivasa', 'Satya', 'Rama', 'Koteswara', 'Subba', 'Nageswara', 'Prasad'])} {lname}"
            p_mobile = f"9{random.randint(100000000, 999999999)}"
            
            u = User.objects.filter(username=roll).first()
            if u:
                u.set_password('vvit@1234')
                u.save()
                stu = Student.objects.filter(roll_number=roll).first()
                if stu:
                    stu.branch = b_obj
                    stu.year = section.year
                    stu.section = section
                    stu.class_teacher = f_class_teacher
                    stu.counsellor = f_counsellor
                    stu.parent_name = p_name
                    stu.parent_mobile = p_mobile
                    stu.save()
                else:
                    stu = Student.objects.create(
                        user=u, roll_number=roll,
                        branch=b_obj, year=section.year,
                        section=section,
                        class_teacher=f_class_teacher,
                        counsellor=f_counsellor,
                        admission_year=2025 if section.year.year == 1 else (2024 if section.year.year == 2 else (2023 if section.year.year == 3 else 2022)),
                        parent_name=p_name,
                        parent_mobile=p_mobile,
                    )
            else:
                u = User.objects.create_user(
                    username=roll, password='vvit@1234',
                    first_name=fname, last_name=lname,
                    email=roll + '@vvit.net', role='student', phone=phone,
                )
                stu = Student.objects.create(
                    user=u, roll_number=roll,
                    branch=b_obj, year=section.year,
                    section=section,
                    class_teacher=f_class_teacher,
                    counsellor=f_counsellor,
                    admission_year=2025 if section.year.year == 1 else (2024 if section.year.year == 2 else (2023 if section.year.year == 3 else 2022)),
                    parent_name=p_name,
                    parent_mobile=p_mobile,
                )
            students.append(stu)
        self.stdout.write(self.style.SUCCESS(f"[OK] {len(students)} Student profiles loaded across all branches/years"))

        # 11. ATTENDANCE (last 45 days for Year 2 Sec A)
        today     = timezone.localdate()
        days_back = 45
        att_count = 0
        
        for bcode in branch_objs.keys():
            sec_a = sections[(bcode, 2, 'A')]
            b_students = [s for s in students if s.section == sec_a]
            b_tt_slots = list(Timetable.objects.filter(section=sec_a))
            if not b_students or not b_tt_slots:
                continue
                
            for day_offset in range(days_back, 0, -1):
                att_date = today - datetime.timedelta(days=day_offset)
                day_name = att_date.strftime('%A')
                day_slots = [t for t in b_tt_slots if t.day == day_name]
                if not day_slots:
                    continue
                for slot in day_slots:
                    for i, stu in enumerate(b_students):
                        threshold = 55 if i == 2 else (65 if i == 3 else 82)
                        status = 'P' if random.randint(1, 100) <= threshold else 'A'
                        Attendance.objects.get_or_create(
                            student=stu,
                            timetable_entry=slot,
                            date=att_date,
                            defaults={'status': status, 'marked_by': slot.faculty}
                        )
                        att_count += 1
        self.stdout.write(self.style.SUCCESS(f"[OK] {att_count} Attendance records generated"))

        # 12. EXAMS AND RESULTS (Mid1, Mid2, Semester Final for Year 2)
        exams_created = 0
        results_created = 0
        
        for bcode, b_obj in branch_objs.items():
            sec_a = sections[(bcode, 2, 'A')]
            b_students = [s for s in students if s.section == sec_a]
            b_subjs = subject_objs[bcode]
            if not b_students or not b_subjs:
                continue
                
            mid1_qs = Exam.objects.filter(
                name=f'{bcode} Mid Term 1', exam_type='mid1', semester=3,
                year=y2, branch=b_obj
            )
            if mid1_qs.exists():
                mid1 = mid1_qs.first()
                mid1_qs.exclude(id=mid1.id).delete()
            else:
                mid1 = Exam.objects.create(
                    name=f'{bcode} Mid Term 1', exam_type='mid1', semester=3,
                    year=y2, branch=b_obj,
                    date=today - datetime.timedelta(days=30)
                )

            mid2_qs = Exam.objects.filter(
                name=f'{bcode} Mid Term 2', exam_type='mid2', semester=3,
                year=y2, branch=b_obj
            )
            if mid2_qs.exists():
                mid2 = mid2_qs.first()
                mid2_qs.exclude(id=mid2.id).delete()
            else:
                mid2 = Exam.objects.create(
                    name=f'{bcode} Mid Term 2', exam_type='mid2', semester=3,
                    year=y2, branch=b_obj,
                    date=today - datetime.timedelta(days=5)
                )

            final_qs = Exam.objects.filter(
                name=f'{bcode} Semester Final', exam_type='final', semester=3,
                year=y2, branch=b_obj
            )
            if final_qs.exists():
                final_exam = final_qs.first()
                final_qs.exclude(id=final_exam.id).delete()
            else:
                final_exam = Exam.objects.create(
                    name=f'{bcode} Semester Final', exam_type='final', semester=3,
                    year=y2, branch=b_obj,
                    date=today - datetime.timedelta(days=2)
                )
            exams_created += 3
            
            for stu in b_students:
                for subj in b_subjs:
                    m1_marks = random.randint(15, 30)
                    Result.objects.get_or_create(
                        student=stu, exam=mid1, subject=subj,
                        defaults={'marks_obtained': m1_marks, 'max_marks': 30}
                    )
                    
                    m2_marks = random.randint(15, 30)
                    Result.objects.get_or_create(
                        student=stu, exam=mid2, subject=subj,
                        defaults={'marks_obtained': m2_marks, 'max_marks': 30}
                    )
                    
                    final_marks = random.randint(45, 95)
                    Result.objects.get_or_create(
                        student=stu, exam=final_exam, subject=subj,
                        defaults={'marks_obtained': final_marks, 'max_marks': 100}
                    )
                    results_created += 3
            
            # Setup ResultRelease
            is_released = bcode in ['CSE', 'CSM', 'CSD', 'IT']
            release_obj, _ = ResultRelease.objects.get_or_create(
                exam=final_exam,
                defaults={
                    'released': is_released,
                    'released_at': timezone.now() if is_released else None,
                    'released_by': admin_user
                }
            )
            if release_obj.released != is_released:
                release_obj.released = is_released
                release_obj.released_at = timezone.now() if is_released else None
                release_obj.released_by = admin_user
                release_obj.save()
        self.stdout.write(self.style.SUCCESS(f"[OK] {exams_created} Exams and {results_created} Results loaded"))

        # 13. ACADEMIC CALENDAR
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
        self.stdout.write(self.style.SUCCESS(f"[OK] {len(events)} academic calendar events created"))

        self.stdout.write(self.style.MIGRATE_HEADING(""))
        self.stdout.write(self.style.MIGRATE_HEADING("=" * 60))
        self.stdout.write(self.style.SUCCESS("  Sample data loaded successfully!"))
        self.stdout.write(self.style.MIGRATE_HEADING("=" * 60))
        self.stdout.write(self.style.MIGRATE_HEADING(""))
        self.stdout.write(self.style.MIGRATE_HEADING("Login credentials mapping (all passwords: vvit@1234):"))
        self.stdout.write(self.style.MIGRATE_HEADING("  Admin   : admin"))
        self.stdout.write(self.style.MIGRATE_HEADING("  HODs    : HOD001 (CSE) to HOD008 (MECH)"))
        self.stdout.write(self.style.MIGRATE_HEADING("  DEOs    : DEO001 (CSE) to DEO008 (MECH)"))
        self.stdout.write(self.style.MIGRATE_HEADING("  Faculty : EMP001 (CSE) to EMP016 (MECH)"))
        self.stdout.write(self.style.MIGRATE_HEADING("  Students: 24BQ1A4901 (CSE), 24BQ1A0401 (ECE), etc."))
        self.stdout.write(self.style.MIGRATE_HEADING("=" * 60))
