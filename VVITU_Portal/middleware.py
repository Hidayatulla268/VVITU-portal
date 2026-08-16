import re
from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages
from django.core.cache import cache
from django.http import HttpResponse, HttpResponseForbidden

PUBLIC_PREFIXES = [
    '/accounts/login',
    '/accounts/logout',
    '/accounts/set-password',
    '/admin/',
    '/static/',
    '/media/',
    '/notifications/',  # accessible to all authenticated roles
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

# ─────────────────────────────────────────────
# 1. SECURITY PAYLOAD SANITIZER (WAF FIREWALL)
# ─────────────────────────────────────────────
MALICIOUS_PATTERNS = [
    # SQL Injection Patterns
    re.compile(r"(\b(UNION\s+ALL\s+SELECT|UNION\s+SELECT|SELECT\s+.*\s+FROM\s+INFORMATION_SCHEMA|INSERT\s+INTO|DELETE\s+FROM|DROP\s+TABLE|ALTER\s+TABLE|TRUNCATE\s+TABLE|EXEC\s*\(|SLEEP\s*\(\d+\)|BENCHMARK\s*\()\b)", re.IGNORECASE),
    re.compile(r"(\'\s*OR\s*\'1\'\s*=\s*\'1|\"\s*OR\s*\"1\"\s*=\s*\"1|;\s*DROP\s+TABLE|;\s*DELETE\s+FROM)", re.IGNORECASE),
    # Cross-Site Scripting (XSS) Patterns
    re.compile(r"(<script\b[^>]*>|javascript\s*:|onerror\s*=|onload\s*=|onclick\s*=|eval\s*\(|<iframe\b|<svg\b[^>]*onload)", re.IGNORECASE),
    # Path Traversal & LFI Patterns
    re.compile(r"(\.\./\.\./|\.\.\\\.\.\\|/etc/passwd|c:\\windows\\system32)", re.IGNORECASE),
    # Command Injection Patterns
    re.compile(r"(\;\s*ls\b|\;\s*cat\b|\|\s*cat\b|\$\(whoami\)|\`id\`)", re.IGNORECASE),
]

class SecuritySanitizerMiddleware:
    """
    Global Web Application Firewall (WAF) Middleware.
    Inspects GET, POST, and PATH parameters for malicious payloads (SQLi, XSS, Path Traversal, Command Injection).
    Rejects malicious requests with HTTP 403 Forbidden.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Inspect query params and POST data
        inputs_to_check = []
        for k, v in request.GET.items():
            inputs_to_check.append(str(v))
        for k, v in request.POST.items():
            # Skip checking csrf middleware token or password values for non-script content
            if k in ['csrfmiddlewaretoken', 'password', 'old_password', 'new_password', 'confirm_password']:
                continue
            inputs_to_check.append(str(v))

        inputs_to_check.append(request.path_info)

        for val in inputs_to_check:
            for pattern in MALICIOUS_PATTERNS:
                if pattern.search(val):
                    return self._forbidden_response()

        return self.get_response(request)

    @staticmethod
    def _forbidden_response():
        html = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <title>403 Security Violation — VVITU Portal</title>
            <style>
                body { background: #050508; color: #f0f0f5; font-family: 'Inter', sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }
                .card { background: rgba(18, 18, 28, 0.9); border: 1px solid rgba(239, 68, 68, 0.4); padding: 40px; border-radius: 16px; text-align: center; max-width: 480px; box-shadow: 0 24px 64px rgba(220,38,38,0.3); }
                h1 { color: #ef4444; font-size: 1.8rem; margin-top: 0; }
                p { color: #9ca3af; font-size: 0.95rem; line-height: 1.6; }
                .alert-badge { display: inline-block; margin-top: 15px; padding: 6px 16px; background: rgba(239,68,68,0.2); color: #ef4444; border-radius: 20px; font-weight: bold; font-size: 0.85rem; }
            </style>
        </head>
        <body>
            <div class="card">
                <h1>🛡️ Security Violation Blocked</h1>
                <p>Your request contained a prohibited input pattern or malicious payload signature. Access has been denied by the VVITU Security Firewall.</p>
                <span class="alert-badge">HTTP 403 Forbidden · Threat Neutralized</span>
            </div>
        </body>
        </html>
        """
        return HttpResponseForbidden(html)


# ─────────────────────────────────────────────
# 2. GLOBAL SECURITY HEADERS MIDDLEWARE
# ─────────────────────────────────────────────
class GlobalSecurityHeadersMiddleware:
    """
    Injects mandatory enterprise HTTP security headers into every server response.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response['X-Frame-Options'] = 'DENY'
        response['X-Content-Type-Options'] = 'nosniff'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=(), payment=(), usb=()'
        response['Cross-Origin-Opener-Policy'] = 'same-origin'
        return response


# ─────────────────────────────────────────────
# 3. ROLE BASED ACCESS CONTROL (RBAC) MIDDLEWARE
# ─────────────────────────────────────────────
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
                if getattr(request.user, 'student_profile', None) and request.user.student_profile.is_first_login:
                    return redirect('accounts:set_password')
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Student profile redirect check failed: {e}")

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


# ─────────────────────────────────────────────
# 4. BRUTE FORCE LOGIN RATE LIMITER
# ─────────────────────────────────────────────
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
        
        if request.method == "POST" and path == "/accounts/login/":
            ip = self._get_client_ip(request)
            username = request.POST.get('username', '').strip().lower()
            
            ip_key = f"login_attempts_{ip}"
            user_key = f"login_attempts_user_{username}" if username else None
            
            ip_attempts = cache.get(ip_key, 0)
            user_attempts = cache.get(user_key, 0) if user_key else 0
            
            if ip_attempts >= 5:
                return self._lockout_response("IP Address", "1 minute")
                
            if user_attempts >= 10:
                return self._lockout_response(f"username '{username}'", "2 minutes")
                
            # Atomic multi-worker cache increment
            try:
                if not cache.add(ip_key, 1, timeout=60):
                    cache.incr(ip_key)
            except Exception:
                cache.set(ip_key, ip_attempts + 1, timeout=60)

            if user_key:
                try:
                    if not cache.add(user_key, 1, timeout=120):
                        cache.incr(user_key)
                except Exception:
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
            parts = [p.strip() for p in x_forwarded_for.split(',') if p.strip()]
            if parts:
                ip = parts[0]
                import re
                if re.match(r'^[0-9a-fA-F:.]+$', ip):
                    return ip
        return request.META.get('REMOTE_ADDR') or '127.0.0.1'
