from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from functools import wraps
import datetime

from accounts.models import User, Student, Faculty, DEOProfile, Achievement
from core.models import Branch, Year, Section, Subject, Timetable, Attendance, Exam, Result, Notification

# ─────────────────────────────────────────────
# DECORATOR
# ─────────────────────────────────────────────
def deo_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or request.user.role != 'deo':
            messages.error(request, "Access denied. DEOs only.")
            return redirect('accounts:login')
        try:
            request.deo_profile = request.user.deo_profile
            request.branch = request.deo_profile.branch
        except DEOProfile.DoesNotExist:
            messages.error(request, "DEO Profile not found. Contact administrator.")
            return redirect('accounts:login')
        return view_func(request, *args, **kwargs)
    return wrapper

# ─────────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────────
@deo_required
def dashboard(request):
    branch = request.branch
    student_count = Student.objects.filter(branch=branch, is_active=True).count()
    faculty_count = Faculty.objects.filter(department=branch, is_active=True).count()
    
    context = {
        'deo_profile': request.deo_profile,
        'branch': branch,
        'student_count': student_count,
        'faculty_count': faculty_count,
    }
    return render(request, 'deo/dashboard.html', context)

# ─────────────────────────────────────────────
# STUDENT DIRECTORY (Scoped to Branch)
# ─────────────────────────────────────────────
@deo_required
def manage_students(request):
    branch = request.branch
    qs = Student.objects.filter(branch=branch).select_related('user', 'year', 'section').order_by('roll_number')
    
    search = request.GET.get('q', '')
    if search:
        qs = qs.filter(
            Q(roll_number__icontains=search) | 
            Q(user__first_name__icontains=search) | 
            Q(user__last_name__icontains=search)
        )
        
    from django.core.paginator import Paginator
    paginator = Paginator(qs, 25)
    page = paginator.get_page(request.GET.get('page', 1))
    return render(request, 'deo/manage_students.html', {'page': page, 'search': search, 'branch': branch})

@deo_required
def add_student(request):
    branch = request.branch
    years = Year.objects.all()
    sections = Section.objects.filter(branch=branch).select_related('year')
    faculties = Faculty.objects.filter(department=branch, is_active=True).select_related('user')
    
    if request.method == 'POST':
        p = request.POST
        username = p.get('username', '').strip().upper()
        
        first_name = p.get('first_name', '').strip()
        last_name  = p.get('last_name',  '').strip()

        if len(first_name) < 3:
            messages.error(request, "First name must be at least 3 characters long.")
            return redirect('deo:add_student')
        if len(last_name) < 1:
            messages.error(request, "Last name must be at least 1 character long.")
            return redirect('deo:add_student')
            
        if User.objects.filter(username=username).exists():
            messages.error(request, f"Student Roll Number '{username}' already exists.")
            return redirect('deo:add_student')
            
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
            branch=branch,
            year_id=p.get('year'),
            section_id=p.get('section'),
            class_teacher_id=p.get('class_teacher') or None,
            counsellor_id=p.get('counsellor') or None,
            admission_year=p.get('admission_year', 2024),
            parent_name=p.get('parent_name', '').strip() or None,
            parent_mobile=p.get('parent_mobile', '').strip() or None,
        )
        messages.success(request, f"Student {username} created successfully.")
        return redirect('deo:manage_students')
        
    return render(request, 'deo/add_student.html', {
        'years': years,
        'sections': sections,
        'faculties': faculties,
    })

@deo_required
def edit_student(request, pk):
    branch = request.branch
    student = get_object_or_404(Student, pk=pk, branch=branch)
    years = Year.objects.all()
    sections = Section.objects.filter(branch=branch).select_related('year')
    faculties = Faculty.objects.filter(department=branch, is_active=True).select_related('user')
    
    if request.method == 'POST':
        p = request.POST
        first_name = p.get('first_name', '').strip()
        last_name  = p.get('last_name',  '').strip()

        if len(first_name) < 3:
            messages.error(request, "First name must be at least 3 characters long.")
            return redirect('deo:edit_student', pk=pk)
        if len(last_name) < 1:
            messages.error(request, "Last name must be at least 1 character long.")
            return redirect('deo:edit_student', pk=pk)
            
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
        return redirect('deo:manage_students')
        
    return render(request, 'deo/edit_student.html', {
        'student': student,
        'years': years,
        'sections': sections,
        'faculties': faculties,
    })

# ─────────────────────────────────────────────
# ATTENDANCE (1-Day Scoped Editing Constraint)
# ─────────────────────────────────────────────
@deo_required
def attendance_list(request):
    branch = request.branch
    sections = Section.objects.filter(branch=branch)
    
    section_id = request.GET.get('section', '')
    date_str = request.GET.get('date', '')
    
    records = []
    selected_section = None
    selected_date = None
    allow_edit = False
    
    if section_id and date_str:
        try:
            selected_section = Section.objects.get(id=section_id, branch=branch)
            selected_date = timezone.datetime.strptime(date_str, '%Y-%m-%d').date()
            records = Attendance.objects.filter(
                student__section=selected_section,
                date=selected_date
            ).select_related('student__user', 'timetable_entry__subject')
            
            # Constraint: DEO can only edit if within 1 day (today or yesterday)
            today = timezone.localdate()
            delta = today - selected_date
            allow_edit = (delta.days <= 1)
            
        except Exception:
            pass
            
    return render(request, 'deo/attendance_list.html', {
        'sections': sections,
        'records': records,
        'selected_section_id': section_id,
        'selected_date': date_str,
        'allow_edit': allow_edit,
    })

@deo_required
def edit_attendance(request, pk):
    branch = request.branch
    record = get_object_or_404(Attendance, pk=pk, student__branch=branch)
    
    # 1-day validation check
    today = timezone.localdate()
    delta = today - record.date
    if delta.days > 1:
        messages.error(request, "DEO cannot modify attendance records older than 1 day. Contact HOD.")
        return redirect(f"/deo/attendance/?section={record.student.section.id}&date={record.date.strftime('%Y-%m-%d')}")
        
    if request.method == 'POST':
        status = request.POST.get('status')
        if status in ['P', 'A']:
            record.status = status
            record.save()
            messages.success(request, f"Attendance updated to {record.get_status_display()}.")
            return redirect(f"/deo/attendance/?section={record.student.section.id}&date={record.date.strftime('%Y-%m-%d')}")
            
    return render(request, 'deo/edit_attendance.html', {'record': record})

# ─────────────────────────────────────────────
# RESULTS DATA ENTRY
# ─────────────────────────────────────────────
@deo_required
def upload_marks(request):
    import csv
    import io
    
    branch = request.branch
    subjects = Subject.objects.filter(branch=branch).select_related('year')
    exams = Exam.objects.filter(branch=branch).order_by('-date')
    
    selected_subject_id = request.GET.get('subject', '')
    selected_exam_id = request.GET.get('exam', '')
    selected_section_id = request.GET.get('section', '')
    
    selected_subject = None
    selected_exam = None
    selected_section = None
    sections = []
    students = []
    current_results = {}
    
    if selected_subject_id:
        selected_subject = get_object_or_404(Subject, id=selected_subject_id, branch=branch)
        sections = Section.objects.filter(branch=branch, year=selected_subject.year)
        
    if selected_exam_id:
        selected_exam = get_object_or_404(Exam, id=selected_exam_id, branch=branch)
        
    if selected_section_id and selected_subject and selected_exam:
        selected_section = get_object_or_404(Section, id=selected_section_id, branch=branch)
        students = Student.objects.filter(section=selected_section, is_active=True).select_related('user').order_by('roll_number')
        
        results_qs = Result.objects.filter(
            student__in=students,
            exam=selected_exam,
            subject=selected_subject
        )
        current_results = {r.student_id: r for r in results_qs}
        
    if request.method == 'POST':
        subj_id = request.POST.get('subject')
        ex_id = request.POST.get('exam')
        sec_id = request.POST.get('section')
        
        subj = get_object_or_404(Subject, id=subj_id, branch=branch)
        ex = get_object_or_404(Exam, id=ex_id, branch=branch)
        sec = get_object_or_404(Section, id=sec_id, branch=branch)
        sec_students = Student.objects.filter(section=sec, is_active=True)
        
        action = request.POST.get('action')
        
        if action == 'csv':
            if 'csv_file' not in request.FILES:
                messages.error(request, "Please upload a CSV file.")
                return redirect(f"{request.path}?subject={subj_id}&exam={ex_id}&section={sec_id}")
                
            csv_file = request.FILES['csv_file']
            if not csv_file.name.endswith('.csv'):
                messages.error(request, "Please upload a valid .csv file.")
                return redirect(f"{request.path}?subject={subj_id}&exam={ex_id}&section={sec_id}")
                
            try:
                data_set = csv_file.read().decode('utf-8-sig')
                io_string = io.StringIO(data_set)
                next(io_string, None)
                
                reader = csv.reader(io_string, delimiter=',', quotechar='"')
                success_count = 0
                errors = []
                
                with transaction.atomic():
                    for row_idx, row in enumerate(reader, start=2):
                        if not row or not row[0].strip():
                            continue
                        if len(row) < 2:
                            errors.append(f"Row {row_idx}: Missing columns.")
                            continue
                            
                        roll = row[0].strip().upper()
                        marks_str = row[1].strip()
                        max_str = row[2].strip() if len(row) > 2 and row[2].strip() else '100'
                        
                        try:
                            marks_obt = float(marks_str)
                            max_mks = float(max_str)
                        except ValueError:
                            errors.append(f"Row {row_idx}: Invalid marks format for {roll}.")
                            continue
                            
                        try:
                            student = sec_students.get(roll_number=roll)
                            Result.objects.update_or_create(
                                student=student,
                                exam=ex,
                                subject=subj,
                                defaults={
                                    'marks_obtained': marks_obt,
                                    'max_marks': max_mks,
                                    'grade': ''
                                }
                            )
                            success_count += 1
                        except Student.DoesNotExist:
                            errors.append(f"Row {row_idx}: Student {roll} not found in this section.")
                            
                if errors:
                    for err in errors[:5]:
                        messages.error(request, err)
                if success_count > 0:
                    messages.success(request, f"Successfully uploaded marks for {success_count} students.")
                    
            except Exception as e:
                messages.error(request, f"Error processing CSV: {e}")
                
        elif action == 'manual':
            try:
                success_count = 0
                max_marks_default = float(request.POST.get('max_marks_default', '100'))
                
                with transaction.atomic():
                    for stu in sec_students:
                        marks_input = request.POST.get(f"marks_{stu.id}", '').strip()
                        if marks_input == '':
                            continue
                            
                        try:
                            marks_obt = float(marks_input)
                        except ValueError:
                            messages.error(request, f"Invalid marks for student {stu.roll_number}.")
                            return redirect(f"{request.path}?subject={subj_id}&exam={ex_id}&section={sec_id}")
                            
                        Result.objects.update_or_create(
                            student=stu,
                            exam=ex,
                            subject=subj,
                            defaults={
                                'marks_obtained': marks_obt,
                                'max_marks': max_marks_default,
                                'grade': ''
                            }
                        )
                        success_count += 1
                        
                messages.success(request, f"Successfully saved marks for {success_count} students.")
            except Exception as e:
                messages.error(request, f"Error saving marks: {e}")
                
        return redirect(f"{request.path}?subject={subj_id}&exam={ex_id}&section={sec_id}")
        
    context = {
        'subjects':            subjects,
        'exams':               exams,
        'selected_subject_id': selected_subject_id,
        'selected_exam_id':    selected_exam_id,
        'selected_section_id': selected_section_id,
        'selected_subject':    selected_subject,
        'selected_exam':       selected_exam,
        'selected_section':    selected_section,
        'sections':            sections,
        'students':            students,
        'current_results':     current_results,
    }
    return render(request, 'deo/upload_marks.html', context)
