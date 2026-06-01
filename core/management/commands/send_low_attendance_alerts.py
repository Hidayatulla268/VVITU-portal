"""
VVIT Portal — Management Command: send_low_attendance_alerts

Sends email notifications to students whose overall attendance falls
below the LOW_ATTENDANCE_THRESHOLD defined in settings.py (default 75%).

Usage:
    python manage.py send_low_attendance_alerts
    python manage.py send_low_attendance_alerts --threshold 65
    python manage.py send_low_attendance_alerts --dry-run

Schedule via cron (example — runs every Monday at 8 AM):
    0 8 * * 1 /path/to/venv/bin/python /path/to/manage.py send_low_attendance_alerts
"""

from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.conf import settings
from django.db.models import Count, Q

from accounts.models import Student
from core.models import Attendance


class Command(BaseCommand):
    help = 'Email students who have attendance below the configured threshold.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--threshold',
            type=float,
            default=None,
            help='Override the LOW_ATTENDANCE_THRESHOLD from settings (0–100).',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Print affected students without actually sending emails.',
        )

    def handle(self, *args, **options):
        threshold = options['threshold'] or getattr(settings, 'LOW_ATTENDANCE_THRESHOLD', 75)
        dry_run   = options['dry_run']

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"Checking attendance against threshold: {threshold}%"
                + (' (DRY RUN)' if dry_run else '')
            )
        )

        # Pull all active students with their attendance records.
        # prefetch_related keeps this to 2 queries regardless of student count.
        students = (
            Student.objects
            .filter(is_active=True)
            .prefetch_related('attendance_records')
            .select_related('user', 'branch', 'year', 'section')
        )

        emailed = 0
        skipped = 0

        for student in students:
            records = student.attendance_records.all()
            total   = len(records)
            if total == 0:
                skipped += 1
                continue

            present = sum(1 for r in records if r.status == 'P')
            pct     = present / total * 100

            if pct < threshold:
                msg = (
                    f"Dear {student.user.get_full_name()},\n\n"
                    f"Your current attendance is {pct:.1f}%, which is below the minimum "
                    f"required threshold of {threshold}%.\n\n"
                    f"  • Classes attended : {present}\n"
                    f"  • Total classes    : {total}\n\n"
                    f"Please ensure you attend classes regularly to avoid academic penalties.\n\n"
                    f"For guidance, contact your counsellor:\n"
                    f"  {student.counsellor.user.get_full_name() if student.counsellor else 'Not assigned'}\n\n"
                    f"Regards,\nVVIT Academic Office\n{settings.COLLEGE_NAME}"
                )

                if dry_run:
                    self.stdout.write(
                        self.style.WARNING(
                            f"  [DRY RUN] Would email {student.user.email} "
                            f"(Roll: {student.roll_number}, Att: {pct:.1f}%)"
                        )
                    )
                else:
                    try:
                        send_mail(
                            subject =f"[VVIT] Low Attendance Warning — {pct:.1f}%",
                            message =msg,
                            from_email=settings.DEFAULT_FROM_EMAIL,
                            recipient_list=[student.user.email],
                            fail_silently=False,
                        )
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"  Emailed {student.user.email} ({student.roll_number}, {pct:.1f}%)"
                            )
                        )
                    except Exception as exc:
                        self.stdout.write(
                            self.style.ERROR(
                                f"  Failed to email {student.user.email}: {exc}"
                            )
                        )

                emailed += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone. {emailed} alert(s) {'queued' if dry_run else 'sent'}, "
                f"{skipped} student(s) skipped (no attendance data)."
            )
        )
