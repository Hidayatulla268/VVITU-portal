from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages
from django.core.cache import cache
from django.http import HttpResponse

PUBLIC_PREFIXES = [
    '/accounts/login',
    '/accounts/logout',
    '/accounts/set-password',
    '/admin/',
    '/static/',
    '/media/',
]

ROLE_URL_MAP = {
    '/student/':     {'student'},
    '/faculty/':     {'faculty', 'hod', 'lab_technician'},
    '/admin-portal/':{'admin'},
    '/hod/':         {'hod'},
    '/deo/':         {'deo'},
}

ROLE_DASHBOARDS = {
    'student':        'student:dashboard',
    'faculty':        'faculty:dashboard',
    'hod':            'hod:dashboard',
    'lab_technician': 'faculty:dashboard',
    'admin':          'admin_dashboard:dashboard',
    'deo':            'deo:dashboard',
}

class RoleBasedAccessMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path_info

        for prefix in PUBLIC_PREFIXES:
            if path.startswith(prefix):
                return self.get_response(request)

        # Force student password setup on first login
        if request.user.is_authenticated and request.user.role == 'student':
            try:
                if request.user.student_profile.is_first_login:
                    return redirect('accounts:set_password')
            except Exception:
                pass

        if path == '/':
            if request.user.is_authenticated:
                return redirect(self._dashboard_url(request.user))
            return redirect('accounts:login')

        if request.user.is_authenticated:
            for prefix, allowed_roles in ROLE_URL_MAP.items():
                if path.startswith(prefix):
                    if request.user.role not in allowed_roles:
                        messages.warning(request, "You are not authorised to access that section.")
                        return redirect(self._dashboard_url(request.user))

        return self.get_response(request)


    @staticmethod
    def _dashboard_url(user):
        view_name = ROLE_DASHBOARDS.get(user.role, 'accounts:login')
        try:
            return reverse(view_name)
        except Exception:
            return reverse('accounts:login')


class LoginRateLimitMiddleware:
    """
    Prevents brute-force and credential stuffing attacks on the login page.
    - Limits requests by Client IP (max 5 attempts per 60 seconds).
    - Limits requests by Target Username (max 10 attempts per 120 seconds).
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path_info
        
        # Only rate limit login POST requests
        if request.method == "POST" and path == "/accounts/login/":
            ip = self._get_client_ip(request)
            username = request.POST.get('username', '').strip().lower()
            
            ip_key = f"login_attempts_{ip}"
            user_key = f"login_attempts_user_{username}" if username else None
            
            ip_attempts = cache.get(ip_key, 0)
            user_attempts = cache.get(user_key, 0) if user_key else 0
            
            # Check IP lockout (5 attempts / minute)
            if ip_attempts >= 5:
                return self._lockout_response("IP Address", "1 minute")
                
            # Check Username lockout (10 attempts / 2 minutes)
            if user_attempts >= 10:
                return self._lockout_response(f"username '{username}'", "2 minutes")
                
            # Increment attempts
            cache.set(ip_key, ip_attempts + 1, timeout=60)
            if user_key:
                cache.set(user_key, user_attempts + 1, timeout=120)
                
        return self.get_response(request)

    @staticmethod
    def _lockout_response(scope_type, duration):
        html = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <title>Too Many Requests</title>
            <style>
                body {{ background: #0a0a12; color: #f0f0f5; font-family: 'Inter', sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }}
                .card {{ background: rgba(255, 255, 255, 0.03); border: 1px solid rgba(255, 255, 255, 0.08); padding: 40px; border-radius: 16px; text-align: center; max-width: 420px; box-shadow: 0 24px 64px rgba(0,0,0,0.5); }}
                h1 {{ color: #dc2626; font-size: 1.8rem; margin-top: 0; }}
                p {{ color: #9ca3af; font-size: 0.95rem; line-height: 1.6; }}
                .timer {{ display: inline-block; margin-top: 20px; font-weight: bold; color: #dc2626; }}
            </style>
        </head>
        <body>
            <div class="card">
                <h1>⚠️ Login Locked</h1>
                <p>Too many login attempts targeting your {scope_type}. For your security, this action has been locked.</p>
                <span class="timer">Please try again in {duration}.</span>
            </div>
        </body>
        </html>
        """
        return HttpResponse(html, status=429)

    @staticmethod
    def _get_client_ip(request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


