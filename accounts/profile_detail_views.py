from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist
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
    can_view = False

    if user.role in ['admin', 'hod', 'deo']:
        can_view = True
    elif user.role in ['faculty', 'lab_technician']:
        try:
            faculty_profile = user.faculty_profile
            is_counsellor = (student.counsellor == faculty_profile)
            is_class_teacher = (student.class_teacher == faculty_profile)
            is_subject_teacher = student.section and Timetable.objects.filter(section=student.section, faculty=faculty_profile).exists()
            if is_counsellor or is_class_teacher or is_subject_teacher:
                can_view = True
        except (ObjectDoesNotExist, AttributeError):
            can_view = False
    elif user.role == 'student':
        try:
            if user.student_profile.pk == student.pk:
                can_view = True
        except (ObjectDoesNotExist, AttributeError):
            can_view = False

    if not can_view:
        messages.error(request, "You are not authorized to view this student profile.")
        return redirect(user.get_dashboard_url())

    # If user is a DEO, check if the student belongs to their assigned branch
    if user.role == 'deo':
        try:
            deo_profile = user.deo_profile
            if deo_profile.branch != student.branch:
                messages.error(request, "You are not authorized to view students outside your assigned branch.")
                return redirect(user.get_dashboard_url())
        except (ObjectDoesNotExist, AttributeError):
            messages.error(request, "DEO Profile not found. Access denied.")
            return redirect('accounts:login')

    # If user is an HOD, check if the student belongs to their branch
    if user.role == 'hod':
        try:
            hod_profile = user.faculty_profile
            if hod_profile.department != student.branch:
                messages.error(request, "You can only view student profiles within your department.")
                return redirect(user.get_dashboard_url())
        except (ObjectDoesNotExist, AttributeError):
            messages.error(request, "HOD Faculty Profile not found.")
            return redirect('accounts:login')

    # 1. Fetch Achievements
    achievements = Achievement.objects.filter(user=student.user)

    # 2. Fetch Attendance stats
    records = Attendance.objects.filter(student=student).select_related('timetable_entry__subject')
    total_classes = records.count()
    present_classes = records.filter(status='P').count()
    overall_percentage = round((present_classes / total_classes * 100), 1) if total_classes > 0 else 0

    context = {
        'student': student,
        'achievements': achievements,
        'overall_percentage': overall_percentage,
        'total_classes': total_classes,
        'present_classes': present_classes,
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
            except (ObjectDoesNotExist, AttributeError):
                is_owner = False
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
        except (ObjectDoesNotExist, AttributeError):
            return redirect('accounts:login')

    # If user is an HOD, they can only view faculty within their department
    if user.role == 'hod':
        try:
            hod_profile = user.faculty_profile
            if hod_profile.department != faculty.department:
                messages.error(request, "You can only view faculty in your department.")
                return redirect(user.get_dashboard_url())
        except (ObjectDoesNotExist, AttributeError):
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
