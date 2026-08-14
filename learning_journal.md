# VVITU Portal — Learning Journal
This journal details the system design, directory structure, commands, key code constructs, and recently added premium features of the VVITU ERP Portal.

---

## 1. Why Add These New Features?

Adding features to a live college ERP platform isn't just about expanding functionality; it is about reinforcing **system integrity, security, auditability, and user experience**.

### A. Soft Delete Pattern
*   **What it is:** Instead of using SQL `DELETE` which permanently removes records from the database, the system marks the record with `is_deleted = True` and logs the timestamp (`deleted_at`) and the user who triggered it (`deleted_by_name`).
*   **Why it is useful:** In an educational database carrying the data of 300,000+ students, accidental deletions of a student, faculty member, or subject could break relational integrity (e.g., deleting attendance history or exam marks). Soft deletion prevents data loss, preserves audit trails, and allows for instant restoration.

### B. Database Backups Manager
*   **What it is:** A portal interface that lets administrators run, download, restore, or delete JSON database backups directly.
*   **Why it is useful:** Ensures high availability. If a data entry operator makes a mistake during a bulk upload, the administrator can restore the previous database state in seconds. It also simplifies local migration and testing.

### C. Consolidated PDF Reports (ReportLab)
*   **What it is:** Dynamic generation of beautifully formatted PDF documents of institutional overviews, faculty rosters, student lists, curriculum summaries, and student GPA registers.
*   **Why it is useful:** Academic auditing requires physical or unalterable digital (PDF) documentation. These consolidated PDFs allow college executives and registrars to generate official university reports with a single click.

### D. HOD Scoped Operations & System Alerts
*   **What it is:** Scopes HOD actions strictly to their department and logs a system notification warning to admins whenever an HOD creates, modifies, or deletes records.
*   **Why it is useful:** Limits the threat boundary (e.g., the CSE HOD cannot delete an ECE student). The admin alerts create an immutable log of administrative activity, increasing accountability.

### E. Premium CSS Micro-Animations
*   **What it is:** Subtle animations such as hover scale effects, diagonal shimmer sweeps on buttons, sliding sidebar links, and breathing badge alerts.
*   **Why it is useful:** Turns a dry academic interface into a premium, responsive app. Micro-animations guide the user's focus (e.g., pulsing notifications demand attention) and feel professional.

### F. Branch Search (Multi-Attribute Search)
*   **What it is:** The search filters in lists (like Student Registry) now support queries against branch codes, branch names, sections, and academic years (e.g., searching "CSE" or "CSE-II-A").
*   **Why it is useful:** Allows administrators and HODs to quickly filter and manage students by department or cohort directly from a single global search input.

### G. Semester Final Exam Marks Restrictions
*   **What it is:** Strict role-based authorization blocking non-admin staff (Faculty and HODs) from uploading or modifying marks for Semester Final (`final`) exams.
*   **Why it is useful:** Guarantees academic security. Faculty and HODs can log internal Mid-term marks, but final exam grades remain locked against tampering, editable only by the System Administrator.

### H. Optional Email Fallback
*   **What it is:** The email field is now optional during manual user creation or bulk CSV uploads. If left blank, it defaults automatically to `username@vvitu.net`.
*   **Why it is useful:** Minimizes data-entry load. Operators do not need to manually input student emails; the system generates standard institutional addresses automatically.

### I. Department-Wide Results Scope for HODs
*   **What it is:** HODs viewing the "My Teaching" dashboard see results and subjects for all students in their department, rather than just students they personally advise.
*   **Why it is useful:** Provides HODs with full administrative oversight over the academic performance of their entire branch, while teaching staff remain scoped only to their direct advisees.

### J. Hardened Login Rate Limiting (IP + Username Lockout)
*   **What it is:** Brute force security protection that locks out client IP addresses after 5 failed login attempts in 60 seconds, and locks out individual target usernames after 10 failed login attempts in 120 seconds. Additionally, successful logins instantly reset both cache counters.
*   **Why it is useful:** Protects the portal against standard single-IP brute forcing as well as distributed credential stuffing (botnet attacks targeting a single username from thousands of different IP proxies) without penalizing legitimate users who occasionally make typos.

### K. Premium Login Screen Animations
*   **What it is:** Micro-animations on the login page including card hover lifts, dynamic background orb drifts, sequential loading delays, horizontal error shakes, and input focus bouncing.
*   **Why it is useful:** Wows users during authentication, directing attention and reinforcing a premium, polished user experience.

### L. Dynamic Cascading Dropdowns for Results Uploads
*   **What it is:** Filtering the Subject, Exam, and Section dropdown selectors by Branch and Academic Year on all student results addition and marks uploading views.
*   **Why it is useful:** Prevents administrative human errors. In large academic databases, operators and HODs could easily select mismatched combinations (e.g. uploading CSE marks to an ECE exam slot), causing silent data corruption. Cascading selectors guarantee that only valid, related subjects/exams are shown.

### M. Daily Faculty Attendance & Log Tracking (`FacultyAttendance` Model)
*   **What it is:** A dedicated tracking system allowing HODs and System Administrators to record daily attendance statuses for faculty members (`Present`, `Absent`, `On Leave`, `Official Duty`), with check-in timestamps and remarks. Faculty members can view their own monthly attendance log and attendance percentage summary.
*   **Why it is useful:** Enables HR and academic management transparency. Ensures faculty punctuality, simplifies leave accounting, and provides official institutional logs for payroll and compliance auditing.

### N. Substitute Class Period Transfers (`ClassTransfer` Model)
*   **What it is:** A substitute class delegation flow allowing faculty members who are absent or on leave to select scheduled class slots for the day and assign them to substitute faculty members within their department.
*   **Why it is useful:** Ensures zero class loss and continuous academic coverage. When a class is transferred, the substitute faculty member is granted explicit authorization to mark student attendance for that specific period, maintaining accurate attendance records without compromising authorization checks.

### O. Classroom / Lab Location Tracking (`room_number` in Timetable)
*   **What it is:** Extends timetable slots with specific room/lab numbers (e.g. "Block C - Room 305" or "Lab 4").
*   **Why it is useful:** Eliminates scheduling confusion for both students and faculty members in multi-building campus layouts. Room assignments are prominently displayed across timetable management grids, daily faculty schedules, and substitute transfer modals.

### P. Parent SMS Alert Utility Module (`core/sms_utils.py`)
*   **What it is:** A centralized utility providing standardized helper functions (`send_absent_sms_to_parent`, `send_result_sms_to_parent`) for sending SMS notifications to parents when students are marked absent or when exam results are published.
*   **Why it is useful:** Promotes real-time parent-institution communication and student attendance accountability. Decouples SMS gateway logic from core views for easy maintainability and testing.

### Q. Enhanced Month-wise Attendance Report Filtering
*   **What it is:** Added an HTML5 month-picker (`<input type="month">`) to the faculty reports interface, enabling quick month-by-month filtering of student attendance records alongside custom start and end dates.
*   **Why it is useful:** Speeds up monthly attendance auditing and report generation for faculty advisors and department heads, eliminating the need to manually compute start and end dates for every calendar month.

### R. Extended Student Profile & Fee Tracking System
*   **What it is:** Optional demographic fields (`gender`, `caste`, `religion`, `parent_occupation`, `personal_mobile`, `permanent_address`, `present_address`) and fee tracking (`fees_pending`, `fees_updated_at`) visible to Admin, HODs, Class Teachers, and Counsellors on `/accounts/students/<id>/detail/`.
*   **Why it is useful:** Provides holistic student profiling, academic advisory context, and financial dues monitoring for faculty advisors and department heads.

### S. Course Degree Hierarchy (`Course` Model)
*   **What it is:** Introduces `Course` model (`B.Tech`, `BBA`, `MBA`, `M.Tech`) linked to `Branch`, structuring departments under specific degree programs.
*   **Why it is useful:** Enables multi-degree university management, supporting undergraduate and postgraduate programs seamlessly within the same portal.

### T. Timetable Attendance Auto-Mapping & Date Selector
*   **What it is:** Enhanced attendance marking form with date calendar selector, live class timing preview (`09:00 AM - 09:50 AM`), classroom location badges, and auto-mapping to scheduled timetable slots.
*   **Why it is useful:** Minimizes clicks for teaching staff and eliminates incorrect period selection by automatically pre-selecting the exact subject scheduled for that section and day.

### U. Multi-Tier Notification Target Routing (`core/sms_utils.py`)
*   **What it is:** Differentiated notification dispatch system:
    - **Parents:** Receive ONLY Absent alerts and Semester Final Results (Grades + CGPA only).
    - **Students:** Receive SMS & Email for Mid Results (marks obtained), Semester Final Results, Absent alerts, Low Attendance alerts (<75%), and notices.
*   **Why it is useful:** Ensures parent communications are concise and high-priority while providing students with detailed academic performance and attendance alerts across SMS and email.

### V. User Profile Picture Management
*   **What it is:** Image upload support for user avatars (`profile_picture`), stored under `media/profile_pics/`, rendered in top navbar, profile pages, and detail views.
*   **Why it is useful:** Enhances visual identification across student registries, faculty rosters, and navigation bars.

### W. College-Wide Admin Class Proxy & Substitution Audit System
*   **What it is:** Centralized proxy assignment and class history audit system allowing administrators to monitor, filter, and assign substitute faculty members to any class period across all academic branches college-wide.
*   **Why it is useful:** Gives university leadership and academic registrars complete institutional oversight to prevent class cancellations, resolve faculty unavailability in real time, and audit proxy substitution records with automated SMS and email notifications to assigned faculty.

### X. Resilient Multi-Format Date Parsing Engine (`core/transfer_utils.py`)
*   **What it is:** A centralized `parse_flexible_date()` utility that gracefully handles ISO formats (`YYYY-MM-DD`), human-readable Flatpickr dates (`Fri, 14 Aug 2026`, `14-Aug-2026`), and standard date strings without throwing 400 or 500 errors.
*   **Why it is useful:** Eliminates client-server date format mismatches between frontend date pickers (like Flatpickr) and backend view logic, ensuring uninterrupted AJAX querying and form submissions.

### Y. Optional Faculty Daily Class Discussion Log & Student Class Diary (`ClassDiary` Model)
*   **What it is:** An integrated lesson logging system where faculty can optionally record topics covered, key concepts discussed, and homework/reading assignments during attendance marking or via a dedicated Faculty Class Diary management panel (`/faculty/class-diary/`). Students in that section can view these notes chronologically on their own Class Diary feed (`/student/class-diary/`) and dashboard widget.
*   **Why it is useful:** Bridges communication between teachers and students, facilitates continuous revision, keeps absent students informed of class progress, and is 100% optional so it adds zero friction to the daily attendance marking workflow.

### Z. High-Contrast Target Audience Capsule Badge System
*   **What it is:** High-contrast audience badges (`Everyone`, `All Admins`, `All HODs`, `All Faculty`, `All Students`, `Class Sections`, `Branches`) with distinct dark and light mode themes for the notices board.
*   **Why it is useful:** Ensures clear visibility and instant readability across both Dark and Light themes.

---

## 2. Directory Structure & File Roles

The project is structured logically as a modular multi-app Django workspace. Below is the breakdown of key directories:

```
VVITU_Portal/
├── VVITU_Portal/          # Django Root Configuration
│   ├── settings.py       # Core Django settings (Database, Apps, Middlewares)
│   ├── settings_prod.py  # Production configuration (Security headers, SSL, caching)
│   ├── urls.py           # Root URL Router
│   └── middleware.py     # Role-based middleware & Login Brute Force protection
│
├── accounts/             # User Profile & Identity App
│   ├── models.py         # User, Student, Faculty, DEO, and Achievement models
│   ├── views.py          # Session auth views, profiles, and password reset flows
│   └── profile_detail_views.py  # Admin/HOD read-only student & faculty views
│
├── core/                 # Shared Academic Logic App
│   ├── models.py         # Branch, Section, Subject, Timetable, Attendance, FacultyAttendance, ClassTransfer, Exam, Result, Notification models
│   ├── notification_views.py # Notices CRUD logic (compose, edit, delete notifications)
│   ├── sms_utils.py      # Parent SMS alert helper functions (absence & exam results)
│   └── management/commands/ # Custom Python terminal management tasks
│
├── admin_dashboard/      # Administrator Management App
│   ├── urls.py           # Admin URL routes
│   └── views.py          # Admin logic (backups, PDF rendering, faculty attendance, student/faculty CRUD)
│
├── hod/                  # Head of Department App
│   └── views.py          # HOD scoped actions (faculty attendance, class transfers, release results, assign teachers, verify achievements)
│
├── deo/                  # Data Entry Operator App
│   └── views.py          # Branch-scoped student entries & attendance uploads (1-day limit)
│
├── student/              # Student Panel App
│   └── views.py          # Dashboard view, results lists, and AI attendance estimator
│
├── faculty/              # Teaching Staff App
│   └── views.py          # Attendance sheets, class transfer requests, my attendance logs, marks uploading, and student advisor views
│
├── templates/            # HTML Template Registry (inheriting core/base.html glassmorphic styling)
│   ├── admin_dashboard/  # Backup dashboard, student bulk upload, staff managers, faculty_attendance.html
│   ├── faculty/          # Dashboard, attendance sheet, my_attendance.html, reports.html
│   ├── hod/              # HOD department manager, approvals, timetable editors, faculty_attendance.html
│   ├── core/             # Base layout, notifications board, composer
│   └── ...               # App-specific HTML views
│
├── static/               # Static Assets
│   ├── css/main.css      # Glassmorphic layout stylesheets & micro-animations
│   └── js/main.js        # Global sidebar controls, drop-down scripting, AJAX handlers
│
└── backups/              # Directory holding database dump files (.json)
```

---

## 3. Terminal & Console Commands

These are the primary commands executed to manage and run the project:

| Command | Usage / Description |
| :--- | :--- |
| `python manage.py runserver` | Starts the Django local development server on `http://127.0.0.1:8000/`. |
| `python -m venv venv` | Sets up a fresh local Python virtual environment. |
| `venv\Scripts\activate` | Activates the virtual environment (Windows syntax). |
| `pip install -r requirements.txt` | Installs all package dependencies (Django, ReportLab, scikit-learn, openpyxl). |
| `python manage.py makemigrations` | Evaluates Python models and generates database migration files. |
| `python manage.py migrate` | Applies pending migration files to the database schema (SQLite or PostgreSQL). |
| `python manage.py seed_data` | **Custom Command:** Runs the script in `core/management/commands/seed_data.py` to populate the DB with sample branches, years, students, teachers, results, and calendars. |
| `python manage.py send_low_attendance_alerts` | **Custom Command:** Scans student attendance rates and notifies students below 75% threshold via in-app alerts and emails. |
| `python manage.py dumpdata` | Serializes the database contents into JSON formats (used programmatically in backup creations). |
| `python manage.py loaddata <file>` | Restores the database content from a serialized JSON file. |

---

## 4. Dictionaries & Core Data Mappings

Python dictionaries (`dict`) and choice mappings are heavily utilized throughout the codebase to drive dashboard routing, grade logic, and views. Key examples:

### A. Role Dashboard Mapping (`accounts/models.py`)
Used to dynamically redirect a user to their appropriate role-based dashboard immediately after authentication:
```python
role_map = {
    'student':       'student:dashboard',
    'faculty':       'faculty:dashboard',
    'hod':           'hod:dashboard',
    'lab_technician':'faculty:dashboard',
    'admin':         'admin_dashboard:dashboard',
    'deo':           'deo:dashboard',
}
```

### B. Timetable Section Grid Mapping (`hod/views.py`)
In the timetable editing system, a dictionary is constructed to map periods (1 to 8) under specific days of the week:
```python
days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
periods = list(range(1, 9))
grid = {day: {p: None for p in periods} for day in days}
for e in entries:
    if e.day in grid:
        grid[e.day][e.period] = e
```
*   **Use:** This maps database entries dynamically onto an $8 \times 6$ table matrix in the HTML template.

### C. Grade Value Mapping (`accounts/models.py`)
Links letter grades to grade points used to compute a student's cumulative grade point average (CGPA):
```python
grade_points = {
    'S': 10, 'A': 9, 'B': 8, 'C': 7, 'D': 6, 'E': 5,
    'F': 0, 'Ab': 0
}
```

### D. Faculty Attendance Status Mapping (`core/models.py`)
Status tuple driving daily faculty attendance tracking and badge renders:
```python
ATTENDANCE_STATUS_CHOICES = (
    ('P', 'Present'),
    ('A', 'Absent'),
    ('L', 'On Leave'),
    ('OD', 'Official Duty'),
)
```

### E. Class Substitute Transfer Status Mapping (`core/models.py`)
Workflow states for substitute period requests:
```python
TRANSFER_STATUS_CHOICES = (
    ('pending', 'Pending'),
    ('accepted', 'Accepted'),
    ('rejected', 'Rejected'),
)
```

---

## 5. In-Depth Code walkthrough

### A. How Soft Delete Filters Data
To implement soft deletion, models include fields:
```python
is_deleted = models.BooleanField(default=False, db_index=True)
deleted_by_name = models.CharField(max_length=150, blank=True, null=True)
deleted_at = models.DateTimeField(blank=True, null=True)
```
When an item is deleted (e.g. in `hod:delete_student` or `admin_dashboard:delete_subject`), we save the context instead of calling `.delete()`:
```python
# Mark user deleted
user = student.user
user.is_active = False
user.is_deleted = True
user.deleted_by_name = f"{request.user.get_full_name() or request.user.username} ({request.user.role.upper()})"
user.deleted_at = timezone.now()
user.save()
```
In our view lists, we query only active records using `is_deleted=False`:
```python
# Query active students in HOD dashboard
qs = Student.objects.filter(branch=dept, user__is_deleted=False)
```

### B. How Backups are Created and Restored
The backup manager executes Django command-line operations dynamically in the background using `django.core.management.call_command`:
```python
from django.core.management import call_command
import io

# 1. Create a dynamic memory stream
out = io.StringIO()

# 2. Dump all DB entries except core authentication and content types to prevent conflicts
call_command('dumpdata', exclude=['contenttypes', 'auth.Permission'], stdout=out)

# 3. Save to backups directory on disk
with open(filepath, 'w', encoding='utf-8') as f:
    f.write(out.getvalue())
```
Restoring reads the file path and calls `loaddata`:
```python
call_command('loaddata', filepath)
```

### C. ReportLab PDF Generation
The PDF export builds reports using ReportLab's Flowables system (Table, Paragraph, Spacer, PageBreak) structured within a `SimpleDocTemplate` page template:
```python
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=36, leftMargin=36, topMargin=40, bottomMargin=40)
story = []

# Style definition
styles = getSampleStyleSheet()
title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=20, textColor=colors.HexColor('#991b1b'))

# Adding flowable elements
story.append(Paragraph("Consolidated Institutional Data Audit", title_style))
story.append(Spacer(1, 20))

# Building grids via Tables
t_overview = Table(overview_data, colWidths=[200, 200])
t_overview.setStyle(TableStyle([
    ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#991b1b')),
    ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
]))
story.append(t_overview)

# Compile document
doc.build(story)
```

### D. HOD Scoped Operations & Admin Alerts
Whenever an HOD makes changes to resources, the server verifies access rights via the `@hod_required` decorator, which attaches `request.department` based on their profile.
If validated, the action is performed, and a system log is created using the `Notification` model:
```python
Notification.objects.create(
    title="Student Account Created by HOD",
    message=f"HOD {request.user.get_full_name()} created student {first_name} {last_name} ({username}) in department {dept.code}.",
    notif_type=Notification.TYPE_SYSTEM,
    priority=Notification.PRIORITY_HIGH,
    target_all=False,
    target_role='admin',
    created_by=request.user
)
```
*   **Result:** Admin logs dynamically populate the administrator's dashboard instantly, warning them about department changes.

### E. Scoping Final Exam Upload Permissions in Code
In `faculty/views.py`, the system strictly blocks Semester Final uploads for non-admins:
```python
if selected_exam_id:
    selected_exam = get_object_or_404(Exam, id=selected_exam_id)
    if selected_exam.exam_type == 'final':
        messages.error(request, "Only the Administrator is authorized to upload Semester Final exam results.")
        return redirect('faculty:upload_marks')
```
And similarly in the POST request handler:
```python
if ex.exam_type == 'final':
    messages.error(request, "Only the Administrator is authorized to upload Semester Final exam results.")
    return redirect(f"{request.path}?subject={subj_id}&exam={ex_id}&section={sec_id}")
```

### F. Multi-Attribute Query Filters
The student student search query leverages Django's `Q` object to combine multiple branch and section fields:
```python
from django.db.models import Q
qs = qs.filter(
    Q(roll_number__icontains=search) | 
    Q(user__first_name__icontains=search) | 
    Q(user__last_name__icontains=search) |
    Q(branch__code__icontains=search) |
    Q(branch__name__icontains=search) |
    Q(section__name__icontains=search) |
    Q(year__year__icontains=search)
)
```

### G. Hardened Login Rate Limiting and Dynamic Reset
In `VVITU_Portal/middleware.py`, rate limit checking checks both client IP and username:
```python
if request.method == "POST" and path == "/accounts/login/":
    ip = self._get_client_ip(request)
    username = request.POST.get('username', '').strip().lower()
    
    ip_key = f"login_attempts_{ip}"
    user_key = f"login_attempts_user_{username}" if username else None
    
    ip_attempts = cache.get(ip_key, 0)
    user_attempts = cache.get(user_key, 0) if user_key else 0
    
    if ip_attempts >= 5:
        return self._lockout_response("IP Address", "1 minute")
    if user_attempts >= 10:
        return self._lockout_response(f"username '{username}'", "2 minutes")
        
    cache.set(ip_key, ip_attempts + 1, timeout=60)
    if user_key:
        cache.set(user_key, user_attempts + 1, timeout=120)
```
And in `accounts/views.py`, the cache is dynamically cleared on successful authentication:
```python
user = authenticate(request, username=resolved_username, password=password)
if user is not None:
    from django.core.cache import cache
    # Extract client IP
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    ip = x_forwarded_for.split(',')[0].strip() if x_forwarded_for else request.META.get('REMOTE_ADDR')
    
    # Delete attempt records to prevent lockout after successful login
    cache.delete(f"login_attempts_{ip}")
    cache.delete(f"login_attempts_user_{resolved_username.lower()}")
    
    login(request, user)
```

### H. Login Screen Transitions & Animations
In `static/css/login.css`, the page elements are stylized with CSS keyframe rules:
```css
/* Card hover glow and lift translation */
.login-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 28px 72px rgba(0, 0, 0, 0.65), 0 0 50px rgba(220, 38, 38, 0.12);
  border-color: rgba(220, 38, 38, 0.28) !important;
}

/* Sequential element loading delay (left & right panels) */
.left-content > *,
.login-card .mobile-logo-ring,
.login-card .d-block.d-lg-none.text-center,
.login-card .form-header,
.login-card .vvit-alert,
.login-card .login-form .form-group-float,
.login-card .login-form .btn-login,
.login-card .form-footer {
  animation: fadeInUp 0.7s cubic-bezier(0.25, 0.8, 0.25, 1) both;
}

/* Background parallax shift controller via custom properties */
.parallax-container {
  transform: translate3d(var(--mouse-x, 0px), var(--mouse-y, 0px), 0);
  transition: transform 0.25s cubic-bezier(0.25, 0.8, 0.25, 1);
}

/* Input focus breathing pulse glow */
@keyframes input-pulse {
  0% { box-shadow: 0 0 0 0 rgba(220, 38, 38, 0.25); }
  50% { box-shadow: 0 0 0 4px rgba(220, 38, 38, 0.45); }
  100% { box-shadow: 0 0 0 0 rgba(220, 38, 38, 0.25); }
}
```

### I. Background Parallax JavaScript Handler
To implement the responsive background movement, `templates/accounts/login.html` listens to mouse coordinates and updates CSS variables:
```javascript
document.addEventListener('mousemove', function(e) {
  const amount = 25;
  const x = (e.clientX / window.innerWidth - 0.5) * amount;
  const y = (e.clientY / window.innerHeight - 0.5) * amount;
  
  const container = document.querySelector('.parallax-container');
  if (container) {
    container.style.setProperty('--mouse-x', `${x}px`);
    container.style.setProperty('--mouse-y', `${y}px`);
  }
});
```

### J. Cascading Dropdown Filtering Implementation
In `admin_dashboard/views.py` and `faculty/views.py`, the dropdown querysets are dynamically filtered when branch and year query parameters are selected, automatically clearing invalid selections:
```python
# Extract branch and year selections
branch_id = request.GET.get('branch') or request.POST.get('branch')
year_id = request.GET.get('year') or request.POST.get('year')

# Filter subject and exam choices accordingly
if branch_id and year_id:
    exams = Exam.objects.filter(branch_id=branch_id, year_id=year_id).order_by('-date')
    subjects = Subject.objects.filter(branch_id=branch_id, year_id=year_id, is_deleted=False)
else:
    exams = Exam.objects.none()
    subjects = Subject.objects.none()
```
And similarly in templates, the dropdowns are conditionally disabled until both filters are set:
```html
<select name="subject" class="vvit-select" required {% if not branch_id or not year_id %}disabled{% endif %}>
```

### K. Daily Faculty Attendance Tracking Logic
In `core/models.py`, `FacultyAttendance` tracks daily attendance records:
```python
class FacultyAttendance(models.Model):
    faculty = models.ForeignKey(Faculty, on_delete=models.CASCADE, related_name='attendance_records')
    date = models.DateField(default=timezone.now)
    status = models.CharField(max_length=5, choices=ATTENDANCE_STATUS_CHOICES, default='P')
    check_in_time = models.TimeField(null=True, blank=True)
    remarks = models.CharField(max_length=255, blank=True, null=True)
    marked_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        unique_together = ('faculty', 'date')
```
And in `hod/views.py`, attendance status updates use atomic `update_or_create`:
```python
FacultyAttendance.objects.update_or_create(
    faculty=fac,
    date=selected_date,
    defaults={
        'status': status,
        'remarks': remarks,
        'marked_by': request.user
    }
)
```

### L. Substitute Class Period Transfer Delegation Pattern
In `core/models.py`, `ClassTransfer` links a scheduled timetable entry to a substitute faculty member:
```python
class ClassTransfer(models.Model):
    timetable_entry = models.ForeignKey(Timetable, on_delete=models.CASCADE, related_name='transfers')
    date = models.DateField()
    original_faculty = models.ForeignKey(Faculty, on_delete=models.CASCADE, related_name='transfers_given')
    substitute_faculty = models.ForeignKey(Faculty, on_delete=models.CASCADE, related_name='transfers_received')
    reason = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=20, choices=TRANSFER_STATUS_CHOICES, default='accepted')
```
During student attendance marking in `faculty/views.py`, authority check inspects both original assignment and accepted substitute transfers:
```python
# Check if current faculty is original instructor or authorized substitute for today
is_substitute = ClassTransfer.objects.filter(
    timetable_entry=slot,
    substitute_faculty=faculty,
    date=today,
    status='accepted'
).exists()

if slot.faculty != faculty and not is_substitute:
    messages.error(request, "You are not authorized to mark attendance for this class period.")
    return redirect('faculty:dashboard')
```

### M. Timetable Classroom & Lab Location Tracking
In `core/models.py`, the `room_number` field specifies class location:
```python
class Timetable(models.Model):
    section = models.ForeignKey(Section, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    faculty = models.ForeignKey(Faculty, on_delete=models.CASCADE)
    day = models.CharField(max_length=15)
    period = models.IntegerField()
    room_number = models.CharField(max_length=100, default='Room 101', blank=True, help_text='Classroom / Lab location')
```

### N. Parent SMS Notification Helpers (`core/sms_utils.py`)
Standardized SMS dispatch functions decouple notification logic from HTTP requests:
```python
def send_absent_sms_to_parent(student, timetable_entry, date):
    if not student.parent_mobile:
        return False
    message = (
        f"Dear {student.parent_name or 'Parent'}, your ward {student.full_name} ({student.roll_number}) "
        f"was marked ABSENT for period {timetable_entry.period} ({timetable_entry.subject.code}) on {date}."
    )
    # Dispatch via SMS gateway API...
    return True
```

### O. Class Diary Model & Lesson Discussion Logging (`ClassDiary`)
`ClassDiary` in `core/models.py` enables faculty to optionally record topics taught, concepts discussed, and homework tasks:
```python
class ClassDiary(models.Model):
    timetable_entry     = models.ForeignKey(Timetable, on_delete=models.CASCADE, related_name='diary_entries')
    section             = models.ForeignKey(Section, on_delete=models.CASCADE, related_name='diary_logs')
    subject             = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='diary_logs')
    faculty             = models.ForeignKey('accounts.Faculty', on_delete=models.CASCADE, related_name='diary_logs')
    date                = models.DateField(db_index=True)
    period              = models.IntegerField(default=1)
    topic_covered       = models.CharField(max_length=255)
    discussion_summary  = models.TextField(blank=True)
    homework_assignment = models.TextField(blank=True)
    created_at          = models.DateTimeField(auto_now_add=True)
    updated_at          = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', 'period']
        unique_together = ('timetable_entry', 'date')
```

### P. Free Faculty Calculation & Flexible Date Parsing Engine (`core/transfer_utils.py`)
Centralized engine for conflict-free substitute assignment and resilient date string parsing:
```python
def parse_flexible_date(date_val):
    """Safely parses ISO dates, Flatpickr formats (Fri, 14 Aug 2026), and common date strings."""
    if not date_val:
        return None
    if isinstance(date_val, datetime.date):
        return date_val
    date_str = str(date_val).strip()
    try:
        return datetime.date.fromisoformat(date_str)
    except (ValueError, TypeError):
        pass
    formats = ['%a, %d %b %Y', '%A, %d %B %Y', '%d %b %Y', '%d-%b-%Y', '%d/%m/%Y', '%d-%m-%Y']
    for fmt in formats:
        try:
            return datetime.datetime.strptime(date_str, fmt).date()
        except (ValueError, TypeError):
            continue
    return None

def get_free_faculty_for_period(date, period, department=None, exclude_faculty=None):
    """Returns faculty members who have no class, no proxy duty, and no active leave for (date, period)."""
    day_name = date.strftime('%A')
    faculty_qs = Faculty.objects.filter(is_active=True, user__is_deleted=False)
    if department:
        faculty_qs = faculty_qs.filter(department=department)
    if exclude_faculty:
        faculty_qs = faculty_qs.exclude(id=exclude_faculty.id if isinstance(exclude_faculty, Faculty) else exclude_faculty)
    
    busy_ids = set(Timetable.objects.filter(day__iexact=day_name, period=period).values_list('faculty_id', flat=True))
    proxy_ids = set(ClassTransfer.objects.filter(date=date, timetable_entry__period=period, status__in=['pending', 'accepted']).values_list('substitute_faculty_id', flat=True))
    leave_ids = set(FacultyLeaveRequest.objects.filter(start_date__lte=date, end_date__gte=date, status__in=['approved', 'pending']).values_list('faculty_id', flat=True))
    
### AA. Syllabus / Unit Coverage & Class Discussion Tracker
*   **What it is:** A comprehensive academic progress monitoring framework that allows faculty to record daily lecture notes, key discussion takeaways, homework, and the specific syllabus unit covered (`Unit 1` to `Unit 5`, plus `Other/Revision/Lab`). Students can view what was taught on their portal. HODs have access to a department-scoped coverage tracker showing which faculty taught which topics and real-time unit completion progress pills (U1..U5) for every subject in their branch. System Administrators have college-wide visibility across all 11 departments with branch-filtering and institutional syllabus completion KPIs.
*   **Why it is useful:** Solves the core educational oversight challenge. Department heads and deans no longer need manual paper logs or guesswork to know how much of the curriculum has been taught before mid-terms and finals. Real-time unit completion badges immediately highlight lagging subjects, enabling timely intervention and ensuring students receive full curriculum coverage.

### BB. Student Comprehensive Counselling Dossier & Official PDF Export
*   **What it is:** A unified student academic, personal, and counselling dossier system. It compiles all student demographic data, family/parent details, residence, fee status/dues, semester-by-semester exam marks (Mid 1, Mid 2, Final Exam, total score, letter grade, grade points, credits, and SGPA per semester), cumulative CGPA, total credits earned, active backlogs, semester-by-semester subject attendance records, verified co-curricular achievements, and counsellor observation remarks with official sign-off spaces for Student, Counsellor, HOD, and Principal.
*   **Why it is useful:** Provides a 360-degree holistic academic record accessible to students (their own dossier), faculty counsellors/class teachers (their assigned wards), HODs (all students in their branch), and Administrators (college-wide). Enables single-click generation of professional multi-page ReportLab PDF documents with official university crest, confidential watermarks, and print-ready layout for physical accreditation audits (NAAC, NBA).

---

## 3. Key Code Constructs and Algorithms

### Q. Syllabus Unit Coverage & Scoped Class Diary Analytics Engine
Calculates real-time unit completion percentages and aggregates faculty lecture logs:
```python
# ── Unit Coverage Computation per Faculty & Subject ──
logs = ClassDiary.objects.filter(faculty=fac, subject=subj, section=sec)
total_logs = logs.count()
covered_units = set(logs.values_list('unit_number', flat=True))

# Syllabus completion out of standard 5 units
standard_units_covered = [u for u in [1, 2, 3, 4, 5] if u in covered_units]
unit_count = len(standard_units_covered)
progress_pct = min(100, int((unit_count / 5.0) * 100))
latest_log = logs.order_by('-date', '-period').first()

# Scoped query for HODs (strictly current department)
hod_diary_qs = ClassDiary.objects.filter(
    Q(section__branch=dept) | Q(faculty__department=dept) | Q(subject__branch=dept)
).distinct().select_related('section__branch', 'subject', 'faculty__user')

# University-wide query for Admin (all 11 branches with dynamic branch filter)
admin_diary_qs = ClassDiary.objects.all().select_related(
    'section__branch', 'section__year', 'subject__branch', 'faculty__user', 'faculty__department'
)
if branch_id:
    admin_diary_qs = admin_diary_qs.filter(
        Q(section__branch_id=branch_id) | Q(subject__branch_id=branch_id) | Q(faculty__department_id=branch_id)
    )
```

### R. Comprehensive Student Counselling Dossier & ReportLab PDF Generator (`core/counselling_utils.py`)
Compiles semester-by-semester academic history, attendance, and generates signed university PDFs:
```python
def get_student_counselling_dossier(student):
    """Aggregates demographic, family, semester marks & SGPA, attendance %, and backlogs."""
    # Semester marks and SGPA computation using R23 grade points
    grade_points_map = {'S': 10, 'A': 9, 'B': 8, 'C': 7, 'D': 6, 'E': 5, 'F': 0, 'Ab': 0}
    # Builds structured semester_reports list, cumulative CGPA, credits earned, and attendance breakdown...
    return dossier

def generate_counselling_report_pdf(student):
    """Generates official multi-page A4 PDF using ReportLab with NumberedCanvas page numbering."""
    dossier = get_student_counselling_dossier(student)
    # Renders official university header, demographics table, KPI summary,
    # semester marks & attendance breakdown tables, achievements, and 4-tier signature blocks.
    doc.build(elements, canvasmaker=NumberedCanvas)
    return buffer.getvalue()
```


