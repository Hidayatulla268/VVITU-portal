from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages

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
}

ROLE_DASHBOARDS = {
    'student':        'student:dashboard',
    'faculty':        'faculty:dashboard',
    'hod':            'faculty:dashboard',
    'lab_technician': 'faculty:dashboard',
    'admin':          'admin_dashboard:dashboard',
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
