from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction
from django.db.models import Q, Count
from django.utils import timezone
from django.core.paginator import Paginator
from functools import wraps

from accounts.models import User, Student, Faculty, Achievement
from core.models import Branch, Year, Section, Subject, Timetable, Attendance, Exam, Result, Notification

# ─────────────────────────────────────────────
# DECORATOR
# ─────────────────────────────────────────────
def hod_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or request.user.role != 'hod':
            messages.error(request, "Access denied. HODs only.")
            return redirect('accounts:login')
        try:
            request.faculty = request.user.faculty_profile
            request.department = request.faculty.department
            if not request.department:
                messages.error(request, "Access denied. HOD has no department assigned. Please contact the administrator.")
                return redirect('accounts:login')
        except Faculty.DoesNotExist:
            messages.error(request, "HOD Faculty Profile not found.")
            return redirect('accounts:login')
        return view_func(request, *args, **kwargs)
    return wrapper

# ─────────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────────
@hod_required
def dashboard(request):
    dept = request.department
    
    # Department stats
    student_count = Student.objects.filter(branch=dept, is_active=True).count()
    faculty_count = Faculty.objects.filter(department=dept, is_active=True).count()
    subject_count = Subject.objects.filter(branch=dept).count()
    section_count = Section.objects.filter(branch=dept).count()
    
    # Attendance today
    today = timezone.localdate()
    att_today = Attendance.objects.filter(student__branch=dept, date=today)
    present_today = att_today.filter(status='P').count()
    absent_today = att_today.filter(status='A').count()
    
    # Department notices
    notices = Notification.objects.filter(
        Q(target_branch=dept) | Q(target_all=True)
    ).order_by('-created_at')[:5]
    
    # Pending achievements in the department
    pending_achievements = Achievement.objects.filter(
        is_verified=False
    ).filter(
        Q(user__student_profile__branch=dept) | Q(user__faculty_profile__department=dept)
    ).select_related('user').order_by('-created_at')
    
    context = {
        'student_count': student_count,
        'faculty_count': faculty_count,
        'subject_count': subject_count,
        'section_count': section_count,
        'present_today': present_today,
        'absent_today': absent_today,
        'notices': notices,
        'pending_achievements': pending_achievements,
        'department': dept,
    }
    return render(request, 'hod/dashboard.html', context)

# ─────────────────────────────────────────────
# NOTICE BOARD / NOTIFICATION CIRCULATION
# ─────────────────────────────────────────────
@hod_required
def create_notice(request):
    dept = request.department
    sections = Section.objects.filter(branch=dept)
    
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        message = request.POST.get('message', '').strip()
        circulation = request.POST.get('circulation', 'branch')  # college, branch, class
        section_id = request.POST.get('section', '')
        
        if not title or not message:
            messages.error(request, "Title and message are required.")
            return redirect('hod:create_notice')
            
        notif = Notification(
            title=title,
            message=message,
            notif_type=Notification.TYPE_ANNOUNCEMENT,
            created_by=request.user,
        )
        
        if circulation == 'college':
            notif.target_all = True
        elif circulation == 'branch':
            notif.target_all = False
            notif.target_branch = dept
        elif circulation == 'class' and section_id:
            notif.target_all = False
            notif.target_branch = dept
            notif.target_role = 'student'
            # Store target section link
            try:
                sec = Section.objects.get(id=section_id, branch=dept)
                notif.target_section = sec
            except Section.DoesNotExist:
                pass
                
        notif.save()
        messages.success(request, "Notice circulated successfully.")
        return redirect('hod:dashboard')
        
    return render(request, 'hod/create_notice.html', {'sections': sections, 'department': dept})

# ─────────────────────────────────────────────
# SUBJECT & FACULTY MAPPING
# ─────────────────────────────────────────────
@hod_required
def subject_mapping(request):
    dept = request.department
    subjects = Subject.objects.filter(branch=dept).select_related('faculty__user', 'year')
    faculties = Faculty.objects.filter(department=dept, is_active=True).select_related('user')
    
    if request.method == 'POST':
        subj_id = request.POST.get('subject_id')
        fac_id = request.POST.get('faculty_id') or None
        
        subj = get_object_or_404(Subject, id=subj_id, branch=dept)
        if fac_id:
            fac = get_object_or_404(Faculty, id=fac_id, department=dept)
            subj.faculty = fac
        else:
            subj.faculty = None
        subj.save()
        messages.success(request, f"Faculty assigned to {subj.code} successfully.")
        return redirect('hod:subject_mapping')
        
    return render(request, 'hod/subject_mapping.html', {
        'subjects': subjects,
        'faculties': faculties,
    })

# ─────────────────────────────────────────────
# ASSIGN CLASS TEACHER / COUNSELLOR
# ─────────────────────────────────────────────
@hod_required
def assign_teacher(request):
    dept = request.department
    sections = Section.objects.filter(branch=dept).select_related('year')
    faculties = Faculty.objects.filter(department=dept, is_active=True).select_related('user')
    students = Student.objects.filter(branch=dept, is_active=True).select_related('user', 'section', 'class_teacher', 'counsellor')
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'class_teacher':
            section_id = request.POST.get('section')
            faculty_id = request.POST.get('faculty') or None
            
            sec = get_object_or_404(Section, id=section_id, branch=dept)
            fac = get_object_or_404(Faculty, id=faculty_id, department=dept) if faculty_id else None
            
            # Batch update student class teachers in this section
            updated = Student.objects.filter(section=sec).update(class_teacher=fac)
            messages.success(request, f"Class Teacher assigned to {updated} students in {sec}.")
            
        elif action == 'counsellor':
            student_id = request.POST.get('student')
            faculty_id = request.POST.get('faculty') or None
            
            stu = get_object_or_404(Student, id=student_id, branch=dept)
            fac = get_object_or_404(Faculty, id=faculty_id, department=dept) if faculty_id else None
            
            stu.counsellor = fac
            stu.save()
            messages.success(request, f"Counsellor assigned to {stu.roll_number} successfully.")
            
        return redirect('hod:assign_teacher')
        
    return render(request, 'hod/assign_teacher.html', {
        'sections': sections,
        'faculties': faculties,
        'students': students,
    })

# ─────────────────────────────────────────────
# TIMETABLE MANAGEMENT
# ─────────────────────────────────────────────
@hod_required
def manage_timetable(request):
    dept = request.department
    sections = Section.objects.filter(branch=dept).select_related('year')
    return render(request, 'hod/manage_timetable.html', {'sections': sections})

@hod_required
def edit_timetable(request, section_id):
    dept = request.department
    section = get_object_or_404(Section, id=section_id, branch=dept)
    subjects = Subject.objects.filter(branch=dept, year=section.year)
    faculties = Faculty.objects.filter(department=dept, is_active=True).select_related('user')
    
    entries = Timetable.objects.filter(section=section).select_related('subject', 'faculty__user').order_by('day', 'period')
    
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
    periods = list(range(1, 9))
    grid = {day: {p: None for p in periods} for day in days}
    for e in entries:
        if e.day in grid:
            grid[e.day][e.period] = e
            
    if request.method == 'POST':
        day = request.POST.get('day')
        period = request.POST.get('period')
        subject_id = request.POST.get('subject')
        faculty_id = request.POST.get('faculty')
        delete_slot = request.POST.get('delete')
        
        try:
            period = int(period)
        except ValueError:
            messages.error(request, "Invalid period.")
            return redirect('hod:edit_timetable', section_id=section_id)
            
        if delete_slot:
            Timetable.objects.filter(section=section, day=day, period=period).delete()
            messages.success(request, f"Timetable slot for {day} Period {period} deleted.")
        else:
            subj = get_object_or_404(Subject, id=subject_id, branch=dept)
            fac = get_object_or_404(Faculty, id=faculty_id, department=dept)
            
            Timetable.objects.update_or_create(
                section=section, day=day, period=period,
                defaults={'subject': subj, 'faculty': fac}
            )
            messages.success(request, f"Timetable slot updated: {day} Period {period} -> {subj.code}.")
            
        return redirect('hod:edit_timetable', section_id=section_id)
        
    return render(request, 'hod/edit_timetable.html', {
        'section': section,
        'days': days,
        'periods': periods,
        'grid': grid,
        'subjects': subjects,
        'faculties': faculties,
    })

# ─────────────────────────────────────────────
# ACHIEVEMENTS VERIFICATION
# ─────────────────────────────────────────────
@hod_required
def verify_achievements(request):
    dept = request.department
    achievements = Achievement.objects.filter(
        Q(user__student_profile__branch=dept) | Q(user__faculty_profile__department=dept)
    ).select_related('user').order_by('is_verified', '-date_achieved')
    
    return render(request, 'hod/verify_achievements.html', {'achievements': achievements})

@hod_required
def verify_achievement_action(request, pk, action_type):
    dept = request.department
    ach = get_object_or_404(Achievement, id=pk)
    
    # Verify the user belongs to the HOD's department
    user_branch = None
    if ach.user.role == 'student':
        user_branch = ach.user.student_profile.branch
    elif ach.user.role in ['faculty', 'hod', 'lab_technician']:
        user_branch = ach.user.faculty_profile.department
        
    if user_branch != dept:
        messages.error(request, "Unauthorized to verify achievements outside your branch.")
        return redirect('hod:verify_achievements')
        
    if action_type == 'approve':
        ach.is_verified = True
        ach.verified_by = request.user
        ach.save()
        messages.success(request, f"Achievement '{ach.title}' approved.")
    elif action_type == 'reject':
        ach.delete()
        messages.success(request, "Achievement rejected and deleted.")
        
    return redirect('hod:verify_achievements')

# ─────────────────────────────────────────────
# STUDENT & FACULTY SCOPED CRUD
# ─────────────────────────────────────────────
@hod_required
def manage_students(request):
    dept = request.department
    qs = Student.objects.filter(branch=dept).select_related('user', 'year', 'section').order_by('roll_number')
    
    search = request.GET.get('q', '')
    if search:
        qs = qs.filter(
            Q(roll_number__icontains=search) | 
            Q(user__first_name__icontains=search) | 
            Q(user__last_name__icontains=search)
        )
        
    paginator = Paginator(qs, 25)
    page = paginator.get_page(request.GET.get('page', 1))
    return render(request, 'hod/manage_students.html', {'page': page, 'search': search, 'department': dept})

@hod_required
def add_student(request):
    dept = request.department
    years = Year.objects.all()
    sections = Section.objects.filter(branch=dept).select_related('year')
    faculties = Faculty.objects.filter(department=dept, is_active=True).select_related('user')
    
    if request.method == 'POST':
        p = request.POST
        username = p.get('username', '').strip().upper()
        
        first_name = p.get('first_name', '').strip()
        last_name  = p.get('last_name',  '').strip()

        if len(first_name) < 3:
            messages.error(request, "First name must be at least 3 characters long.")
            return redirect('hod:add_student')
        if len(last_name) < 1:
            messages.error(request, "Last name must be at least 1 character long.")
            return redirect('hod:add_student')
            
        if User.objects.filter(username=username).exists():
            messages.error(request, f"Student Roll Number '{username}' already exists.")
            return redirect('hod:add_student')
            
        user = User.objects.create_user(
            username=username,
            password=p.get('password', 'vvit@1234'),
            first_name=first_name,
            last_name=last_name,
            email=f"{username}@vvit.net",
            role='student',
            phone=p.get('phone', ''),
        )
        
        Student.objects.create(
            user=user,
            roll_number=username,
            branch=dept,
            year_id=p.get('year'),
            section_id=p.get('section'),
            class_teacher_id=p.get('class_teacher') or None,
            counsellor_id=p.get('counsellor') or None,
            admission_year=p.get('admission_year', 2024),
            parent_name=p.get('parent_name', '').strip() or None,
            parent_mobile=p.get('parent_mobile', '').strip() or None,
        )
        messages.success(request, f"Student {username} created successfully.")
        return redirect('hod:manage_students')
        
    return render(request, 'hod/add_student.html', {
        'years': years,
        'sections': sections,
        'faculties': faculties,
        'department': dept,
    })

@hod_required
def edit_student(request, pk):
    dept = request.department
    student = get_object_or_404(Student, pk=pk, branch=dept)
    years = Year.objects.all()
    sections = Section.objects.filter(branch=dept).select_related('year')
    faculties = Faculty.objects.filter(department=dept, is_active=True).select_related('user')
    
    if request.method == 'POST':
        p = request.POST
        first_name = p.get('first_name', '').strip()
        last_name  = p.get('last_name',  '').strip()

        if len(first_name) < 3:
            messages.error(request, "First name must be at least 3 characters long.")
            return redirect('hod:edit_student', pk=pk)
        if len(last_name) < 1:
            messages.error(request, "Last name must be at least 1 character long.")
            return redirect('hod:edit_student', pk=pk)
            
        u = student.user
        u.first_name = first_name
        u.last_name = last_name
        u.phone = p.get('phone', u.phone)
        u.save()
        
        student.year_id = p.get('year', student.year_id)
        student.section_id = p.get('section', student.section_id)
        student.class_teacher_id = p.get('class_teacher') or None
        student.counsellor_id = p.get('counsellor') or None
        student.parent_name = p.get('parent_name', '').strip() or None
        student.parent_mobile = p.get('parent_mobile', '').strip() or None
        student.save()
        
        messages.success(request, f"Student {student.roll_number} updated.")
        return redirect('hod:manage_students')
        
    return render(request, 'hod/edit_student.html', {
        'student': student,
        'years': years,
        'sections': sections,
        'faculties': faculties,
    })

@hod_required
def delete_student(request, pk):
    dept = request.department
    student = get_object_or_404(Student, pk=pk, branch=dept)
    if request.method == 'POST':
        student.user.delete()
        messages.success(request, "Student profile deleted.")
    return redirect('hod:manage_students')

@hod_required
def manage_faculty(request):
    dept = request.department
    faculties = Faculty.objects.filter(department=dept).select_related('user').order_by('employee_id')
    return render(request, 'hod/manage_faculty.html', {'faculties': faculties, 'department': dept})

@hod_required
def add_faculty(request):
    dept = request.department
    if request.method == 'POST':
        p = request.POST
        emp_id = p.get('employee_id', '').strip().upper()
        first_name = p.get('first_name', '').strip()
        last_name  = p.get('last_name',  '').strip()

        if len(first_name) < 3:
            messages.error(request, "First name must be at least 3 characters long.")
            return redirect('hod:add_faculty')
        if len(last_name) < 1:
            messages.error(request, "Last name must be at least 1 character long.")
            return redirect('hod:add_faculty')
            
        if User.objects.filter(username=emp_id).exists():
            messages.error(request, f"Employee ID '{emp_id}' already exists.")
            return redirect('hod:add_faculty')
            
        user = User.objects.create_user(
            username=emp_id,
            password=p.get('password', 'vvit@1234'),
            first_name=first_name,
            last_name=last_name,
            email=f"{emp_id}@vvit.net",
            role='faculty',
            phone=p.get('phone', ''),
        )
        
        Faculty.objects.create(
            user=user,
            employee_id=emp_id,
            department=dept,
            designation=p.get('designation', 'Assistant Professor'),
        )
        messages.success(request, f"Faculty {emp_id} created successfully.")
        return redirect('hod:manage_faculty')
        
    return render(request, 'hod/add_faculty.html')

@hod_required
def edit_faculty(request, pk):
    dept = request.department
    fac = get_object_or_404(Faculty, pk=pk, department=dept)
    
    if request.method == 'POST':
        p = request.POST
        first_name = p.get('first_name', '').strip()
        last_name  = p.get('last_name',  '').strip()

        if len(first_name) < 3:
            messages.error(request, "First name must be at least 3 characters long.")
            return redirect('hod:edit_faculty', pk=pk)
        if len(last_name) < 1:
            messages.error(request, "Last name must be at least 1 character long.")
            return redirect('hod:edit_faculty', pk=pk)
            
        u = fac.user
        u.first_name = first_name
        u.last_name = last_name
        u.phone = p.get('phone', u.phone)
        u.save()
        
        fac.designation = p.get('designation', fac.designation)
        fac.save()
        messages.success(request, f"Faculty {fac.employee_id} updated.")
        return redirect('hod:manage_faculty')
        
    return render(request, 'hod/edit_faculty.html', {'fac': fac})

# ─────────────────────────────────────────────
# ATTENDANCE LIST & EDIT OVERRIDE
# ─────────────────────────────────────────────
@hod_required
def attendance_list(request):
    dept = request.department
    # Fetch sections in branch
    sections = Section.objects.filter(branch=dept)
    
    section_id = request.GET.get('section', '')
    date_str = request.GET.get('date', '')
    
    records = []
    selected_section = None
    selected_date = None
    
    if section_id and date_str:
        try:
            selected_section = Section.objects.get(id=section_id, branch=dept)
            selected_date = timezone.datetime.strptime(date_str, '%Y-%m-%d').date()
            records = Attendance.objects.filter(
                student__section=selected_section,
                date=selected_date
            ).select_related('student__user', 'timetable_entry__subject', 'timetable_entry__faculty__user')
        except Exception as e:
            pass
            
    return render(request, 'hod/attendance_list.html', {
        'sections': sections,
        'records': records,
        'selected_section_id': section_id,
        'selected_date': date_str,
    })

@hod_required
def edit_attendance(request, pk):
    dept = request.department
    record = get_object_or_404(Attendance, pk=pk, student__branch=dept)
    
    if request.method == 'POST':
        status = request.POST.get('status')
        if status in ['P', 'A']:
            record.status = status
            record.save()
            messages.success(request, f"Attendance for {record.student.roll_number} updated to {record.get_status_display()}.")
            return redirect(f"/hod/attendance/?section={record.student.section.id}&date={record.date.strftime('%Y-%m-%d')}")
            
    return render(request, 'hod/edit_attendance.html', {'record': record})
