from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction
from django.db.models import Q, Count
from django.utils import timezone
from django.core.paginator import Paginator
import datetime as dt
from functools import wraps

from accounts.models import User, Student, Faculty, Achievement, FacultyLeaveRequest
from core.models import (
    Branch, Year, Section, Subject, Timetable, Attendance, Exam, Result,
    Notification, ResultRelease, FacultyAttendance, ClassTransfer,
    ensure_sections_for_all_branches
)
from admin_dashboard.views import _send_result_emails
from core.sms_utils import send_result_notifications, send_result_sms_to_parent

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
    subject_count = Subject.objects.filter(branch=dept, is_deleted=False).count()
    section_count = Section.objects.filter(branch=dept).count()
    
    # Attendance today
    today = timezone.localdate()
    att_today = Attendance.objects.filter(student__branch=dept, date=today)
    present_today = att_today.filter(status='P').count()
    absent_today = att_today.filter(status='A').count()
    
    # Department notices
    notices = Notification.objects.filter(is_active=True, is_deleted=False).filter(
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
    subjects = Subject.objects.filter(branch=dept, is_deleted=False).select_related('faculty__user', 'year')
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
    ensure_sections_for_all_branches()
    dept = request.department
    sections = Section.objects.filter(branch=dept).select_related('year', 'branch')
    return render(request, 'hod/manage_timetable.html', {'sections': sections})

@hod_required
def edit_timetable(request, section_id):
    dept = request.department
    section = get_object_or_404(Section, id=section_id, branch=dept)
    subjects = Subject.objects.filter(branch=dept, year=section.year, is_deleted=False)
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
            start_time = request.POST.get('start_time') or None
            end_time = request.POST.get('end_time') or None
            room_number = request.POST.get('room_number', '').strip() or 'Room 101'
            
            Timetable.objects.update_or_create(
                section=section, day=day, period=period,
                defaults={
                    'subject': subj,
                    'faculty': fac,
                    'room_number': room_number,
                    'start_time': start_time,
                    'end_time': end_time,
                }
            )
            messages.success(request, f"Timetable slot updated: {day} Period {period} -> {subj.code} ({room_number}).")
            
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
# FACULTY ATTENDANCE MANAGEMENT
# ─────────────────────────────────────────────
@hod_required
def faculty_attendance(request):
    """
    Allows HOD to view and mark attendance for department faculty.
    Supports Month-wise filtering (`month_year`) and Custom Date Range filtering (`date_from`, `date_to`).
    """
    dept = request.department
    today = timezone.localdate()

    month_year = request.GET.get('month_year', '')
    date_from  = request.GET.get('date_from', '')
    date_to    = request.GET.get('date_to', '')
    selected_date_str = request.GET.get('date', today.isoformat())

    try:
        selected_date = dt.datetime.strptime(selected_date_str, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        selected_date = today

    department_faculty = Faculty.objects.filter(department=dept, is_active=True, user__is_deleted=False).select_related('user').order_by('employee_id')

    # Save attendance POST
    if request.method == 'POST':
        date_param = request.POST.get('date', today.isoformat())
        try:
            post_date = dt.datetime.strptime(date_param, '%Y-%m-%d').date()
        except ValueError:
            post_date = today

        saved_count = 0
        for fac in department_faculty:
            status = request.POST.get(f'status_{fac.id}', 'P')
            remarks = request.POST.get(f'remarks_{fac.id}', '').strip()
            if status not in ('P', 'A', 'L'):
                status = 'P'

            FacultyAttendance.objects.update_or_create(
                faculty=fac,
                date=post_date,
                defaults={
                    'status': status,
                    'remarks': remarks,
                    'marked_by': request.user,
                }
            )
            saved_count += 1

        messages.success(request, f"Faculty attendance updated for {saved_count} staff members for {post_date.strftime('%d %b %Y')}.")
        return redirect(f"{request.path}?date={post_date.isoformat()}&month_year={month_year}&date_from={date_from}&date_to={date_to}")

    # Build attendance query for logs report
    records_qs = FacultyAttendance.objects.filter(faculty__department=dept).select_related('faculty__user', 'marked_by')

    if month_year:
        try:
            yr, mn = map(int, month_year.split('-'))
            records_qs = records_qs.filter(date__year=yr, date__month=mn)
        except ValueError:
            pass
    elif date_from or date_to:
        if date_from:
            records_qs = records_qs.filter(date__gte=date_from)
        if date_to:
            records_qs = records_qs.filter(date__lte=date_to)
    else:
        records_qs = records_qs.filter(date=selected_date)

    records = records_qs.order_by('-date', 'faculty__employee_id')

    # Current daily attendance status for each faculty for the selected mark date
    today_records = {
        att.faculty_id: att for att in FacultyAttendance.objects.filter(faculty__department=dept, date=selected_date)
    }

    total_present = records.filter(status='P').count()
    total_absent  = records.filter(status='A').count()
    total_leave   = records.filter(status='L').count()

    context = {
        'department':         dept,
        'department_faculty': department_faculty,
        'selected_date':      selected_date.isoformat(),
        'today_records':      today_records,
        'records':            records,
        'month_year':         month_year,
        'date_from':          date_from,
        'date_to':            date_to,
        'total_present':      total_present,
        'total_absent':       total_absent,
        'total_leave':        total_leave,
    }
    return render(request, 'hod/faculty_attendance.html', context)

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
    qs = Student.objects.filter(branch=dept, user__is_deleted=False).select_related('user', 'year', 'section').order_by('roll_number')
    
    search = request.GET.get('q', '')
    if search:
        qs = qs.filter(
            Q(roll_number__icontains=search) | 
            Q(user__first_name__icontains=search) | 
            Q(user__last_name__icontains=search) |
            Q(branch__code__icontains=search) |
            Q(branch__name__icontains=search) |
            Q(section__name__icontains=search) |
            Q(year__year__icontains=search)
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
            
        email = p.get('email', '').strip()
        if not email:
            email = f"{username}@vvitu.net"

        user = User.objects.create_user(
            username=username,
            password=p.get('password', 'vvit@1234'),
            first_name=first_name,
            last_name=last_name,
            email=email,
            role='student',
            phone=p.get('phone', ''),
        )
        
        fees_val = p.get('fees_pending')
        fees_pending_amount = 0.00
        if fees_val is not None and fees_val != '':
            try:
                fees_pending_amount = float(fees_val)
            except ValueError:
                pass

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
            parent_occupation=p.get('parent_occupation', '').strip() or None,
            parent_mobile=p.get('parent_mobile', '').strip() or None,
            personal_mobile=p.get('personal_mobile', '').strip() or None,
            gender=p.get('gender', '').strip() or None,
            caste=p.get('caste', '').strip() or None,
            religion=p.get('religion', '').strip() or None,
            permanent_address=p.get('permanent_address', '').strip() or None,
            present_address=p.get('present_address', '').strip() or None,
            fees_pending=fees_pending_amount,
            fees_updated_at=timezone.now() if fees_pending_amount > 0 else None,
        )
        
        Notification.objects.create(
            title="Student Account Created by HOD",
            message=f"HOD {request.user.get_full_name() or request.user.username} created student {first_name} {last_name} ({username}) in department {dept.code}.",
            notif_type=Notification.TYPE_SYSTEM,
            priority=Notification.PRIORITY_HIGH,
            target_all=False,
            target_role='admin',
            created_by=request.user
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
        email = p.get('email', '').strip()
        u.email = email or f"{student.roll_number}@vvitu.net"

        password = p.get('password', '').strip()
        if password:
            if len(password) < 6:
                messages.error(request, "Password must be at least 6 characters long.")
                return redirect('hod:edit_student', pk=pk)
            u.set_password(password)
            student.is_first_login = False

        u.save()
        
        student.year_id = p.get('year', student.year_id)
        student.section_id = p.get('section', student.section_id)
        student.class_teacher_id = p.get('class_teacher') or None
        student.counsellor_id = p.get('counsellor') or None
        student.parent_name = p.get('parent_name', '').strip() or None
        student.parent_occupation = p.get('parent_occupation', '').strip() or None
        student.parent_mobile = p.get('parent_mobile', '').strip() or None
        student.personal_mobile = p.get('personal_mobile', '').strip() or None
        student.gender = p.get('gender', '').strip() or None
        student.caste = p.get('caste', '').strip() or None
        student.religion = p.get('religion', '').strip() or None
        student.permanent_address = p.get('permanent_address', '').strip() or None
        student.present_address = p.get('present_address', '').strip() or None

        fees_val = p.get('fees_pending')
        if fees_val is not None and fees_val != '':
            try:
                student.fees_pending = float(fees_val)
                student.fees_updated_at = timezone.now()
            except ValueError:
                pass

        student.save()
        
        Notification.objects.create(
            title="Student Account Updated by HOD",
            message=f"HOD {request.user.get_full_name() or request.user.username} updated student {first_name} {last_name} ({student.roll_number}) details.",
            notif_type=Notification.TYPE_SYSTEM,
            priority=Notification.PRIORITY_HIGH,
            target_all=False,
            target_role='admin',
            created_by=request.user
        )
        
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
        user = student.user
        user.is_active = False
        user.is_deleted = True
        user.deleted_by_name = f"{request.user.get_full_name() or request.user.username} ({request.user.role.upper()})"
        from django.utils import timezone
        user.deleted_at = timezone.now()
        user.save()
        
        Notification.objects.create(
            title="Student Account Deleted by HOD",
            message=f"HOD {request.user.get_full_name() or request.user.username} deleted student {student.roll_number}.",
            notif_type=Notification.TYPE_SYSTEM,
            priority=Notification.PRIORITY_HIGH,
            target_all=False,
            target_role='admin',
            created_by=request.user
        )
        
        messages.success(request, "Student profile soft-deleted successfully.")
    return redirect('hod:manage_students')


@hod_required
def manage_faculty(request):
    dept = request.department
    faculties = Faculty.objects.filter(department=dept, user__is_deleted=False).select_related('user').order_by('employee_id')
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
            
        email = p.get('email', '').strip()
        user = User.objects.create_user(
            username=emp_id,
            password=p.get('password', 'vvit@1234'),
            first_name=first_name,
            last_name=last_name,
            email=email,
            role='faculty',
            phone=p.get('phone', ''),
        )
        
        Faculty.objects.create(
            user=user,
            employee_id=emp_id,
            department=dept,
            designation=p.get('designation', 'Assistant Professor'),
        )
        
        Notification.objects.create(
            title="Faculty Account Created by HOD",
            message=f"HOD {request.user.get_full_name() or request.user.username} created faculty member {first_name} {last_name} ({emp_id}).",
            notif_type=Notification.TYPE_SYSTEM,
            priority=Notification.PRIORITY_HIGH,
            target_all=False,
            target_role='admin',
            created_by=request.user
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
        u.email = p.get('email', '').strip()

        password = p.get('password', '').strip()
        if password:
            if len(password) < 6:
                messages.error(request, "Password must be at least 6 characters long.")
                return redirect('hod:edit_faculty', pk=pk)
            u.set_password(password)

        u.save()
        
        fac.designation = p.get('designation', fac.designation)
        fac.save()
        
        Notification.objects.create(
            title="Faculty Account Updated by HOD",
            message=f"HOD {request.user.get_full_name() or request.user.username} updated faculty member {first_name} {last_name} ({fac.employee_id}) details.",
            notif_type=Notification.TYPE_SYSTEM,
            priority=Notification.PRIORITY_HIGH,
            target_all=False,
            target_role='admin',
            created_by=request.user
        )
        
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
            selected_date = dt.datetime.strptime(date_str, '%Y-%m-%d').date()
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

@hod_required
def release_results(request):
    dept = request.department
    exams = (
        Exam.objects
        .filter(branch=dept)
        .select_related('year')
        .prefetch_related('release')
        .order_by('-date')
    )

    # Build a status dict {exam_id: ResultRelease}
    release_map = {}
    for exam in exams:
        try:
            release_map[exam.id] = exam.release
        except ResultRelease.DoesNotExist:
            release_map[exam.id] = None

    if request.method == 'POST':
        exam_id = request.POST.get('exam_id')
        action  = request.POST.get('action')   # 'release' or 'unrelease'

        # Ensure HOD can only release results for their branch's exams
        exam = get_object_or_404(Exam, pk=exam_id, branch=dept)

        release_obj, _ = ResultRelease.objects.get_or_create(exam=exam)

        if action == 'release':
            release_obj.released    = True
            release_obj.released_at = timezone.now()
            release_obj.released_by = request.user
            release_obj.save()

            # Send emails & parent SMS if not already sent
            sms_sent_count = 0
            student_results = {}
            results_qs = Result.objects.filter(exam=exam).select_related('student__user', 'subject')
            for r in results_qs:
                if r.student_id not in student_results:
                    student_results[r.student_id] = {'student': r.student, 'results': []}
                student_results[r.student_id]['results'].append(r)

            for sid, data in student_results.items():
                from core.sms_utils import send_result_notifications
                if send_result_notifications(data['student'], exam, data['results']):
                    sms_sent_count += 1

            if not release_obj.email_sent:
                sent, failed = _send_result_emails(exam, request)
                release_obj.email_sent = True
                release_obj.save()
                messages.success(
                    request,
                    f"Results released for '{exam.name}'. Emails sent: {sent}, Parent SMS sent: {sms_sent_count}."
                )
            else:
                messages.success(request, f"Results released for '{exam.name}'. Parent SMS sent: {sms_sent_count}.")
                messages.success(request, f"Results released for '{exam.name}'.")

            Notification.objects.create(
                title="Results Released by HOD",
                message=f"HOD {request.user.get_full_name() or request.user.username} released results for exam {exam.name}.",
                notif_type=Notification.TYPE_SYSTEM,
                priority=Notification.PRIORITY_HIGH,
                target_all=False,
                target_role='admin',
                created_by=request.user
            )

        elif action == 'unrelease':
            release_obj.released = False
            release_obj.save()
            messages.warning(request, f"Results hidden for '{exam.name}'.")

            Notification.objects.create(
                title="Results Hidden by HOD",
                message=f"HOD {request.user.get_full_name() or request.user.username} hid results for exam {exam.name}.",
                notif_type=Notification.TYPE_SYSTEM,
                priority=Notification.PRIORITY_HIGH,
                target_all=False,
                target_role='admin',
                created_by=request.user
            )

        return redirect('hod:release_results')

    context = {
        'department':  dept,
        'exams':       exams,
        'release_map': release_map,
    }
    return render(request, 'hod/release_results.html', context)


# ─────────────────────────────────────────────
# SUBJECT CRUD
# ─────────────────────────────────────────────
@hod_required
def manage_subjects(request):
    dept = request.department
    qs = Subject.objects.filter(branch=dept, is_deleted=False).select_related('year', 'faculty__user').order_by('year', 'semester', 'name')
    
    search = request.GET.get('q', '')
    if search:
        qs = qs.filter(
            Q(name__icontains=search) | 
            Q(code__icontains=search)
        )
        
    paginator = Paginator(qs, 25)
    page = paginator.get_page(request.GET.get('page', 1))
    return render(request, 'hod/manage_subjects.html', {'page': page, 'search': search, 'department': dept})


@hod_required
def add_subject(request):
    dept = request.department
    years = Year.objects.all()
    faculties = Faculty.objects.filter(department=dept, is_active=True).select_related('user')
    
    if request.method == 'POST':
        p = request.POST
        name = p.get('name', '').strip()
        code = p.get('code', '').strip().upper()
        year_id = p.get('year')
        semester = p.get('semester')
        faculty_id = p.get('faculty') or None
        credits_val = p.get('credits', '3')
        is_lab = p.get('is_lab') == 'true'
        
        if not name or not code or not year_id or not semester:
            messages.error(request, "Please fill in all required fields.")
            return redirect('hod:add_subject')
            
        if Subject.objects.filter(code=code).exists():
            messages.error(request, f"Subject code '{code}' already exists.")
            return redirect('hod:add_subject')
            
        try:
            credits_int = int(credits_val)
        except ValueError:
            credits_int = 3
            
        Subject.objects.create(
            name=name,
            code=code,
            branch=dept,
            year_id=year_id,
            semester=semester,
            faculty_id=faculty_id,
            credits=credits_int,
            is_lab=is_lab
        )
        
        Notification.objects.create(
            title="Subject Created by HOD",
            message=f"HOD {request.user.get_full_name() or request.user.username} created subject {name} ({code}) in department {dept.code}.",
            notif_type=Notification.TYPE_SYSTEM,
            priority=Notification.PRIORITY_HIGH,
            target_all=False,
            target_role='admin',
            created_by=request.user
        )
        
        messages.success(request, f"Subject '{name}' created successfully.")
        return redirect('hod:manage_subjects')
        
    return render(request, 'hod/add_subject.html', {
        'years': years,
        'faculties': faculties,
        'department': dept,
        'semester_choices': Subject.SEMESTER_CHOICES,
    })


@hod_required
def delete_subject(request, pk):
    dept = request.department
    subject = get_object_or_404(Subject, pk=pk, branch=dept)
    if request.method == 'POST':
        subject.is_deleted = True
        subject.deleted_by_name = f"{request.user.get_full_name() or request.user.username} ({request.user.role.upper()})"
        from django.utils import timezone
        subject.deleted_at = timezone.now()
        subject.save()
        
        Notification.objects.create(
            title="Subject Deleted by HOD",
            message=f"HOD {request.user.get_full_name() or request.user.username} soft-deleted subject {subject.name} ({subject.code}) in department {dept.code}.",
            notif_type=Notification.TYPE_SYSTEM,
            priority=Notification.PRIORITY_HIGH,
            target_all=False,
            target_role='admin',
            created_by=request.user
        )
        
        messages.success(request, "Subject soft-deleted successfully.")
    return redirect('hod:manage_subjects')


# ─────────────────────────────────────────────
# HOD LEAVE MANAGEMENT & APPLICATION
# ─────────────────────────────────────────────
@hod_required
def manage_leave_requests(request):
    dept = request.department
    status_filter = request.GET.get('status', '')
    
    if request.method == 'POST':
        leave_type = request.POST.get('leave_type')
        start_date_str = request.POST.get('start_date')
        end_date_str = request.POST.get('end_date')
        reason = request.POST.get('reason', '').strip()
        substitute_notes = request.POST.get('substitute_notes', '').strip()
        
        if not leave_type or not start_date_str or not end_date_str or not reason:
            messages.error(request, "Please fill in all required leave application fields.")
        else:
            try:
                start_date = dt.datetime.strptime(start_date_str, '%Y-%m-%d').date()
                end_date = dt.datetime.strptime(end_date_str, '%Y-%m-%d').date()
                
                if end_date < start_date:
                    messages.error(request, "End date cannot be earlier than start date.")
                else:
                    leave_req = FacultyLeaveRequest.objects.create(
                        faculty=request.faculty,
                        leave_type=leave_type,
                        start_date=start_date,
                        end_date=end_date,
                        reason=reason,
                        substitute_notes=substitute_notes,
                        status='pending'
                    )
                    
                    # Notify Admin about HOD leave request
                    try:
                        Notification.objects.create(
                            title=f"HOD Leave Application — {request.faculty.full_name}",
                            message=(
                                f"HOD {request.faculty.full_name} ({dept.code}) applied for {leave_req.get_leave_type_display()} "
                                f"from {start_date.strftime('%d-%b-%Y')} to {end_date.strftime('%d-%b-%Y')}. "
                                f"Admin approval is required."
                            ),
                            notif_type=Notification.TYPE_ALERT,
                            priority=Notification.PRIORITY_HIGH,
                            target_all=False,
                            target_role='admin',
                            created_by=request.user
                        )
                    except Exception:
                        pass
                        
                    messages.success(request, "Your leave application has been submitted to College Administration for approval.")
                    return redirect('hod:manage_leave_requests')
            except ValueError:
                messages.error(request, "Invalid date format submitted.")
    
    # HOD's own leave applications
    my_leaves = FacultyLeaveRequest.objects.filter(
        faculty=request.faculty
    ).order_by('-created_at')
    
    # Department faculty leaves (excluding HOD's own leave request from actioning queue)
    dept_faculty_leaves = FacultyLeaveRequest.objects.filter(
        faculty__department=dept
    ).exclude(
        faculty=request.faculty
    ).select_related('faculty__user', 'action_by').order_by('-created_at')
    
    if status_filter in ['pending', 'approved', 'rejected']:
        dept_faculty_leaves = dept_faculty_leaves.filter(status=status_filter)
        
    pending_count = FacultyLeaveRequest.objects.filter(
        faculty__department=dept, 
        status='pending'
    ).exclude(faculty=request.faculty).count()
    
    return render(request, 'hod/leave_requests.html', {
        'department': dept,
        'leaves': dept_faculty_leaves,
        'my_leaves': my_leaves,
        'status_filter': status_filter,
        'pending_count': pending_count,
        'leave_type_choices': FacultyLeaveRequest.LEAVE_TYPE_CHOICES,
    })


@hod_required
def action_leave_request(request, pk, action):
    dept = request.department
    leave_req = get_object_or_404(FacultyLeaveRequest, pk=pk, faculty__department=dept)
    
    # Guard: HOD cannot approve or reject their own leave or another HOD's leave!
    if leave_req.faculty == request.faculty or leave_req.faculty.user.role == 'hod':
        messages.error(request, "HOD leave applications can only be approved or rejected by College Administration.")
        return redirect('hod:manage_leave_requests')
    
    if action not in ['approve', 'reject']:
        messages.error(request, "Invalid leave action.")
        return redirect('hod:manage_leave_requests')
        
    remarks = request.POST.get('remarks', '').strip() if request.method == 'POST' else ''
    
    new_status = 'approved' if action == 'approve' else 'rejected'
    leave_req.status = new_status
    leave_req.action_by = request.user
    leave_req.action_at = timezone.now()
    if remarks:
        leave_req.admin_remarks = remarks
    leave_req.save()
    
    try:
        status_text = "Approved" if new_status == 'approved' else "Rejected"
        notif_msg = (
            f"Your leave request for {leave_req.get_leave_type_display()} "
            f"({leave_req.start_date.strftime('%d-%b-%Y')} to {leave_req.end_date.strftime('%d-%b-%Y')}) "
            f"has been {status_text} by HOD {request.user.get_full_name() or request.user.username}."
        )
        if remarks:
            notif_msg += f" Remarks: {remarks}"
            
        Notification.objects.create(
            title=f"Leave Request {status_text}",
            message=notif_msg,
            notif_type=Notification.TYPE_ALERT,
            priority=Notification.PRIORITY_HIGH,
            target_user=leave_req.faculty.user,
            created_by=request.user
        )
        
        from core.sms_utils import send_sms
        if leave_req.faculty.user.email:
            from django.core.mail import send_mail
            send_mail(
                subject=f"[Leave Request {status_text}] VVITU Leave Application",
                message=notif_msg,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@vvitu.ac.in'),
                recipient_list=[leave_req.faculty.user.email],
                fail_silently=True
            )
        if leave_req.faculty.phone:
            send_sms(leave_req.faculty.phone, f"VVITU: Leave Request {status_text} by HOD. Log in for details.")
    except Exception:
        pass
        
    messages.success(request, f"Leave request for {leave_req.faculty.full_name} {new_status} successfully.")
    return redirect('hod:manage_leave_requests')


@hod_required
def cancel_leave_request(request, pk):
    leave_req = get_object_or_404(FacultyLeaveRequest, pk=pk, faculty=request.faculty, status='pending')
    leave_req.delete()
    messages.success(request, "Your leave application has been cancelled.")
    return redirect('hod:manage_leave_requests')

