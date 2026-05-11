"""
VVIT Portal — Accounts Views

Handles login, logout, and post-login role-based redirect.
"""

from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required


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
