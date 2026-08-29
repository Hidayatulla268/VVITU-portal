"""
VVITU Portal — Custom Error Handlers with Auto-Dashboard Redirection

When HTTP 404, 500, 403, or 400 errors occur, instead of displaying cold static error pages,
these handlers automatically redirect authenticated users to their role-specific main dashboard.
"""

from django.shortcuts import redirect, render
from django.urls import reverse
from django.contrib import messages
from django.http import JsonResponse, HttpResponseRedirect


def _get_target_dashboard(request):
    """Determine the user's role-specific main dashboard URL or fallback to login."""
    if hasattr(request, 'user') and request.user.is_authenticated:
        try:
            return request.user.get_dashboard_url()
        except Exception:
            return reverse('accounts:login')
    return reverse('accounts:login')


def _safe_add_message(request, msg_type, text):
    """Safely append a toast message if message middleware is active."""
    try:
        getattr(messages, msg_type)(request, text)
    except Exception:
        pass


def custom_404_view(request, exception=None):
    """Handle 404 Page Not Found with automatic dashboard redirect."""
    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.path.startswith('/chat/'):
        return JsonResponse({'error': 'Resource not found', 'status': 404}, status=404)
    
    target_url = _get_target_dashboard(request)
    _safe_add_message(request, 'info', "The requested page was not found. Redirecting to your main dashboard...")
    
    return render(request, 'core/auto_redirect_error.html', {
        'error_title': '404 — Page Not Found',
        'error_message': 'The page or resource you are looking for does not exist or has been moved.',
        'dashboard_url': target_url,
    }, status=404)


def custom_500_view(request):
    """Handle 500 Server Error with automatic dashboard redirect."""
    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.path.startswith('/chat/'):
        return JsonResponse({'error': 'An internal server error occurred', 'status': 500}, status=500)
    
    target_url = _get_target_dashboard(request)
    _safe_add_message(request, 'error', "An unexpected server error occurred. Redirecting to your main dashboard...")
    
    return render(request, 'core/auto_redirect_error.html', {
        'error_title': '500 — Server Exception Neutralized',
        'error_message': 'An unexpected system error occurred. You are being safely redirected to your main dashboard.',
        'dashboard_url': target_url,
    }, status=500)


def custom_403_view(request, exception=None):
    """Handle 403 Permission Denied with automatic dashboard redirect."""
    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.path.startswith('/chat/'):
        return JsonResponse({'error': 'Permission denied', 'status': 403}, status=403)
    
    target_url = _get_target_dashboard(request)
    _safe_add_message(request, 'warning', "You are not authorized to access that resource. Redirecting to your main dashboard...")
    
    return render(request, 'core/auto_redirect_error.html', {
        'error_title': '403 — Access Restricted',
        'error_message': 'You do not have administrative permission to view this section.',
        'dashboard_url': target_url,
    }, status=403)


def custom_400_view(request, exception=None):
    """Handle 400 Bad Request with automatic dashboard redirect."""
    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.path.startswith('/chat/'):
        return JsonResponse({'error': 'Bad request', 'status': 400}, status=400)
    
    target_url = _get_target_dashboard(request)
    _safe_add_message(request, 'warning', "Invalid request. Redirecting to your main dashboard...")
    
    return render(request, 'core/auto_redirect_error.html', {
        'error_title': '400 — Invalid Request',
        'error_message': 'The request parameters were invalid or malformed.',
        'dashboard_url': target_url,
    }, status=400)
