"""
VVITU Portal — Notification Centre Views

Endpoints:
  GET  /notifications/             → full notification centre page
  GET  /notifications/api/         → JSON list of notifications for current user
  POST /notifications/mark-read/   → mark one notification as read (AJAX)
  POST /notifications/mark-all/    → mark all as read (AJAX)
  GET  /notifications/count/       → JSON unread count (for polling)

Staff and Admin views:
  GET  /notifications/manage/      → list sent notifications (Admin sees all, HOD/DEO see theirs)
  GET/POST /notifications/create/  → Admin/HOD/DEO creates a notification (mail)
  GET/POST /notifications/edit/<id>/ → edit sent notification
  POST /notifications/delete/<id>/ → delete sent notification
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

from core.models import Notification, NotificationRead, Branch, Section
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

    user_role = getattr(user, 'role', '')
    
    # Get user branch and section
    user_branch = None
    user_section = None
    if user_role == 'student':
        try:
            user_branch = user.student_profile.branch
            user_section = user.student_profile.section
        except Exception:
            pass
    elif user_role in ['faculty', 'hod', 'lab_technician']:
        try:
            user_branch = user.faculty_profile.department
        except Exception:
            pass
    elif user_role == 'deo':
        try:
            user_branch = user.deo_profile.branch
        except Exception:
            pass

    # Precise Targeting Query:
    # 1. Sent to everyone (target_all=True)
    # 2. Sent to this specific user (target_user=user)
    # 3. Sent to a group matching user's branch/section/role
    combination_q = Q(target_all=False, target_user__isnull=True)
    
    if user_branch:
        combination_q &= (Q(target_branch__isnull=True) | Q(target_branch=user_branch))
    else:
        combination_q &= Q(target_branch__isnull=True)
        
    if user_section:
        combination_q &= (Q(target_section__isnull=True) | Q(target_section=user_section))
    else:
        combination_q &= Q(target_section__isnull=True)
        
    if user_role:
        combination_q &= (Q(target_role='') | Q(target_role=user_role))
    else:
        combination_q &= Q(target_role='')

    target_q = Q(target_all=True) | Q(target_user=user) | combination_q

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
# Management: Sent Notices List
# ─────────────────────────────────────────────
@login_required
def manage_notices(request):
    if request.user.role not in ['admin', 'hod', 'deo']:
        messages.error(request, 'Access denied.')
        return redirect('accounts:redirect')

    user = request.user
    if user.role == 'admin':
        notices = Notification.objects.all().select_related('created_by', 'target_branch', 'target_section').order_by('-created_at')
    else:
        branch = None
        if user.role == 'hod':
            try:
                branch = user.faculty_profile.department
            except Exception:
                pass
        elif user.role == 'deo':
            try:
                branch = user.deo_profile.branch
            except Exception:
                pass

        notices = Notification.objects.filter(
            Q(created_by=user) | Q(target_branch=branch)
        ).select_related('created_by', 'target_branch', 'target_section').order_by('-created_at')

    return render(request, 'core/manage_notifications.html', {
        'notices': notices,
        'page_title': 'Sent Notices / Mails',
    })


# ─────────────────────────────────────────────
# Staff/Admin: Create / Send Notification
# ─────────────────────────────────────────────
@login_required
def create_notification(request):
    if request.user.role not in ['admin', 'hod', 'deo']:
        messages.error(request, 'Access denied.')
        return redirect('accounts:redirect')

    user = request.user
    branches = Branch.objects.all()
    users    = User.objects.filter(is_active=True).order_by('username')
    sections = []

    # Scoped branch details for HOD and DEO
    branch = None
    if user.role == 'hod':
        try:
            branch = user.faculty_profile.department
        except Exception:
            pass
    elif user.role == 'deo':
        try:
            branch = user.deo_profile.branch
        except Exception:
            pass

    if branch:
        sections = Section.objects.filter(branch=branch).select_related('year')

    if request.method == 'POST':
        title      = request.POST.get('title', '').strip()
        message    = request.POST.get('message', '').strip()
        notif_type = request.POST.get('notif_type', Notification.TYPE_ANNOUNCEMENT)
        priority   = request.POST.get('priority', Notification.PRIORITY_NORMAL)
        link       = request.POST.get('link', '').strip()
        target     = request.POST.get('target', 'all')
        
        branch_id  = request.POST.get('branch_id', '')
        section_id = request.POST.get('section_id', '')
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
                created_by = user,
            )

            # Apply targeting
            if user.role == 'admin':
                if target == 'all':
                    n.target_all  = True
                elif target == 'hod':
                    n.target_role = 'hod'
                elif target == 'deo':
                    n.target_role = 'deo'
                elif target == 'faculty':
                    n.target_role = 'faculty'
                elif target == 'student':
                    n.target_role = 'student'
                elif target == 'branch' and branch_id:
                    n.target_branch = Branch.objects.filter(id=branch_id).first()
                elif target == 'user' and user_id:
                    n.target_user = User.objects.filter(id=user_id).first()
            else:
                # HOD or DEO
                n.target_all = False
                n.target_branch = branch
                if target == 'branch':
                    pass
                elif target == 'faculty':
                    n.target_role = 'faculty'
                elif target == 'student':
                    n.target_role = 'student'
                elif target == 'class' and section_id:
                    n.target_role = 'student'
                    n.target_section = Section.objects.filter(id=section_id, branch=branch).first()

            if expires_str:
                expires = parse_datetime(expires_str)
                if expires:
                    if timezone.is_naive(expires):
                        expires = timezone.make_aware(expires)
                    n.expires_at = expires

            n.save()
            messages.success(request, f'Notice "{title}" sent successfully!')
            return redirect('notifications:manage')

    return render(request, 'core/create_notification.html', {
        'branches':         branches,
        'users':            users,
        'sections':         sections,
        'branch':           branch,
        'notif_types':      Notification.NOTIF_TYPES,
        'priority_choices': Notification.PRIORITY_CHOICES,
        'page_title':       'Send Notice',
    })


# ─────────────────────────────────────────────
# Staff/Admin: Edit Sent Notification
# ─────────────────────────────────────────────
@login_required
def edit_notification(request, pk):
    if request.user.role not in ['admin', 'hod', 'deo']:
        messages.error(request, 'Access denied.')
        return redirect('accounts:redirect')

    user = request.user
    n = get_object_or_404(Notification, pk=pk)

    # Check permission
    if user.role != 'admin' and n.created_by != user:
        messages.error(request, 'You are not authorized to edit this notice.')
        return redirect('notifications:manage')

    branches = Branch.objects.all()
    users    = User.objects.filter(is_active=True).order_by('username')
    sections = []

    # Scoped branch details for HOD and DEO
    branch = None
    if user.role == 'hod':
        try:
            branch = user.faculty_profile.department
        except Exception:
            pass
    elif user.role == 'deo':
        try:
            branch = user.deo_profile.branch
        except Exception:
            pass

    if branch:
        sections = Section.objects.filter(branch=branch).select_related('year')

    # Determine current target type
    current_target = 'all'
    if n.target_user:
        current_target = 'user'
    elif n.target_section:
        current_target = 'class'
    elif n.target_branch:
        if n.target_role == 'faculty':
            current_target = 'faculty'
        elif n.target_role == 'student':
            current_target = 'student'
        else:
            current_target = 'branch'
    elif n.target_role:
        current_target = n.target_role

    if request.method == 'POST':
        title      = request.POST.get('title', '').strip()
        message    = request.POST.get('message', '').strip()
        notif_type = request.POST.get('notif_type', n.notif_type)
        priority   = request.POST.get('priority', n.priority)
        link       = request.POST.get('link', '').strip()
        target     = request.POST.get('target', 'all')
        
        branch_id  = request.POST.get('branch_id', '')
        section_id = request.POST.get('section_id', '')
        user_id    = request.POST.get('user_id', '')
        expires_str = request.POST.get('expires_at', '').strip()

        if not title or not message:
            messages.error(request, 'Title and message are required.')
        else:
            n.title = title
            n.message = message
            n.notif_type = notif_type
            n.priority = priority
            n.link = link

            # Reset targeting before reapplying
            n.target_all = False
            n.target_role = ''
            n.target_branch = None
            n.target_section = None
            n.target_user = None

            if user.role == 'admin':
                if target == 'all':
                    n.target_all  = True
                elif target == 'hod':
                    n.target_role = 'hod'
                elif target == 'deo':
                    n.target_role = 'deo'
                elif target == 'faculty':
                    n.target_role = 'faculty'
                elif target == 'student':
                    n.target_role = 'student'
                elif target == 'branch' and branch_id:
                    n.target_branch = Branch.objects.filter(id=branch_id).first()
                elif target == 'user' and user_id:
                    n.target_user = User.objects.filter(id=user_id).first()
            else:
                # HOD or DEO
                n.target_branch = branch
                if target == 'branch':
                    pass
                elif target == 'faculty':
                    n.target_role = 'faculty'
                elif target == 'student':
                    n.target_role = 'student'
                elif target == 'class' and section_id:
                    n.target_role = 'student'
                    n.target_section = Section.objects.filter(id=section_id, branch=branch).first()

            if expires_str:
                expires = parse_datetime(expires_str)
                if expires:
                    if timezone.is_naive(expires):
                        expires = timezone.make_aware(expires)
                    n.expires_at = expires
            else:
                n.expires_at = None

            n.save()
            messages.success(request, f'Notice "{title}" updated successfully!')
            return redirect('notifications:manage')

    return render(request, 'core/create_notification.html', {
        'notice':           n,
        'current_target':   current_target,
        'branches':         branches,
        'users':            users,
        'sections':         sections,
        'branch':           branch,
        'notif_types':      Notification.NOTIF_TYPES,
        'priority_choices': Notification.PRIORITY_CHOICES,
        'page_title':       'Edit Notice',
    })


# ─────────────────────────────────────────────
# Staff/Admin: Delete Sent Notification
# ─────────────────────────────────────────────
@login_required
@require_POST
def delete_notification(request, pk):
    if request.user.role not in ['admin', 'hod', 'deo']:
        messages.error(request, 'Access denied.')
        return redirect('accounts:redirect')

    n = get_object_or_404(Notification, pk=pk)
    if request.user.role != 'admin' and n.created_by != request.user:
        messages.error(request, 'You are not authorized to delete this notice.')
    else:
        n.delete()
        messages.success(request, 'Notice deleted successfully.')
    return redirect('notifications:manage')
