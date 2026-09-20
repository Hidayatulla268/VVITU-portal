import re
import logging
from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages
from django.core.cache import cache
from django.http import HttpResponse, HttpResponseForbidden

logger = logging.getLogger('vvitu.security')

PUBLIC_PREFIXES = [
    '/accounts/login',
    '/accounts/logout',
    '/accounts/set-password',
    '/admin/',
    '/static/',
    '/media/',
    '/notifications/',          # accessible to all authenticated roles
    '/chat/',                   # accessible to all authenticated roles
    '/academic-calendar/',      # accessible to all authenticated roles
    '/student/academic-calendar/', # accessible to all authenticated roles
    '/overview/',               # Public Interactive Showcase & Architecture Tour
    '/features/',               # Public Features & ERP Comparison
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
# 1. SECURITY PAYLOAD SANITIZER (WAF & TELEMETRY)
# ─────────────────────────────────────────────
# Unambiguous high-risk exploit signatures (block immediately)
HIGH_RISK_PATTERNS = [
    # Path Traversal & LFI Patterns
    re.compile(r"(\.\./\.\./|\.\.\\\.\.\\|/etc/passwd|c:\\windows\\system32)", re.IGNORECASE),
    # Raw HTML script tag injection
    re.compile(r"(<script\b[^>]*>|<iframe\b|<svg\b[^>]*onload)", re.IGNORECASE),
]

# Suspicious signatures for telemetry & audit logging (do not block legitimate academic text)
TELEMETRY_PATTERNS = [
    re.compile(r"(\b(UNION\s+ALL\s+SELECT|UNION\s+SELECT|SELECT\s+.*\s+FROM\s+INFORMATION_SCHEMA)\b)", re.IGNORECASE),
    re.compile(r"(\'\s*OR\s*\'1\'\s*=\s*\'1|\"\s*OR\s*\"1\"\s*=\s*\"1)", re.IGNORECASE),
    re.compile(r"(\;\s*DROP\s+TABLE|\;\s*DELETE\s+FROM)", re.IGNORECASE),
]

class SecuritySanitizerMiddleware:
    """
    Global Web Application Firewall (WAF) & Telemetry Middleware.
    Inspects GET, POST, and PATH parameters for malicious payloads.
    Blocks unambiguous attacks (path traversal, script tags) and logs telemetry for suspicious patterns.
    Real security is guaranteed by parameterized ORM queries, CSRF, and template auto-escaping.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path_info
        if path.startswith('/static/') or path.startswith('/media/'):
            return self.get_response(request)

        # Inspect path, query params and POST data
        inputs_to_check = [path]
        for _, v in request.GET.items():
            inputs_to_check.append(str(v))
        for k, v in request.POST.items():
            # Skip checking csrf token or password fields
            if k in ['csrfmiddlewaretoken', 'password', 'old_password', 'new_password', 'confirm_password']:
                continue
            inputs_to_check.append(str(v))

        for val in inputs_to_check:
            for pattern in HIGH_RISK_PATTERNS:
                if pattern.search(val):
                    logger.warning("Blocked malicious payload at %s: pattern '%s'", path, pattern.pattern)
                    return self._forbidden_response()

            for pattern in TELEMETRY_PATTERNS:
                if pattern.search(val):
                    logger.info("Security telemetry: suspicious pattern in %s: %s", path, val[:80])

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
        if request.user.is_authenticated and getattr(request.user, 'role', None) == 'student':
            try:
                profile = getattr(request.user, 'student_profile', None)
                if profile and profile.is_first_login:
                    if not path.startswith('/accounts/set-password') and not path.startswith('/accounts/logout'):
                        return redirect('accounts:set_password')
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Student profile redirect check failed: {e}")

        if path == '/':
            if request.user.is_authenticated:
                dash_url = self._dashboard_url(request.user)
                if dash_url and dash_url != '/':
                    return redirect(dash_url)
            return redirect('accounts:login')

        if request.user.is_authenticated:
            for prefix, allowed_roles in ROLE_URL_MAP.items():
                if path.startswith(prefix):
                    if request.user.role not in allowed_roles:
                        messages.warning(request, "You are not authorised to access that section.")
                        dash_url = self._dashboard_url(request.user)
                        if dash_url and dash_url.rstrip('/') != path.rstrip('/'):
                            return redirect(dash_url)
                        return redirect('accounts:login')

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
    - Limits rapid requests by Client IP (max 10 attempts per 60 seconds).
    - Limits failed authentication attempts by Target Username (max 5 failed attempts per 120 seconds).
    - Resets failed username counter upon successful login to prevent DoS lockouts.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path_info
        
        if request.method == "POST" and path == "/accounts/login/":
            ip = self._get_client_ip(request)
            username = request.POST.get('username', '').strip().lower()
            
            ip_key = f"login_ip_attempts_{ip}"
            user_key = f"login_failed_user_{username}" if username else None
            
            ip_attempts = cache.get(ip_key, 0)
            user_attempts = cache.get(user_key, 0) if user_key else 0
            
            if ip_attempts >= 10:
                return self._lockout_response("IP Address", "1 minute")
                
            if user_attempts >= 5:
                return self._lockout_response(f"username '{username}'", "2 minutes")
                
            # Count request attempt against IP rate limit
            try:
                if not cache.add(ip_key, 1, timeout=60):
                    cache.incr(ip_key)
            except Exception:
                cache.set(ip_key, ip_attempts + 1, timeout=60)

            # Process login request through Django auth pipeline
            response = self.get_response(request)

            # Only increment failed username counter when authentication actually fails (HTTP 200 re-render)
            # When authentication succeeds (HTTP 302/301 redirect), reset any failed attempt count
            if user_key:
                if response.status_code in [301, 302]:
                    cache.delete(user_key)
                elif response.status_code == 200:
                    try:
                        if not cache.add(user_key, 1, timeout=120):
                            cache.incr(user_key)
                    except Exception:
                        cache.set(user_key, user_attempts + 1, timeout=120)

            return response
                
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
        from django.conf import settings
        if getattr(settings, 'USE_X_FORWARDED_FOR', False):
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                parts = [p.strip() for p in x_forwarded_for.split(',') if p.strip()]
                if parts:
                    ip = parts[0]
                    import re
                    if re.match(r'^[0-9a-fA-F:.]+$', ip):
                        return ip
        return request.META.get('REMOTE_ADDR') or '127.0.0.1'


# ─────────────────────────────────────────────
# 5. GLOBAL UNHANDLED EXCEPTION AUTO-REDIRECT MIDDLEWARE
# ─────────────────────────────────────────────
class GlobalExceptionRedirectMiddleware:
    """
    Catches any unhandled view exceptions during request processing.
    Instead of showing a 500 error page or raw stack trace, it logs the exception,
    notifies the user, and automatically redirects them to their main dashboard.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        from django.http import Http404
        from django.core.exceptions import PermissionDenied

        # Allow standard 404 and 403 handlers to process normal not-found and permission errors
        if isinstance(exception, (Http404, PermissionDenied)):
            return None

        import logging
        logging.getLogger('django.request').error(f"Unhandled exception on {request.path_info}: {exception}", exc_info=True)
        
        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.path_info.startswith('/chat/'):
            return None  # Allow standard JSON 500 response for AJAX/API endpoints

        try:
            messages.error(request, "An unexpected error occurred. You have been automatically redirected to your dashboard.")
        except Exception:
            pass
        
        if hasattr(request, 'user') and request.user.is_authenticated:
            try:
                dashboard_url = request.user.get_dashboard_url()
                # AVOID REDIRECT LOOP: If already on dashboard_url or login, let standard 500 handler render!
                if request.path_info.rstrip('/') == dashboard_url.rstrip('/') or request.path_info.startswith('/accounts/login'):
                    return None
                return redirect(dashboard_url)
            except Exception:
                return None
        return None

