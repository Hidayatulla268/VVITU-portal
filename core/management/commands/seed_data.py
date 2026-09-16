"""
VVIT Portal — Management Command: seed_data

Seeds comprehensive initial academic records:
- All 8 branches (CSE, ECE, EEE, IT, CSM, CSD, CIVIL, MECH).
- 5+ rich distinct subjects per branch with credits, labs, and faculty assignments.
- Min 10+ students per section across all 4 years and sections (A & B).
- Full 6-day weekly timetables (Periods 1-6) for all sections.
- 3 full months of realistic daily attendance (June 1 to August 31, 2026).
- Daily Class Diary lecture logs across the 3 months.
- Milestone Exam Schedules (Mid-1 2.5 units, Mid-2 5.0 units).
- Topic-by-topic Syllabus Plans (SubjectTopicPlan) showing covered (Units 1-2.5) vs. pending (Units 3-5).
- Exams, Results, and Result Releases.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from django.contrib.auth.hashers import make_password
from accounts.models import User, Student, Faculty, DEOProfile, StudentFee
from core.models import (
    Branch, Year, Section, Subject, Timetable,
    Attendance, Exam, Result, AcademicCalendar, ResultRelease,
    ClassDiary, ExamSchedule, SubjectTopicPlan
)
import datetime
import random


class Command(BaseCommand):
    help = 'Seeds comprehensive sample academic data for all branches, students, timetables, attendance, diaries, and syllabus topics.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset-passwords',
            action='store_true',
            default=False,
            help='Reset passwords of existing users to default (vvit@1234)',
        )

    def handle(self, *args, **options):
        reset_passwords = options.get('reset_passwords', False)
        random.seed(2026)

        self.stdout.write(self.style.MIGRATE_HEADING("=" * 70))
        self.stdout.write(self.style.MIGRATE_HEADING("  VVIT Portal - Loading Comprehensive Academic & Syllabus Data"))
        self.stdout.write(self.style.MIGRATE_HEADING("=" * 70))

        # 1. ADMIN USER
        admin_user = User.objects.filter(username='admin').first()
        if not admin_user:
            admin_user = User.objects.create_superuser(
                username='admin', password='vvit@1234',
                email='admin@vvit.net',
                first_name='Portal', last_name='Admin',
                role='admin',
            )
        elif reset_passwords:
            admin_user.set_password('vvit@1234')
            admin_user.save()
        self.stdout.write(self.style.SUCCESS("[OK] Admin user verified"))

        # 2. BRANCHES
        branches_data = [
            {'code': 'CSE',   'name': 'Computer Science and Engineering', 'digit': '49'},
            {'code': 'ECE',   'name': 'Electronics and Communication Engineering', 'digit': '04'},
            {'code': 'EEE',   'name': 'Electrical and Electronics Engineering', 'digit': '02'},
            {'code': 'IT',    'name': 'Information Technology', 'digit': '12'},
            {'code': 'CSM',   'name': 'CSE (Artificial Intelligence and Machine Learning)', 'digit': '42'},
            {'code': 'CSD',   'name': 'CSE (Data Science)', 'digit': '44'},
            {'code': 'CIVIL', 'name': 'Civil Engineering', 'digit': '01'},
            {'code': 'MECH',  'name': 'Mechanical Engineering', 'digit': '03'},
        ]
        
        branch_objs = {}
        branch_digits = {}
        for b in branches_data:
            obj, _ = Branch.objects.get_or_create(code=b['code'], defaults={'name': b['name']})
            branch_objs[b['code']] = obj
            branch_digits[b['code']] = b['digit']
        self.stdout.write(self.style.SUCCESS(f"[OK] {len(branch_objs)} branches loaded"))

        # 3. YEARS & SECTIONS
        years = {y: Year.objects.get_or_create(year=y)[0] for y in [1, 2, 3, 4]}
        sections = {}
        for code, b_obj in branch_objs.items():
            for y_num in [1, 2, 3, 4]:
                for sec_name in ['A', 'B']:
                    sec_obj, _ = Section.objects.get_or_create(
                        name=sec_name, branch=b_obj, year=years[y_num]
                    )
                    sections[(code, y_num, sec_name)] = sec_obj
        self.stdout.write(self.style.SUCCESS(f"[OK] {len(sections)} sections loaded across all branches"))

        # Helper: Create/update Faculty profile
        def make_faculty(emp_id, fname, lname, dept, desig='Associate Professor', role='faculty', phone='9000000001'):
            u = User.objects.filter(username=emp_id).first()
            if u:
                if reset_passwords:
                    u.set_password('vvit@1234')
                u.role = role
                u.phone = phone
                u.first_name = fname
                u.last_name = lname
                u.save()
                fac = Faculty.objects.filter(employee_id=emp_id).first()
                if not fac:
                    fac = Faculty.objects.create(user=u, employee_id=emp_id, department=dept, designation=desig)
                else:
                    fac.department = dept
                    fac.designation = desig
                    fac.save()
                return fac
            u = User.objects.create_user(
                username=emp_id, password='vvit@1234',
                first_name=fname, last_name=lname,
                email=emp_id.lower() + '@vvit.net', role=role, phone=phone,
            )
            return Faculty.objects.create(
                user=u, employee_id=emp_id, department=dept,
                designation=desig
            )

        # 4. HODs & DEOs
        hod_map = [
            ('HOD001', 'Prof. K. Suresh', 'Reddy', 'CSE'),
            ('HOD002', 'Dr. T. Sridevi', 'Varma', 'ECE'),
            ('HOD003', 'Dr. P. Kiran', 'Kumar', 'EEE'),
            ('HOD004', 'Dr. M. Suresh', 'Babu', 'IT'),
            ('HOD005', 'Dr. B. Ravi', 'Teja', 'CSM'),
            ('HOD006', 'Dr. V. Satish', 'Chandra', 'CSD'),
            ('HOD007', 'Dr. G. Siva', 'Rama Krishna', 'CIVIL'),
            ('HOD008', 'Dr. Ch. Ramesh', 'Babu', 'MECH'),
        ]
        for idx, (username, fname, lname, bcode) in enumerate(hod_map):
            b_obj = branch_objs[bcode]
            make_faculty(username, fname, lname, b_obj, desig='Professor & HOD', role='hod', phone=f'987654320{idx+1}')

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
            elif reset_passwords:
                deo_user.set_password('vvit@1234')
                deo_user.save()
            deo_p, _ = DEOProfile.objects.get_or_create(user=deo_user, defaults={'employee_id': username, 'branch': b_obj})
            if deo_p.branch != b_obj:
                deo_p.branch = b_obj
                deo_p.save()

        # 5. FACULTY ROSTER (6+ per branch)
        faculty_roster = {
            'CSE': [
                ('EMP015', 'Dr. Ramesh', 'Kumar', 'Associate Professor'),
                ('EMP016', 'Dr. Lakshmi', 'Priya', 'Associate Professor'),
                ('EMP018', 'Dr. Ananya', 'Sharma', 'Assistant Professor'),
                ('EMP019', 'Prof. Venkatesh', 'Rao', 'Assistant Professor'),
                ('EMP021', 'Prof. Rajesh', 'Verma', 'Assistant Professor'),
                ('EMP024', 'Prof. Sandhya', 'Devi', 'Assistant Professor'),
            ],
            'ECE': [
                ('EMP039', 'Dr. Harish', 'Babu', 'Associate Professor'),
                ('EMP040', 'Prof. Geetha', 'Madhuri', 'Associate Professor'),
                ('EMP041', 'Dr. Naveen', 'Prasad', 'Assistant Professor'),
                ('EMP042', 'Prof. Sunitha', 'Nair', 'Assistant Professor'),
                ('EMP048', 'Prof. Padmavathi', 'Devi', 'Assistant Professor'),
            ],
            'EEE': [
                ('EMP049', 'Dr. Anand', 'Shekhar', 'Associate Professor'),
                ('EMP050', 'Prof. Sangeetha', 'Rao', 'Associate Professor'),
                ('EMP053', 'Dr. Vijay', 'Bhaskar', 'Assistant Professor'),
                ('EMP054', 'Prof. Pushpa', 'Latha', 'Assistant Professor'),
                ('EMP055', 'Dr. Murali', 'Mohan', 'Assistant Professor'),
            ],
            'IT': [
                ('EMP056', 'Dr. Phani', 'Kumar', 'Associate Professor'),
                ('EMP057', 'Prof. Swathi', 'Krishna', 'Associate Professor'),
                ('EMP058', 'Prof. Raghu', 'Vamsi', 'Assistant Professor'),
                ('EMP061', 'Prof. Harika', 'Reddy', 'Assistant Professor'),
                ('EMP062', 'Dr. Santosh', 'Hegde', 'Assistant Professor'),
            ],
            'CSM': [
                ('EMP031', 'Dr. Aditya', 'Prasad', 'Associate Professor'),
                ('EMP032', 'Prof. Shreya', 'Ghosh', 'Associate Professor'),
                ('EMP034', 'Dr. Manas', 'Ranjan', 'Assistant Professor'),
                ('EMP035', 'Prof. Deepa', 'Sundaram', 'Assistant Professor'),
                ('EMP037', 'Dr. Tanmoy', 'Das', 'Assistant Professor'),
            ],
            'CSD': [
                ('EMP007', 'Dr. Arvind', 'Swaroop', 'Associate Professor'),
                ('EMP009', 'Dr. Kiran', 'Babu', 'Associate Professor'),
                ('EMP010', 'Prof. Supriya', 'Kulkarni', 'Assistant Professor'),
                ('EMP011', 'Dr. Mahesh', 'Chandra', 'Assistant Professor'),
                ('EMP012', 'Prof. Vani', 'Sree', 'Assistant Professor'),
            ],
            'CIVIL': [
                ('EMP001', 'Dr. Rajesh', 'Babu', 'Associate Professor'),
                ('EMP002', 'Prof. Kavitha', 'Devi', 'Associate Professor'),
                ('EMP003', 'Dr. Karthik', 'Rajan', 'Assistant Professor'),
                ('EMP004', 'Prof. Nithya', 'Menon', 'Assistant Professor'),
                ('EMP006', 'Prof. Yamini', 'Priya', 'Assistant Professor'),
            ],
            'MECH': [
                ('EMP064', 'Prof. Suhasini', 'Rao', 'Associate Professor'),
                ('EMP065', 'Dr. Praveen', 'Kumar', 'Associate Professor'),
                ('EMP066', 'Prof. Mohan', 'Krishna', 'Assistant Professor'),
                ('EMP067', 'Dr. Jagadeesh', 'Reddy', 'Assistant Professor'),
                ('EMP068', 'Prof. Bhanu', 'Prasad', 'Assistant Professor'),
            ],
        }
        branch_faculty = {}
        for bcode, fac_list in faculty_roster.items():
            b_obj = branch_objs[bcode]
            branch_faculty[bcode] = list(Faculty.objects.filter(department=b_obj))
            for emp_id, fname, lname, desig in fac_list:
                f_obj = make_faculty(emp_id, fname, lname, b_obj, desig=desig, phone=f'98765{random.randint(10000, 99999)}')
                if f_obj not in branch_faculty[bcode]:
                    branch_faculty[bcode].append(f_obj)
        self.stdout.write(self.style.SUCCESS("[OK] Faculty roster verified across all branches"))

        # 6. SUBJECTS CURRICULUM (5+ distinct subjects per branch)
        subjects_master = {
            'CSE': [
                ('CSE201', 'Database Management Systems', 2, 3, 3, False),
                ('CSE202', 'Object Oriented Programming Java', 2, 3, 3, False),
                ('CSE203', 'Operating Systems', 2, 4, 3, False),
                ('CSE204', 'Computer Organization & Architecture', 2, 4, 3, False),
                ('CSE201L', 'DBMS and Java Lab', 2, 3, 2, True),
                ('CSE301', 'Design & Analysis of Algorithms', 3, 5, 3, False),
                ('CSE302', 'Computer Networks', 3, 5, 3, False),
                ('CSE401', 'Machine Learning & Neural Nets', 4, 7, 3, False),
            ],
            'ECE': [
                ('ECE201', 'Electronic Devices & Circuits', 2, 3, 3, False),
                ('ECE202', 'Signals & Systems Analysis', 2, 3, 3, False),
                ('ECE203', 'Digital System Design & Verilog', 2, 4, 3, False),
                ('ECE204', 'Analog Communications Systems', 2, 4, 3, False),
                ('ECE201L', 'EDC & Simulation Lab', 2, 3, 2, True),
                ('ECE301', 'Digital Signal Processing', 3, 5, 3, False),
                ('ECE302', 'VLSI Design & Architecture', 3, 6, 3, False),
                ('ECE401', 'Embedded Systems & IoT', 4, 7, 3, False),
            ],
            'EEE': [
                ('EEE201', 'Electrical Circuit Analysis', 2, 3, 3, False),
                ('EEE202', 'DC Machines and Transformers', 2, 3, 3, False),
                ('EEE203', 'Electromagnetic Field Theory', 2, 4, 3, False),
                ('EEE204', 'Power Systems Engineering - I', 2, 4, 3, False),
                ('EEE201L', 'Electrical Machines Lab', 2, 3, 2, True),
                ('EEE301', 'Control Systems & Automation', 3, 5, 3, False),
                ('EEE302', 'Power Electronics & Drives', 3, 6, 3, False),
                ('EEE401', 'Renewable Energy Systems', 4, 7, 3, False),
            ],
            'IT': [
                ('IT201', 'Full Stack Web Development', 2, 3, 3, False),
                ('IT202', 'Data Structures & Algorithms in Java', 2, 3, 3, False),
                ('IT203', 'Object Oriented Software Engineering', 2, 4, 3, False),
                ('IT204', 'Data Communication & Computer Networks', 2, 4, 3, False),
                ('IT201L', 'Web Technologies & Frameworks Lab', 2, 3, 2, True),
                ('IT301', 'Information & Network Security', 3, 5, 3, False),
                ('IT302', 'Cloud Computing & Virtualization', 3, 6, 3, False),
                ('IT401', 'DevOps & Microservices Architecture', 4, 7, 3, False),
            ],
            'CSM': [
                ('CSM201', 'Artificial Intelligence Principles', 2, 3, 3, False),
                ('CSM202', 'Python for Machine Learning', 2, 3, 3, False),
                ('CSM203', 'Deep Learning & Neural Architectures', 2, 4, 3, False),
                ('CSM204', 'Optimization Techniques for AI', 2, 4, 3, False),
                ('CSM201L', 'AI & Deep Learning Tools Lab', 2, 3, 2, True),
                ('CSM301', 'Natural Language Processing & LLMs', 3, 5, 3, False),
                ('CSM302', 'Computer Vision & Image Processing', 3, 6, 3, False),
                ('CSM401', 'Reinforcement Learning & Robotics', 4, 7, 3, False),
            ],
            'CSD': [
                ('CSD201', 'Data Wrangling with Python & Pandas', 2, 3, 3, False),
                ('CSD202', 'Big Data Analytics & Hadoop', 2, 3, 3, False),
                ('CSD203', 'Data Warehousing & Business Intelligence', 2, 4, 3, False),
                ('CSD204', 'Statistical Inference & Applied R', 2, 4, 3, False),
                ('CSD201L', 'Data Science & Visual Analytics Lab', 2, 3, 2, True),
                ('CSD301', 'Data Visualization & Tableau / PowerBI', 3, 5, 3, False),
                ('CSD302', 'Feature Engineering & Mining', 3, 6, 3, False),
                ('CSD401', 'Predictive Modeling & Time Series', 4, 7, 3, False),
            ],
            'CIVIL': [
                ('CIV201', 'Strength of Materials & Mechanics', 2, 3, 3, False),
                ('CIV202', 'Fluid Mechanics & Hydraulic Machinery', 2, 3, 3, False),
                ('CIV203', 'Concrete Technology & Building Materials', 2, 4, 3, False),
                ('CIV204', 'Building Planning, Drawing & CAD', 2, 4, 3, False),
                ('CIV201L', 'Strength of Materials & Geotechnical Lab', 2, 3, 2, True),
                ('CIV301', 'Structural Analysis & Design of RC Structures', 3, 5, 3, False),
                ('CIV302', 'Transportation & Highway Engineering', 3, 6, 3, False),
                ('CIV401', 'Environmental Engineering & Waste Management', 4, 7, 3, False),
            ],
            'MECH': [
                ('MEC201', 'Applied Engineering Thermodynamics', 2, 3, 3, False),
                ('MEC202', 'Metallurgy & Material Science', 2, 3, 3, False),
                ('MEC203', 'Mechanics of Solids & Machine Design', 2, 4, 3, False),
                ('MEC204', 'Kinematics & Dynamics of Machinery', 2, 4, 3, False),
                ('MEC201L', 'Thermal Engineering & Metallurgy Lab', 2, 3, 2, True),
                ('MEC301', 'Fluid Mechanics & Turbo Machinery', 3, 5, 3, False),
                ('MEC302', 'Manufacturing Technology & CNC', 3, 6, 3, False),
                ('MEC401', 'CAD / CAM & Industrial Automation', 4, 7, 3, False),
            ],
        }
        branch_subjects = {}
        for bcode, subjs in subjects_master.items():
            b_obj = branch_objs[bcode]
            fac_list = branch_faculty[bcode]
            branch_subjects[bcode] = []
            for idx, (scode, sname, y_num, sem, cred, is_lab) in enumerate(subjs):
                fac = fac_list[idx % len(fac_list)]
                s_obj, created = Subject.objects.get_or_create(
                    code=scode,
                    defaults={
                        'name': sname, 'branch': b_obj, 'year': years[y_num],
                        'semester': sem, 'credits': cred, 'is_lab': is_lab, 'faculty': fac,
                    }
                )
                if not created:
                    s_obj.name = sname
                    s_obj.branch = b_obj
                    s_obj.year = years[y_num]
                    s_obj.semester = sem
                    s_obj.credits = cred
                    s_obj.is_lab = is_lab
                    s_obj.faculty = fac
                    s_obj.is_deleted = False
                    s_obj.save()
                branch_subjects[bcode].append(s_obj)
        self.stdout.write(self.style.SUCCESS("[OK] 5+ Subjects configured per branch"))

        # 7. STUDENTS (Min 10 per section)
        first_names_pool = ['Aarav', 'Aditya', 'Akhil', 'Anand', 'Aniket', 'Arjun', 'Bhavana', 'Charan', 'Deepika', 'Divya', 'Eswar', 'Ganesh', 'Kalyan', 'Kavya', 'Kiran', 'Meghana', 'Naveen', 'Nikhil', 'Pooja', 'Rahul', 'Rajesh', 'Sai', 'Sravani', 'Tarun', 'Vikram']
        last_names_pool = ['Adusumilli', 'Bandaru', 'Chowdary', 'Garlapati', 'Kakarla', 'Koneru', 'Nalluri', 'Paruchuri', 'Rayapati', 'Surapaneni', 'Vasireddy', 'Yarlagadda']
        adm_years = {1: 2025, 2: 2024, 3: 2023, 4: 2022}
        adm_prefixes = {1: '25', 2: '24', 3: '23', 4: '22'}
        default_hashed_pwd = make_password('vvit@1234')

        with transaction.atomic():
            for bcode, b_obj in branch_objs.items():
                digit = branch_digits[bcode]
                fac_list = branch_faculty[bcode]

                for y_num in [1, 2, 3, 4]:
                    prefix = adm_prefixes[y_num]
                    adm_yr = adm_years[y_num]

                    for sec_name in ['A', 'B']:
                        sec_obj = sections[(bcode, y_num, sec_name)]
                        existing_students = list(Student.objects.filter(section=sec_obj))
                        target_min = 10
                        needed = target_min - len(existing_students)

                        if needed > 0:
                            sec_offset = 0 if sec_name == 'A' else 50
                            for i in range(1, target_min + 1):
                                roll_seq = sec_offset + i
                                roll_num = f"{prefix}BQ1A{digit}{roll_seq:02d}"
                                if Student.objects.filter(roll_number=roll_num).exists():
                                    continue
                                fn = random.choice(first_names_pool)
                                ln = random.choice(last_names_pool)
                                ct = fac_list[i % len(fac_list)]
                                coun = fac_list[(i + 1) % len(fac_list)]

                                u = User.objects.filter(username=roll_num).first()
                                if not u:
                                    u = User.objects.create(
                                        username=roll_num, password=default_hashed_pwd,
                                        first_name=fn, last_name=ln,
                                        email=f"{roll_num.lower()}@vvit.net", role='student',
                                        phone=f"9{random.randint(100000000, 999999999)}"
                                    )
                                stu = Student.objects.create(
                                    user=u, roll_number=roll_num,
                                    branch=b_obj, year=years[y_num], section=sec_obj,
                                    class_teacher=ct, counsellor=coun, admission_year=adm_yr,
                                    is_active=True, academic_status='REGULAR',
                                    parent_name=f"Srinivasa {ln}", parent_mobile=f"9{random.randint(100000000, 999999999)}"
                                )
                                paid_amt = random.choice([78000.00, 60000.00, 50000.00])
                                StudentFee.objects.get_or_create(
                                    student=stu, academic_year=years[y_num],
                                    defaults={
                                        'college_fee': 70000.00, 'nba_fee': 3000.00, 'exam_fee': 2500.00,
                                        'book_bank_fee': 1500.00, 'other_fee': 1000.00,
                                        'total_fee_amount': 78000.00, 'amount_paid': paid_amt,
                                        'due_amount': max(0.0, 78000.00 - paid_amt),
                                        'status': 'paid' if paid_amt >= 78000.00 else 'partial'
                                    }
                                )
        self.stdout.write(self.style.SUCCESS(f"[OK] Min 10 students loaded per section (Total: {Student.objects.count()})"))

        # 8. TIMETABLES (Mon-Sat, 6 periods)
        days_of_week = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
        period_times = {
            1: (datetime.time(9, 0), datetime.time(9, 50)),
            2: (datetime.time(9, 50), datetime.time(10, 40)),
            3: (datetime.time(10, 50), datetime.time(11, 40)),
            4: (datetime.time(11, 40), datetime.time(12, 30)),
            5: (datetime.time(13, 20), datetime.time(14, 10)),
            6: (datetime.time(14, 10), datetime.time(15, 0)),
        }
        for bcode, b_obj in branch_objs.items():
            b_subjs = branch_subjects[bcode]
            fac_list = branch_faculty[bcode]
            for y_num in [1, 2, 3, 4]:
                y_subjs = [s for s in b_subjs if s.year.year == y_num]
                if len(y_subjs) < 5:
                    other_subjs = [s for s in b_subjs if s not in y_subjs]
                    y_subjs = (y_subjs + other_subjs)[:6]
                theory_subjs = [s for s in y_subjs if not s.is_lab]
                lab_subjs = [s for s in y_subjs if s.is_lab] or [theory_subjs[-1]]

                for sec_name in ['A', 'B']:
                    sec_obj = sections[(bcode, y_num, sec_name)]
                    for day_idx, day_name in enumerate(days_of_week):
                        for p in range(1, 7):
                            if day_name in ['Wednesday', 'Friday'] and p in [5, 6]:
                                subj = lab_subjs[0]
                                rm = f"{bcode} Advanced Systems Lab"
                            else:
                                s_idx = (day_idx * 6 + p) % len(theory_subjs)
                                subj = theory_subjs[s_idx]
                                rm = f"Block {bcode[:2]} - Room {y_num}0{1 if sec_name == 'A' else 2}"
                            fac = subj.faculty or fac_list[p % len(fac_list)]
                            st, et = period_times[p]
                            Timetable.objects.update_or_create(
                                section=sec_obj, day=day_name, period=p,
                                defaults={'subject': subj, 'faculty': fac, 'room_number': rm, 'start_time': st, 'end_time': et}
                            )
        self.stdout.write(self.style.SUCCESS(f"[OK] Timetables loaded for all sections (Total: {Timetable.objects.count()})"))

        # 9. EXAM SCHEDULES & SYLLABUS TOPIC PLANS
        for bcode, b_obj in branch_objs.items():
            for y_num in [1, 2, 3, 4]:
                sem = y_num * 2 - 1
                ExamSchedule.objects.update_or_create(
                    branch=b_obj, year=years[y_num], semester=sem, exam_type='mid1',
                    defaults={'title': f'{bcode} Y{y_num} Sem{sem} Mid-1', 'start_date': datetime.date(2026, 9, 14), 'end_date': datetime.date(2026, 9, 19), 'target_units': 2.5, 'target_completion_date': datetime.date(2026, 8, 30), 'is_active': True, 'created_by': admin_user}
                )
                ExamSchedule.objects.update_or_create(
                    branch=b_obj, year=years[y_num], semester=sem, exam_type='mid2',
                    defaults={'title': f'{bcode} Y{y_num} Sem{sem} Mid-2', 'start_date': datetime.date(2026, 11, 16), 'end_date': datetime.date(2026, 11, 21), 'target_units': 5.0, 'target_completion_date': datetime.date(2026, 10, 30), 'is_active': True, 'created_by': admin_user}
                )

        SubjectTopicPlan.objects.all().delete()
        default_pattern = [
            (1, "Fundamental Principles & Theoretical Concepts", "2026-06-15", "mid1", True, "2026-06-15"),
            (1, "Mathematical Modeling & Analysis of Basic Subsystems", "2026-06-28", "mid1", True, "2026-06-28"),
            (1, "Elementary Component Evaluation & Laboratory Setup", "2026-07-12", "mid1", True, "2026-07-12"),
            (2, "Core Design Methods & Algorithmic Transformations", "2026-07-25", "mid1", True, "2026-07-25"),
            (2, "System Implementations & Performance Optimization", "2026-08-08", "mid1", True, "2026-08-08"),
            (2, "Verification & Protocol Testing Methodologies", "2026-08-22", "mid1", True, "2026-08-22"),
            (3, "Mid-Term Milestone Integration & Unit 3 Fundamentals", "2026-08-30", "mid1", True, "2026-08-30"),
            (3, "Complex Subsystem Design & Dynamic Optimization", "2026-09-22", "mid2", False, None),
            (4, "Specialized Industrial Architectures & Case Studies", "2026-10-10", "mid2", False, None),
            (4, "Modern Frameworks & High-Load Handling Protocols", "2026-10-25", "mid2", False, None),
            (5, "Emerging Technologies, Capstone Synthesis & Review", "2026-11-10", "final", False, None),
        ]
        for bcode, subjs in branch_subjects.items():
            for subj in subjs:
                for order_idx, (u_num, t_name, t_date_str, m_stone, is_d, d_date_str) in enumerate(default_pattern, 1):
                    SubjectTopicPlan.objects.create(
                        subject=subj, unit_number=u_num, unit_title=f"Unit {u_num}",
                        topic_name=f"{subj.short_name}: {t_name}",
                        description=f"Concepts for {t_name}",
                        target_date=datetime.datetime.strptime(t_date_str, "%Y-%m-%d").date(),
                        target_milestone=m_stone, order=order_idx, is_completed=is_d,
                        completed_date=datetime.datetime.strptime(d_date_str, "%Y-%m-%d").date() if d_date_str else None,
                        completed_by=subj.faculty if is_d else None,
                    )
        self.stdout.write(self.style.SUCCESS(f"[OK] Topic plans loaded (Units 1-2.5 completed, Units 3-5 pending)"))

        # 10. CLASS DIARY LOGS (Daily lecture discussion logs)
        ClassDiary.objects.all().delete()
        start_date = datetime.date(2026, 6, 1)
        end_date = datetime.date(2026, 8, 31)
        working_dates = [start_date + datetime.timedelta(days=d) for d in range((end_date - start_date).days + 1) if (start_date + datetime.timedelta(days=d)).weekday() < 6]
        all_timetables = list(Timetable.objects.select_related('section', 'subject', 'faculty'))
        tt_by_day = {}
        for tt in all_timetables:
            tt_by_day.setdefault(tt.day, []).append(tt)

        diary_batch = []
        for cur_date in working_dates:
            slots = tt_by_day.get(cur_date.strftime('%A'), [])
            sample_slots = [s for s in slots if (hash(f"{cur_date}_{s.id}") % 5 == 0)]
            u_num = 1 if cur_date < datetime.date(2026, 7, 10) else (2 if cur_date < datetime.date(2026, 8, 15) else 3)
            for slot in sample_slots:
                diary_batch.append(
                    ClassDiary(
                        timetable_entry=slot, section=slot.section, subject=slot.subject, faculty=slot.faculty,
                        date=cur_date, period=slot.period, unit_number=u_num,
                        topic_covered=f"{slot.subject.short_name}: Lecture on Unit {u_num} Key Principles",
                        discussion_summary=f"In-depth discussion on analytical techniques and system applications of {slot.subject.name}.",
                        homework_assignment="Solve textbook chapter exercise problems and review past paper questions."
                    )
                )
        ClassDiary.objects.bulk_create(diary_batch, batch_size=2000)
        self.stdout.write(self.style.SUCCESS(f"[OK] {ClassDiary.objects.count()} ClassDiary entries created"))

        # 11. ATTENDANCE (3 Months)
        Attendance.objects.all().delete()
        students_by_sec = {}
        for s in Student.objects.filter(is_active=True).select_related('section'):
            students_by_sec.setdefault(s.section_id, []).append(s)

        attendance_batch = []
        for cur_date in working_dates:
            day_slots = tt_by_day.get(cur_date.strftime('%A'), [])
            for slot in day_slots:
                sec_students = students_by_sec.get(slot.section_id, [])
                for idx, stu in enumerate(sec_students):
                    prob = 62 if idx % 10 == 0 else (74 if idx % 10 == 1 else 86)
                    status = 'P' if random.randint(1, 100) <= prob else 'A'
                    attendance_batch.append(
                        Attendance(student=stu, timetable_entry=slot, date=cur_date, status=status, marked_by=slot.faculty)
                    )
                if len(attendance_batch) >= 15000:
                    Attendance.objects.bulk_create(attendance_batch, batch_size=5000)
                    attendance_batch = []
        if attendance_batch:
            Attendance.objects.bulk_create(attendance_batch, batch_size=5000)
        self.stdout.write(self.style.SUCCESS(f"[OK] {Attendance.objects.count()} Attendance records created (3 months)"))

        # 12. EXAMS & RESULTS
        Exam.objects.all().delete()
        Result.objects.all().delete()
        for bcode, b_obj in branch_objs.items():
            b_subjs = [s for s in branch_subjects[bcode] if s.year.year == 2]
            sec_a_students = Student.objects.filter(branch=b_obj, year=years[2], section__name='A')
            m1 = Exam.objects.create(name=f"{bcode} Y2 Mid-1", exam_type='mid1', semester=3, year=years[2], branch=b_obj, date=datetime.date(2026, 7, 25))
            m2 = Exam.objects.create(name=f"{bcode} Y2 Mid-2", exam_type='mid2', semester=3, year=years[2], branch=b_obj, date=datetime.date(2026, 8, 28))
            final_ex = Exam.objects.create(name=f"{bcode} Y2 Final", exam_type='final', semester=3, year=years[2], branch=b_obj, date=datetime.date(2026, 8, 31))
            for stu in sec_a_students:
                for subj in b_subjs:
                    Result.objects.create(student=stu, exam=m1, subject=subj, marks_obtained=random.randint(18, 30), max_marks=30)
                    Result.objects.create(student=stu, exam=m2, subject=subj, marks_obtained=random.randint(18, 30), max_marks=30)
                    Result.objects.create(student=stu, exam=final_ex, subject=subj, marks_obtained=random.randint(45, 95), max_marks=100)
            ResultRelease.objects.create(exam=final_ex, released=True, released_at=timezone.now(), released_by=admin_user, email_sent=True)
        self.stdout.write(self.style.SUCCESS("[OK] Exams, Results, and Releases loaded"))

        # 13. ACADEMIC CALENDAR
        events = [
            ('Diwali Holiday', 'Holiday - college closed', datetime.date(2026, 10, 20), 'holiday'),
            ('Mid Term 1 Examinations', 'Mid-term 1 for all branches', datetime.date(2026, 9, 14), 'exam'),
            ('Technical Fest Innovista', 'Annual technical festival', datetime.date(2026, 10, 5), 'event'),
            ('Mid Term 2 Examinations', 'Mid-term 2 for all branches', datetime.date(2026, 11, 16), 'exam'),
            ('Semester End Examinations', 'Final theory exams begin', datetime.date(2026, 12, 1), 'exam'),
        ]
        for title, desc, date, etype in events:
            AcademicCalendar.objects.get_or_create(title=title, date=date, defaults={'description': desc, 'event_type': etype})

        self.stdout.write(self.style.MIGRATE_HEADING("=" * 70))
        self.stdout.write(self.style.SUCCESS("  Sample data loaded successfully!"))
        self.stdout.write(self.style.MIGRATE_HEADING("=" * 70))
