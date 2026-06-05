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
│   ├── models.py         # Branch, Section, Subject, Timetable, Attendance, Exam, Result, Notification models
│   ├── notification_views.py # Notices CRUD logic (compose, edit, delete notifications)
│   └── management/commands/ # Custom Python terminal management tasks
│
├── admin_dashboard/      # Administrator Management App
│   ├── urls.py           # Admin URL routes
│   └── views.py          # Admin logic (backups, PDF rendering, student/faculty CRUD)
│
├── hod/                  # Head of Department App
│   └── views.py          # HOD scoped actions (release results, assign teachers, verify achievements)
│
├── deo/                  # Data Entry Operator App
│   └── views.py          # Branch-scoped student entries & attendance uploads (1-day limit)
│
├── student/              # Student Panel App
│   └── views.py          # Dashboard view, results lists, and AI attendance estimator
│
├── faculty/              # Teaching Staff App
│   └── views.py          # Attendance sheets, marks uploading, and student advisor views
│
├── templates/            # HTML Template Registry (inheriting core/base.html glassmorphic styling)
│   ├── admin_dashboard/  # Backup dashboard, student bulk upload, staff managers
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
