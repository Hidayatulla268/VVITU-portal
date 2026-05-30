"""
VVIT Portal — Accounts Views

Handles login, logout, and post-login role-based redirect.
"""

from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from .models import Student, Faculty


# ─────────────────────────────────────────────
# LOGIN
# ─────────────────────────────────────────────
@require_http_methods(["GET", "POST"])
def login_view(request):
    """
    Render the login form on GET; authenticate and redirect on POST.
    Supports the VVIT username format (e.g., 24BQ1A4942) or email.
    """
    if request.user.is_authenticated:
        return redirect(request.user.get_dashboard_url())

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, f"Welcome back, {user.get_full_name() or user.username}!")
            # Honour ?next= param if present, else go to role dashboard
            next_url = request.GET.get('next', user.get_dashboard_url())
            return redirect(next_url)
        else:
            messages.error(request, "Invalid username or password. Please try again.")

    return render(request, 'accounts/login.html')


# ─────────────────────────────────────────────
# LOGOUT
# ─────────────────────────────────────────────
def logout_view(request):
    """Log out and redirect to login page."""
    logout(request)
    messages.info(request, "You have been logged out successfully.")
    return redirect('accounts:login')


# ─────────────────────────────────────────────
# ROLE-BASED REDIRECT
# ─────────────────────────────────────────────
@login_required
def role_redirect(request):
    """
    Redirect authenticated users to their role-specific dashboard.
    Used as LOGIN_REDIRECT_URL in settings.
    """
    return redirect(request.user.get_dashboard_url())


# ─────────────────────────────────────────────
# FORCE SET PASSWORD FOR STUDENTS (FIRST LOGIN)
# ─────────────────────────────────────────────
@login_required
def set_password(request):
    """
    Force students on first login to set their permanent password.
    """
    # Check if the user is a student and has is_first_login set to True
    try:
        profile = request.user.student_profile
    except Exception:
        profile = None

    if request.user.role != 'student' or not profile or not profile.is_first_login:
        return redirect(request.user.get_dashboard_url())

    if request.method == 'POST':
        password = request.POST.get('password', '').strip()
        confirm_password = request.POST.get('confirm_password', '').strip()

        if not password:
            messages.error(request, "Password cannot be empty.")
        elif password != confirm_password:
            messages.error(request, "Passwords do not match.")
        elif len(password) < 6:
            messages.error(request, "Password must be at least 6 characters long.")
        else:
            # Set new password
            request.user.set_password(password)
            request.user.save()
            
            # Update student profile first login flag
            profile.is_first_login = False
            profile.save()
            
            # Since password changed, we must update the session auth hash to prevent logout
            from django.contrib.auth import update_session_auth_hash
            update_session_auth_hash(request, request.user)
            
            messages.success(request, "Your password has been set successfully! This is now your permanent password.")
            return redirect(request.user.get_dashboard_url())

    return render(request, 'accounts/set_password.html')


# ─────────────────────────────────────────────
# USER PROFILE VIEW
# ─────────────────────────────────────────────
@login_required
def profile_view(request):
    """
    Render personal profile details for Students, Faculty, and Admin.
    """
    user = request.user
    student = None
    faculty = None
    
    if user.role == 'student':
        try:
            student = user.student_profile
        except Student.DoesNotExist:
            pass
    elif user.role in ['faculty', 'hod', 'lab_technician']:
        try:
            faculty = user.faculty_profile
        except Faculty.DoesNotExist:
            pass
            
    context = {
        'user': user,
        'student': student,
        'faculty': faculty,
    }
    return render(request, 'accounts/profile.html', context)

