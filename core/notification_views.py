"""
VVITU Portal — Notification Centre Views

Endpoints:
  GET  /notifications/             → full notification centre page
  GET  /notifications/api/         → JSON list of notifications for current user
  POST /notifications/mark-read/   → mark one notification as read (AJAX)
  POST /notifications/mark-all/    → mark all as read (AJAX)
  GET  /notifications/count/       → JSON unread count (for polling)

Admin push:
  GET/POST /notifications/create/  → admin sends a new notification
"""

import json
from django.db import models
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from core.models import Notification, NotificationRead, Branch
from accounts.models import User


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────
def get_user_notifications(user, limit=None):
    """Return active, non-expired Notifications visible to this user, newest first."""
    now = timezone.now()
    qs = Notification.objects.filter(is_active=True).filter(
        Q(expires_at__isnull=True) | Q(expires_at__gt=now)
    )

    # Build targeting filter
    target_q = Q(target_all=True)

    if hasattr(user, 'role') and user.role:
        target_q |= Q(target_role=user.role, target_all=False)

    # Branch targeting for students/faculty
    user_branch = None
    if hasattr(user, 'student_profile'):
        try:
            user_branch = user.student_profile.branch
        except Exception:
            pass
    elif hasattr(user, 'faculty_profile'):
        try:
            user_branch = user.faculty_profile.department
        except Exception:
            pass

    if user_branch:
        target_q |= Q(target_branch=user_branch, target_all=False)

    target_q |= Q(target_user=user, target_all=False)

    qs = qs.filter(target_q).select_related('created_by').order_by('-created_at')

    if limit:
        qs = qs[:limit]
    return qs


def get_unread_ids(user, notifications):
    """Return set of notification IDs already read by this user."""
    if not notifications:
        return set()
    notif_ids = [n.id for n in notifications]
    return set(
        NotificationRead.objects.filter(
            user=user, notification_id__in=notif_ids
        ).values_list('notification_id', flat=True)
    )


# ─────────────────────────────────────────────
# Notification Centre Page
# ─────────────────────────────────────────────
@login_required
def notification_centre(request):
    """Full-page notification centre."""
    notifications = list(get_user_notifications(request.user))
    read_ids      = get_unread_ids(request.user, notifications)

    notif_data = []
    for n in notifications:
        notif_data.append({
            'obj':    n,
            'is_read': n.id in read_ids,
        })

    unread_count = sum(1 for d in notif_data if not d['is_read'])

    return render(request, 'core/notification_centre.html', {
        'notif_data':    notif_data,
        'unread_count':  unread_count,
        'page_title':    'Notification Centre',
    })


# ─────────────────────────────────────────────
# API: notification list (JSON for navbar dropdown)
# ─────────────────────────────────────────────
@login_required
def notifications_api(request):
    """Return latest 20 notifications as JSON for the navbar dropdown."""
    notifications = list(get_user_notifications(request.user, limit=20))
    read_ids      = get_unread_ids(request.user, notifications)

    data = []
    for n in notifications:
        data.append({
            'id':        n.id,
            'title':     n.title,
            'message':   n.message[:120] + ('…' if len(n.message) > 120 else ''),
            'type':      n.notif_type,
            'icon':      n.icon,
            'color':     n.color_class,
            'priority':  n.priority,
            'link':      n.link or '',
            'is_read':   n.id in read_ids,
            'created_at': n.created_at.strftime('%d %b %Y, %I:%M %p'),
        })

    unread_count = sum(1 for d in data if not d['is_read'])
    return JsonResponse({'notifications': data, 'unread_count': unread_count})


# ─────────────────────────────────────────────
# API: unread count (lightweight polling)
# ─────────────────────────────────────────────
@login_required
def notification_count(request):
    notifications = list(get_user_notifications(request.user, limit=50))
    read_ids      = get_unread_ids(request.user, notifications)
    unread = sum(1 for n in notifications if n.id not in read_ids)
    return JsonResponse({'unread_count': unread})


# ─────────────────────────────────────────────
# Mark one notification read
# ─────────────────────────────────────────────
@login_required
@require_POST
def mark_read(request):
    try:
        data  = json.loads(request.body)
        notif_id = int(data.get('id', 0))
        notif = get_object_or_404(Notification, id=notif_id)
        NotificationRead.objects.get_or_create(user=request.user, notification=notif)
        return JsonResponse({'status': 'ok'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


# ─────────────────────────────────────────────
# Mark all notifications read
# ─────────────────────────────────────────────
@login_required
@require_POST
def mark_all_read(request):
    notifications = list(get_user_notifications(request.user))
    read_ids      = get_unread_ids(request.user, notifications)
    to_create = [
        NotificationRead(user=request.user, notification=n)
        for n in notifications if n.id not in read_ids
    ]
    NotificationRead.objects.bulk_create(to_create, ignore_conflicts=True)
    return JsonResponse({'status': 'ok', 'marked': len(to_create)})


# ─────────────────────────────────────────────
# Admin: Create / Send Notification
# ─────────────────────────────────────────────
@login_required
def create_notification(request):
    if request.user.role != 'admin':
        messages.error(request, 'Access denied.')
        return redirect('accounts:redirect')

    branches = Branch.objects.all()
    users    = User.objects.filter(is_active=True).order_by('username')

    if request.method == 'POST':
        title      = request.POST.get('title', '').strip()
        message    = request.POST.get('message', '').strip()
        notif_type = request.POST.get('notif_type', Notification.TYPE_ANNOUNCEMENT)
        priority   = request.POST.get('priority', Notification.PRIORITY_NORMAL)
        link       = request.POST.get('link', '').strip()
        target     = request.POST.get('target', 'all')   # all / students / faculty / branch / user
        branch_id  = request.POST.get('branch_id', '')
        user_id    = request.POST.get('user_id', '')
        expires_str = request.POST.get('expires_at', '').strip()

        if not title or not message:
            messages.error(request, 'Title and message are required.')
        else:
            n = Notification(
                title      = title,
                message    = message,
                notif_type = notif_type,
                priority   = priority,
                link       = link,
                created_by = request.user,
            )

            if target == 'all':
                n.target_all  = True
            elif target == 'students':
                n.target_all  = False
                n.target_role = 'student'
            elif target == 'faculty':
                n.target_all  = False
                n.target_role = 'faculty'
            elif target == 'branch' and branch_id:
                n.target_all    = False
                n.target_branch = Branch.objects.filter(id=branch_id).first()
            elif target == 'user' and user_id:
                n.target_all  = False
                n.target_user = User.objects.filter(id=user_id).first()
            else:
                n.target_all = True

            if expires_str:
                expires = parse_datetime(expires_str)
                if expires:
                    n.expires_at = expires

            n.save()
            messages.success(request, f'Notification "{title}" sent successfully!')
            return redirect('notifications:centre')

    return render(request, 'core/create_notification.html', {
        'branches':         branches,
        'users':            users,
        'notif_types':      Notification.NOTIF_TYPES,
        'priority_choices': Notification.PRIORITY_CHOICES,
        'page_title':       'Send Notification',
    })
