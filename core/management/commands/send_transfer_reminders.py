"""
VVITU Portal — Management Command: Send 15-Minute Advance Proxy Class Reminders
Dispatches SMS & Email reminders to substitute faculty members 15 minutes before their proxy class starts.
"""

import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from core.models import ClassTransfer
from core.sms_utils import send_class_transfer_reminder_15min


class Command(BaseCommand):
    help = 'Send 15-minute advance SMS and Email reminders to substitute faculty for transferred classes.'

    def handle(self, *args, **options):
        now = timezone.localtime()
        today = now.date()
        current_time = now.time()

        # Fetch active class transfers for today where reminder has not been sent yet
        transfers = ClassTransfer.objects.filter(
            date=today,
            status__in=['accepted', 'pending'],
            reminder_sent=False
        ).select_related('substitute_faculty__user', 'original_faculty__user', 'timetable_entry__subject', 'timetable_entry__section')

        sent_count = 0
        for t in transfers:
            tt = t.timetable_entry
            start_time = tt.start_time

            # Period default time mapping if start_time is unset on model
            period_times = {
                1: datetime.time(9, 0),
                2: datetime.time(9, 50),
                3: datetime.time(10, 50),
                4: datetime.time(11, 40),
                5: datetime.time(13, 20),
                6: datetime.time(14, 10),
                7: datetime.time(15, 10),
                8: datetime.time(16, 0),
            }

            p_time = start_time if start_time else period_times.get(tt.period, datetime.time(9, 0))
            
            # Calculate time difference in minutes
            dt_start = datetime.datetime.combine(today, p_time)
            dt_now = datetime.datetime.combine(today, current_time)
            diff_mins = (dt_start - dt_now).total_seconds() / 60.0

            # Send reminder if period starts within 15 minutes (or if period is starting now)
            if -5 <= diff_mins <= 20:
                if send_class_transfer_reminder_15min(t):
                    sent_count += 1
                    self.stdout.write(self.style.SUCCESS(f"Sent 15-min reminder for Transfer ID {t.id} to Prof. {t.substitute_faculty.full_name}"))

        self.stdout.write(self.style.SUCCESS(f"Processed {transfers.count()} transfers. Sent {sent_count} reminders."))
