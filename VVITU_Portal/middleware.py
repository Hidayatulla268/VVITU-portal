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
    Prevents brute-force / credential stuffing attacks on the login page.
    Limits POST requests to 5 per minute per IP address.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path_info
        
        # Only rate limit login POST requests
        if request.method == "POST" and path == "/accounts/login/":
            ip = self._get_client_ip(request)
            cache_key = f"login_attempts_{ip}"
            attempts = cache.get(cache_key, 0)
            
            # Allow max 5 attempts per minute
            if attempts >= 5:
                # Render a clean, stylized error page or simple message
                html = """
                <!DOCTYPE html>
                <html lang="en">
                <head>
                    <meta charset="UTF-8">
                    <title>Too Many Requests</title>
                    <style>
                        body { background: #0a0a12; color: #f0f0f5; font-family: 'Inter', sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }
                        .card { background: rgba(255, 255, 255, 0.03); border: 1px solid rgba(255, 255, 255, 0.08); padding: 40px; border-radius: 16px; text-align: center; max-width: 400px; box-shadow: 0 24px 64px rgba(0,0,0,0.5); }
                        h1 { color: #dc2626; font-size: 1.8rem; margin-top: 0; }
                        p { color: #9ca3af; font-size: 0.95rem; line-height: 1.6; }
                        .timer { display: inline-block; margin-top: 20px; font-weight: bold; color: #dc2626; }
                    </style>
                </head>
                <body>
                    <div class="card">
                        <h1>⚠️ Login Locked</h1>
                        <p>Too many login attempts from your IP address. For your security, this action has been locked for 60 seconds.</p>
                        <span class="timer">Please try again in 1 minute.</span>
                    </div>
                </body>
                </html>
                """
                return HttpResponse(html, status=429)
                
            cache.set(cache_key, attempts + 1, timeout=60)
            
        return self.get_response(request)

    @staticmethod
    def _get_client_ip(request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

