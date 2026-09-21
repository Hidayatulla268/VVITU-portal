"""
VVITU Portal — Management Command: Seed Academic Calendar Events
Populates rich university-wide and branch-specific academic events, exams,
and holidays for September through December 2026.
"""

import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from core.models import AcademicCalendar, Branch, Year


class Command(BaseCommand):
    help = 'Seeds realistic university-wide and branch-specific academic calendar events.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing events before seeding'
        )

    def handle(self, *args, **options):
        if options.get('clear'):
            count, _ = AcademicCalendar.objects.all().delete()
            self.stdout.write(self.style.WARNING(f"Cleared {count} existing academic calendar events."))

        today = timezone.localdate()
        tomorrow = today + datetime.timedelta(days=1)

        branches = {b.code: b for b in Branch.objects.all()}
        cse_branch = branches.get('CSE')
        ece_branch = branches.get('ECE')
        mech_branch = branches.get('MECH')
        civil_branch = branches.get('CIVIL')
        eee_branch = branches.get('EEE')
        csm_branch = branches.get('CSM')

        events_data = [
            # ── TOMORROW (1-Day Reminder Candidate) ─────────────────────────
            {
                'title': 'VVITU Annual Tech Conclave & Hackathon 2026 — Grand Inauguration',
                'date': tomorrow,
                'event_type': 'event',
                'branch': None,  # University-Wide
                'year': None,
                'description': (
                    "All departments and students across all academic years are invited to the Main Auditorium "
                    "for the grand inauguration ceremony. Featuring keynote addresses by engineering leaders from "
                    "Google & Microsoft, project exhibitions, and kickoff of the 24-hour hackathon. Attendance is mandatory."
                )
            },
            {
                'title': 'CSE Hands-on Workshop: Scalable Cloud Architecture & GenAI Systems',
                'date': tomorrow,
                'event_type': 'event',
                'branch': cse_branch,
                'year': None,
                'description': (
                    "Department of Computer Science & Engineering exclusive full-day workshop in Computing Lab 301. "
                    "Covers Docker, Kubernetes, microservice design, LLM orchestration with LangChain, and real-time APIs. "
                    "All CSE faculty, research scholars, and students are requested to attend with their laptops."
                )
            },
            {
                'title': 'ECE Bootcamp: VLSI Circuit Design & Embedded IoT Systems',
                'date': tomorrow,
                'event_type': 'event',
                'branch': ece_branch,
                'year': None,
                'description': (
                    "Organized by the Department of Electronics & Communication Engineering in the Embedded Systems Lab. "
                    "Hands-on session on FPGA programming, SystemVerilog synthesis, sensor interfacing, and MQTT telemetry."
                )
            },
            {
                'title': 'MECH Industry Seminar: Advanced CAD/CAM & Robotics Automation',
                'date': tomorrow,
                'event_type': 'event',
                'branch': mech_branch,
                'year': None,
                'description': (
                    "Department of Mechanical Engineering seminar in Siemens Centre of Excellence. "
                    "Live demonstrations of multi-axis CNC machining, robotic welding simulation, and digital twin manufacturing."
                )
            },

            # ── UPCOMING: SEPTEMBER 2026 ────────────────────────────────────
            {
                'title': 'Mid-1 Internal Examinations (All Branches & Years)',
                'date': today + datetime.timedelta(days=4),  # 2026-09-25
                'event_type': 'exam',
                'branch': None,
                'year': None,
                'description': (
                    "Formal Mid-1 assessment for all UG/PG branches under R23/R20 regulations. "
                    "Forenoon session: 10:00 AM – 12:00 PM; Afternoon session: 02:00 PM – 04:00 PM. "
                    "Hall tickets and college ID cards are strictly compulsory."
                )
            },
            {
                'title': 'CSM AI Innovation Showcase & Deep Learning Project Pitch',
                'date': today + datetime.timedelta(days=9),  # 2026-09-30
                'event_type': 'event',
                'branch': csm_branch,
                'year': None,
                'description': (
                    "CSE (AI & ML) branch symposium with capstone presentations, computer vision demos, "
                    "and evaluation by an external industry panel. Outstanding teams will receive incubation support."
                )
            },

            # ── UPCOMING: OCTOBER 2026 ─────────────────────────────────────
            {
                'title': 'Mahatma Gandhi Jayanti (National Holiday)',
                'date': datetime.date(2026, 10, 2),
                'event_type': 'holiday',
                'branch': None,
                'year': None,
                'description': (
                    "The University will remain closed on Friday, 02 October 2026 in observance of "
                    "Mahatma Gandhi Jayanti. Regular academic sessions will resume on Saturday."
                )
            },
            {
                'title': 'CIVIL Field Survey Camp & Aerial Drone Photogrammetry',
                'date': datetime.date(2026, 10, 8),
                'event_type': 'event',
                'branch': civil_branch,
                'year': None,
                'description': (
                    "Practical survey camp conducted at the university outer grounds. Includes Total Station data capture, "
                    "GPS contouring, GIS software integration, and UAV topographical analysis."
                )
            },
            {
                'title': 'EEE National Symposium: Smart Grids & Clean Energy Transition',
                'date': datetime.date(2026, 10, 15),
                'event_type': 'event',
                'branch': eee_branch,
                'year': None,
                'description': (
                    "Annual national symposium organized by Electrical & Electronics Engineering. "
                    "Technical paper presentations, EV powertrain design exhibits, and power electronics workshop."
                )
            },
            {
                'title': 'Dussehra & Vijayadashami Break',
                'date': datetime.date(2026, 10, 20),
                'event_type': 'holiday',
                'branch': None,
                'year': None,
                'description': (
                    "University remains closed for Dussehra festival holidays from October 20 to October 25, 2026. "
                    "Hostels remain operational. College reopens on Monday, October 26, 2026."
                )
            },

            # ── UPCOMING: NOVEMBER & DECEMBER 2026 ──────────────────────────
            {
                'title': 'Mid-2 Examination Schedule Release & Condonation Deadline',
                'date': datetime.date(2026, 11, 5),
                'event_type': 'deadline',
                'branch': None,
                'year': None,
                'description': (
                    "Deadline for faculty to upload continuous assessment grades and syllabus coverage audit reports. "
                    "Mid-2 examination schedule will be published on student and faculty dashboards."
                )
            },
            {
                'title': 'Diwali / Deepavali Festival Holiday',
                'date': datetime.date(2026, 11, 12),
                'event_type': 'holiday',
                'branch': None,
                'year': None,
                'description': (
                    "University holiday in celebration of the Festival of Lights (Deepavali). "
                    "Wishing all students, faculty, and staff a joyous and prosperous Diwali."
                )
            },
            {
                'title': 'Semester End Practical Laboratory Examinations',
                'date': datetime.date(2026, 11, 25),
                'event_type': 'exam',
                'branch': None,
                'year': None,
                'description': (
                    "Semester end laboratory external practical examinations across all branches. "
                    "Internal and external examiner rosters will be dispatched via DEO and HOD portals."
                )
            },
            {
                'title': 'Semester End Theory Examinations Commencing',
                'date': datetime.date(2026, 12, 5),
                'event_type': 'exam',
                'branch': None,
                'year': None,
                'description': (
                    "Commencement of End Semester Theory Examinations. Seating blueprints and invigilation duty rosters "
                    "are active under Admin and Examination Branch portals."
                )
            },
        ]

        created_count = 0
        for data in events_data:
            obj, created = AcademicCalendar.objects.get_or_create(
                title=data['title'],
                date=data['date'],
                defaults={
                    'event_type': data['event_type'],
                    'branch': data['branch'],
                    'year': data['year'],
                    'description': data['description'],
                    'reminder_sent': False,
                }
            )
            if created:
                created_count += 1
                scope = data['branch'].code if data['branch'] else 'University-Wide'
                self.stdout.write(self.style.SUCCESS(
                    f"Created: [{scope}] {data['date']} - {data['title']}"
                ))

        self.stdout.write(self.style.SUCCESS(
            f"\nSeeding complete! Added {created_count} events. Total events now: {AcademicCalendar.objects.count()}."
        ))
