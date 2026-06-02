from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from accounts.models import User, Student, Faculty, Achievement
from core.models import Subject, Result, Attendance, Timetable
from django.db.models import Q
import datetime

@login_required
def student_detail_view(request, pk):
    """
    Detailed read-only student profile, accessible to Admins, HODs, DEOs,
    or the student themselves.
    """
    student = get_object_or_404(Student, pk=pk)
    
    # Access control check
    user = request.user
    if user.role not in ['admin', 'hod', 'deo']:
        # Only allow the student to view their own profile
        is_owner = False
        if user.role == 'student':
            try:
                is_owner = (user.student_profile.pk == student.pk)
            except Exception:
                pass
        if not is_owner:
            messages.error(request, "You are not authorized to view this profile.")
            return redirect(user.get_dashboard_url())

    # If user is a DEO, check if the student belongs to their assigned branch
    if user.role == 'deo':
        try:
            deo_profile = user.deo_profile
            if deo_profile.branch != student.branch:
                messages.error(request, "You are not authorized to view students outside your assigned branch.")
                return redirect(user.get_dashboard_url())
        except Exception:
            messages.error(request, "DEO Profile not found. Access denied.")
            return redirect('accounts:login')

    # If user is an HOD, check if the student belongs to their branch
    if user.role == 'hod':
        try:
            hod_profile = user.faculty_profile
            if hod_profile.department != student.branch:
                messages.error(request, "You can only view student profiles within your department.")
                return redirect(user.get_dashboard_url())
        except Exception:
            messages.error(request, "HOD Faculty Profile not found.")
            return redirect('accounts:login')

    # 1. Fetch Achievements
    achievements = Achievement.objects.filter(user=student.user)

    # 2. Fetch Attendance stats
    records = Attendance.objects.filter(student=student).select_related('timetable_entry__subject')
    att_stats = {}
    for rec in records:
        subj = rec.timetable_entry.subject
        key = subj.code
        if key not in att_stats:
            att_stats[key] = {'name': subj.name, 'code': key, 'total': 0, 'present': 0}
        att_stats[key]['total'] += 1
        if rec.status == 'P':
            att_stats[key]['present'] += 1
    
    overall_total = 0
    overall_present = 0
    for s in att_stats.values():
        t = s['total']
        s['percentage'] = round(s['present'] / t * 100, 1) if t else 0
        overall_total += s['total']
        overall_present += s['present']
    
    overall_percentage = round(overall_present / overall_total * 100, 1) if overall_total else 0.0

    # 3. Fetch Exam Results
    results_qs = Result.objects.filter(student=student).select_related('exam', 'subject').order_by('subject__name', '-exam__date')
    
    # Organize results by subject code
    subject_results = {}
    for res in results_qs:
        code = res.subject.code
        if code not in subject_results:
            subject_results[code] = {
                'subject': res.subject,
                'mid1': None,
                'mid2': None,
                'final': None,
            }
        
        exam_type = res.exam.exam_type
        if exam_type == 'mid1':
            subject_results[code]['mid1'] = res
        elif exam_type == 'mid2':
            subject_results[code]['mid2'] = res
        elif exam_type == 'final':
            subject_results[code]['final'] = res

    context = {
        'student': student,
        'achievements': achievements,
        'att_stats': att_stats.values(),
        'overall_total': overall_total,
        'overall_present': overall_present,
        'overall_percentage': overall_percentage,
        'subject_results': subject_results.values(),
    }
    return render(request, 'accounts/student_detail.html', context)


@login_required
def faculty_detail_view(request, pk):
    """
    Detailed read-only faculty profile, accessible to Admins, HODs, DEOs,
    or the faculty member themselves.
    """
    faculty = get_object_or_404(Faculty, pk=pk)
    
    # Access control check
    user = request.user
    if user.role not in ['admin', 'hod', 'deo']:
        is_owner = False
        if user.role in ['faculty', 'hod', 'lab_technician']:
            try:
                is_owner = (user.faculty_profile.pk == faculty.pk)
            except Exception:
                pass
        if not is_owner:
            messages.error(request, "You are not authorized to view this profile.")
            return redirect(user.get_dashboard_url())

    # If user is a DEO, they can see faculty details if they are in the same branch
    if user.role == 'deo':
        try:
            deo_profile = user.deo_profile
            if deo_profile.branch != faculty.department:
                messages.error(request, "You can only view faculty in your assigned branch.")
                return redirect(user.get_dashboard_url())
        except Exception:
            return redirect('accounts:login')

    # If user is an HOD, they can only view faculty within their department
    if user.role == 'hod':
        try:
            hod_profile = user.faculty_profile
            if hod_profile.department != faculty.department:
                messages.error(request, "You can only view faculty in your department.")
                return redirect(user.get_dashboard_url())
        except Exception:
            return redirect('accounts:login')

    # 1. Fetch Achievements
    achievements = Achievement.objects.filter(user=faculty.user)

    # 2. Fetch Subjects taught
    subjects = Subject.objects.filter(faculty=faculty).select_related('branch', 'year')

    # 3. Timetable details
    timetable_slots = Timetable.objects.filter(faculty=faculty).select_related('section', 'subject')

    context = {
        'faculty': faculty,
        'achievements': achievements,
        'subjects': subjects,
        'timetable_slots': timetable_slots,
    }
    return render(request, 'accounts/faculty_detail.html', context)
