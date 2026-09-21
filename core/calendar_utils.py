"""
VVITU Portal — Academic Calendar Utilities
Handles 1-day prior event reminders, stakeholder notification dispatch,
and branch-scoped audience resolution.
"""

import logging
import datetime
from django.utils import timezone
from django.conf import settings
from django.core.mail import send_mail
from django.db.models import Q

logger = logging.getLogger(__name__)


def get_event_audience(event):
    """
    Resolve the set of User records who should receive alerts for this event:
    - Admins: always receive alerts for all events.
    - If event.branch is None (University-Wide):
        Students (optionally filtered by year), Faculty, HODs, DEOs.
    - If event.branch is set:
        Students of that branch (and year if set), Faculty of that branch,
        HODs of that branch, DEOs of that branch.
    """
    from accounts.models import User

    # 1. Admins always receive alerts for all academic events
    admin_q = Q(role='admin') | Q(is_superuser=True)

    if event.branch is None:
        # University-Wide:
        # Students (respecting year if specified)
        if event.year:
            student_q = Q(role='student', student_profile__year=event.year, student_profile__is_active=True)
        else:
            student_q = Q(role='student', student_profile__is_active=True)

        # Faculty, HOD, and DEO
        staff_q = Q(role__in=['faculty', 'hod', 'deo'])

        audience_q = admin_q | student_q | staff_q
    else:
        # Branch-Specific:
        # Students in the specified branch (and year if specified)
        if event.year:
            student_q = Q(
                role='student',
                student_profile__branch=event.branch,
                student_profile__year=event.year,
                student_profile__is_active=True
            )
        else:
            student_q = Q(
                role='student',
                student_profile__branch=event.branch,
                student_profile__is_active=True
            )

        # Faculty in this branch/dept
        faculty_q = Q(
            role='faculty',
            faculty_profile__department=event.branch,
            faculty_profile__is_active=True
        )

        # HOD of this branch/dept
        hod_q = Q(
            role='hod',
            faculty_profile__department=event.branch
        )

        # DEO of this branch
        deo_q = Q(
            role='deo',
            deo_profile__branch=event.branch,
            deo_profile__is_active=True
        )

        audience_q = admin_q | student_q | faculty_q | hod_q | deo_q

    users = User.objects.filter(audience_q, is_active=True, is_deleted=False).distinct()
    return users


def build_event_email_html(event, recipient_count=0):
    """
    Construct a responsive, VVITU-branded HTML email template for 1-day event alerts.
    """
    scope_str = event.branch.name if event.branch else "All Branches / University-Wide"
    year_str = f"Year {event.year.year}" if event.year else "All Academic Years"
    type_display = event.get_event_type_display()
    formatted_date = event.date.strftime("%A, %d %B %Y")
    portal_url = getattr(settings, 'COLLEGE_WEBSITE', 'https://www.vvitu.ac.in')

    badge_color = "#dc2626"
    if event.event_type == 'holiday':
        badge_color = "#16a34a"
    elif event.event_type == 'exam':
        badge_color = "#ea580c"
    elif event.event_type == 'deadline':
        badge_color = "#b91c1c"
    elif event.event_type == 'event':
        badge_color = "#2563eb"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>VVITU Academic Alert</title>
</head>
<body style="margin: 0; padding: 0; background-color: #f1f5f9; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #1e293b;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: #f1f5f9; padding: 30px 15px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" style="max-width: 600px; background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 10px 25px rgba(0,0,0,0.08); border: 1px solid #e2e8f0;" cellspacing="0" cellpadding="0">
          
          <!-- Header Banner -->
          <tr>
            <td style="background: linear-gradient(135deg, #881337 0%, #b91c1c 100%); padding: 24px 30px; text-align: left;">
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
                <tr>
                  <td>
                    <div style="font-size: 12px; font-weight: 700; letter-spacing: 1.5px; text-transform: uppercase; color: #fecdd3; margin-bottom: 4px;">
                      Official Academic Alert
                    </div>
                    <div style="font-size: 20px; font-weight: 800; color: #ffffff; line-height: 1.2;">
                      VVIT University Portal
                    </div>
                    <div style="font-size: 12px; color: #ffe4e6; margin-top: 3px;">
                      Vasireddy Venkatadri International Technological University
                    </div>
                  </td>
                  <td align="right" style="vertical-align: middle;">
                    <span style="display: inline-block; background-color: rgba(255,255,255,0.2); color: #ffffff; padding: 6px 12px; border-radius: 20px; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px;">
                      Starts Tomorrow
                    </span>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Main Content -->
          <tr>
            <td style="padding: 30px;">
              <div style="display: inline-block; background-color: {badge_color}; color: #ffffff; padding: 4px 12px; border-radius: 6px; font-size: 11px; font-weight: 700; text-transform: uppercase; margin-bottom: 12px;">
                {type_display}
              </div>

              <h1 style="margin: 0 0 16px 0; font-size: 22px; font-weight: 700; color: #0f172a; line-height: 1.35;">
                {event.title}
              </h1>

              <div style="background-color: #f8fafc; border-left: 4px solid {badge_color}; border-radius: 0 8px 8px 0; padding: 16px 20px; margin-bottom: 24px;">
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="font-size: 14px; line-height: 1.6;">
                  <tr>
                    <td style="padding: 4px 0; color: #64748b; width: 120px; font-weight: 600;">Date:</td>
                    <td style="padding: 4px 0; color: #0f172a; font-weight: 700;">{formatted_date}</td>
                  </tr>
                  <tr>
                    <td style="padding: 4px 0; color: #64748b; font-weight: 600;">Target Branch:</td>
                    <td style="padding: 4px 0; color: #0f172a;">{scope_str}</td>
                  </tr>
                  <tr>
                    <td style="padding: 4px 0; color: #64748b; font-weight: 600;">Target Year:</td>
                    <td style="padding: 4px 0; color: #0f172a;">{year_str}</td>
                  </tr>
                </table>
              </div>

              {f'''<div style="margin-bottom: 24px;">
                <h3 style="margin: 0 0 8px 0; font-size: 14px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; color: #475569;">Event Information</h3>
                <p style="margin: 0; font-size: 14px; line-height: 1.65; color: #334155; white-space: pre-line;">
                  {event.description}
                </p>
              </div>''' if event.description else ''}

              <div style="text-align: center; margin: 30px 0 10px 0;">
                <a href="{portal_url}/calendar/" style="display: inline-block; background-color: #b91c1c; color: #ffffff; text-decoration: none; padding: 12px 28px; border-radius: 8px; font-size: 14px; font-weight: 700; box-shadow: 0 4px 12px rgba(185, 28, 28, 0.25);">
                  View in Academic Calendar &rarr;
                </a>
              </div>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="background-color: #f8fafc; border-top: 1px solid #e2e8f0; padding: 20px 30px; text-align: center; font-size: 12px; color: #64748b; line-height: 1.5;">
              <p style="margin: 0 0 6px 0;">
                This automated reminder is sent to Students, Faculty, HODs, DEOs, and Administrators associated with this academic milestone.
              </p>
              <p style="margin: 0; color: #94a3b8;">
                &copy; {event.date.year} VVITU, Nambur, Guntur District, AP. All rights reserved.
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""
    return html


def build_event_email_text(event):
    """
    Plain text version for email clients without HTML support.
    """
    scope_str = event.branch.name if event.branch else "All Branches / University-Wide"
    year_str = f"Year {event.year.year}" if event.year else "All Academic Years"
    formatted_date = event.date.strftime("%A, %d %B %Y")
    portal_url = getattr(settings, 'COLLEGE_WEBSITE', 'https://www.vvitu.ac.in')

    text = f"""[VVITU ACADEMIC ALERT — TOMORROW]
Event: {event.title}
Category: {event.get_event_type_display()}
Date: {formatted_date} (Starts Tomorrow)
Scope: {scope_str}
Year: {year_str}

Details:
{event.description or 'No additional details.'}

Please access the VVITU Portal to view your complete schedule:
{portal_url}/calendar/

---
Vasireddy Venkatadri International Technological University
Nambur, Guntur District, Andhra Pradesh
"""
    return text


def send_event_1day_reminders(target_date=None, force=False, dry_run=False):
    """
    Check for events occurring tomorrow (target_date = today + 1 day),
    and dispatch email and in-app notifications to all targeted stakeholders:
    Students, Faculty, HODs, DEOs, and Administrators.

    Parameters:
    - target_date: date object. Defaults to tomorrow (timezone.localdate() + 1 day).
    - force: bool. If True, re-send reminders even if reminder_sent is True.
    - dry_run: bool. If True, calculate and return targets without sending or mutating DB.

    Returns:
    - dict with summary of dispatched notifications and emails.
    """
    from core.models import AcademicCalendar, Notification

    if target_date is None:
        target_date = timezone.localdate() + datetime.timedelta(days=1)

    events_qs = AcademicCalendar.objects.filter(date=target_date)
    if not force:
        events_qs = events_qs.filter(reminder_sent=False)

    events = list(events_qs.select_related('branch', 'year'))

    summary = {
        'target_date': str(target_date),
        'events_found': len(events),
        'reminders_sent': 0,
        'details': []
    }

    if not events:
        logger.info(f"send_event_1day_reminders: No pending events found for {target_date}.")
        return summary

    for event in events:
        audience_users = get_event_audience(event)
        recipient_emails = list(
            audience_users.exclude(email__isnull=True).exclude(email='').values_list('email', flat=True).distinct()
        )
        total_audience_count = audience_users.count()
        emails_count = len(recipient_emails)

        detail = {
            'event_id': event.id,
            'title': event.title,
            'event_type': event.event_type,
            'branch': event.branch.code if event.branch else 'All',
            'audience_count': total_audience_count,
            'emails_count': emails_count,
            'notified': False,
            'emailed': False,
        }

        if dry_run:
            detail['dry_run'] = True
            summary['details'].append(detail)
            continue

        # 1. Create In-App Notification
        # Map event type to Notification type
        notif_type_map = {
            'exam': Notification.TYPE_EXAM,
            'holiday': Notification.TYPE_HOLIDAY,
            'event': Notification.TYPE_ANNOUNCEMENT,
            'deadline': Notification.TYPE_ANNOUNCEMENT,
            'other': Notification.TYPE_ANNOUNCEMENT,
        }
        notif_type = notif_type_map.get(event.event_type, Notification.TYPE_ANNOUNCEMENT)
        priority = Notification.PRIORITY_HIGH if event.event_type in ['exam', 'deadline'] else Notification.PRIORITY_NORMAL

        scope_desc = f"Branch: {event.branch.code}" if event.branch else "University-Wide"
        notif_message = (
            f"Event Starting Tomorrow ({event.date.strftime('%d-%b-%Y')}): {event.title}. "
            f"Category: {event.get_event_type_display()} | Scope: {scope_desc}."
        )
        if event.description:
            notif_message += f" {event.description}"

        try:
            Notification.objects.create(
                title=f"Tomorrow: {event.title}",
                message=notif_message,
                notif_type=notif_type,
                priority=priority,
                target_all=(event.branch is None),
                target_branch=event.branch,
                link='/calendar/',
                created_by=None,
            )
            detail['notified'] = True
        except Exception as e:
            logger.error(f"Failed to create notification for event {event.id}: {e}")

        # 2. Dispatch Emails
        if recipient_emails:
            subject = f"[VVITU Academic Alert] Tomorrow: {event.title} ({event.get_event_type_display()})"
            text_content = build_event_email_text(event)
            html_content = build_event_email_html(event, emails_count)
            from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'VVITU Portal <noreply@vvitu.ac.in>')

            # Send in batches of 50 to avoid SMTP connection limits
            batch_size = 50
            for i in range(0, len(recipient_emails), batch_size):
                batch = recipient_emails[i:i + batch_size]
                try:
                    send_mail(
                        subject=subject,
                        message=text_content,
                        from_email=from_email,
                        recipient_list=batch,
                        html_message=html_content,
                        fail_silently=True
                    )
                except Exception as e:
                    logger.error(f"Error sending email batch for event {event.id}: {e}")

            detail['emailed'] = True

        # 3. Mark Event as Reminded
        event.reminder_sent = True
        event.reminder_sent_at = timezone.now()
        event.save(update_fields=['reminder_sent', 'reminder_sent_at'])
        detail['reminder_marked'] = True

        summary['reminders_sent'] += 1
        summary['details'].append(detail)

    return summary
