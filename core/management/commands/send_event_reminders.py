"""
VVITU Portal — Management Command: Send 1-Day Advance Academic Calendar Event Reminders
Dispatches automated email alerts and in-app notifications to Students, Faculty, HODs, DEOs,
and Administrators for events starting tomorrow (or on a specified date).
"""

import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from core.calendar_utils import send_event_1day_reminders


class Command(BaseCommand):
    help = 'Dispatches 1-day prior email and in-app notifications for upcoming Academic Calendar events.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--date',
            type=str,
            help='Target event date in YYYY-MM-DD format (defaults to tomorrow: today + 1 day)'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force re-sending reminders even if already marked as sent'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Calculate targets and log details without sending emails or modifying database'
        )

    def handle(self, *args, **options):
        date_str = options.get('date')
        force = options.get('force', False)
        dry_run = options.get('dry_run', False)

        if date_str:
            try:
                target_date = datetime.date.fromisoformat(date_str)
            except ValueError:
                self.stderr.write(self.style.ERROR(f"Invalid date format '{date_str}'. Expected YYYY-MM-DD."))
                return
        else:
            target_date = timezone.localdate() + datetime.timedelta(days=1)

        self.stdout.write(self.style.NOTICE(
            f"Checking Academic Calendar events for target date: {target_date} "
            f"(force={force}, dry_run={dry_run})..."
        ))

        summary = send_event_1day_reminders(target_date=target_date, force=force, dry_run=dry_run)

        events_found = summary['events_found']
        reminders_sent = summary['reminders_sent']

        if events_found == 0:
            self.stdout.write(self.style.WARNING(f"No pending events found for {target_date}."))
            return

        for d in summary['details']:
            status_tag = "[DRY-RUN]" if d.get('dry_run') else "[SENT]"
            self.stdout.write(self.style.SUCCESS(
                f"{status_tag} Event #{d['event_id']} '{d['title']}' | Branch: {d['branch']} | "
                f"Audience: {d['audience_count']} users ({d['emails_count']} with email) | "
                f"Notified: {d.get('notified', False)} | Emailed: {d.get('emailed', False)}"
            ))

        self.stdout.write(self.style.SUCCESS(
            f"Completed! Found {events_found} event(s), dispatched reminders for {reminders_sent} event(s)."
        ))
