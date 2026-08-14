# VVITU Portal — Complete ERP System
### Vasireddy Venkatadri International Technological University, Nambur, Guntur

A production-grade college ERP web application built with Django, featuring a glassmorphism UI, role-based access control, AI attendance prediction, multi-role leave management, student backlog tracking, dark/light theme switching, Excel/PDF exports, automatic cloud seeding, and scalability for 300,000+ concurrent students.

---

## 🚀 Key Features

*   **Role-Based Access Control**: Highly secure dashboard routing for **Students, Faculty, HODs, DEOs, and Admin** — each with tailored sidebar navigation, scoped permissions, and dedicated action portals.
*   **Multi-Role Leave Management System**:
    *   **Faculty Leave Applications**: Faculty members can apply for leave (Casual, Medical, Duty, Loss of Pay) with custom date ranges, reasons, and proxy substitution notes.
    *   **Dual Approval Workflow**: Leave requests are submitted simultaneously to the Department HOD and College Administration (Admin). Either authority can approve or reject the request.
    *   **HOD Leave Applications**: HODs can also apply for leave directly from their portal, routed exclusively to College Administration (Admin) for approval.
    *   **Multi-Channel Notifications**: Real-time dispatch of In-App notifications (with bell badge counter), HTML Emails, and Fast2SMS alerts to HODs and Admins upon leave submission.
*   **Student Active Backlogs Tracking**:
    *   **Dynamic Backlog Engine**: Evaluates released semester final results to identify active backlogs (failing grades `F`, `Ab`, `AB`, `FAIL` or marks < 40) that have not been cleared in subsequent attempts.
    *   **Conditional High-Visibility Card**: Rendered ONLY for students with active backlogs across Student Profile (`/accounts/profile/`), Student Results (`/student/results/`), and Admin/HOD/Faculty Detail Views (`/accounts/student/<id>/detail/`).
    *   **Total Backlogs Counter & Subject Breakdown**: Displays a prominent `Total Backlogs: N` header badge alongside a structured subject table (Subject Code, Subject Name, Exam/Semester, Marks, Grade, Status).
*   **Dynamic Dark & Light Mode Theme Engine**:
    *   **Theme Switcher**: Instant theme toggle with localStorage persistence (`data-theme="light"` / `data-theme="dark"`).
    *   **100% High-Contrast Accessibility Overrides**: CSS token variables (`var(--text-primary)`, `var(--text-secondary)`) ensure crisp, legible typography in both modes without invisible white-on-white text issues.
    *   **Interactive Calendar Picker Symbols**: Custom CSS filters (`hue-rotate`) turn native date/month picker icons into bright crimson icons with hover scale animations and `pointer-events: auto`.
*   **Timetable & Saturday Class Allocation**:
    *   Full support for Monday–Saturday timetable scheduling. Includes room/lab location badges (e.g. "Block C - Room 305") and faculty class allocations.
*   **Comprehensive Password Management**: Self-service password change (`/accounts/change-password/`) restricted to authorized roles (Admin, HOD, DEO). Students and Faculty are prevented from self-service password changes, requiring resets via Admin/HOD/DEO management tools.
*   **Faculty Attendance & Daily Tracking**: Allows HODs and Admins to monitor and log daily faculty attendance (`Present`, `Absent`, `On Leave`, `Official Duty`) with check-in timestamps and remarks. Faculty members can review their monthly attendance summary.
*   **College-Wide Class Proxy & Substitution Audit (Admin & HOD)**:
    *   **Cross-Branch Proxy Allocation**: Administrators have complete college-wide control to assign substitute faculty across any academic department, while HODs manage substitutions within their branch.
    *   **Conflict-Free Substitute Availability Engine**: Real-time AJAX calculation filters faculty members with zero scheduling collisions, no existing proxy assignments, and no active leaves for that period.
    *   **Automated Multi-Channel Dispatch**: Instantly triggers Fast2SMS, transactional Email, and in-app bell notifications to the assigned substitute teacher.
*   **Syllabus & Unit Coverage Progress Tracker (Admin & HOD)**:
    *   **Unit-Level Tracking (Units 1–5 + Revision)**: Every class discussion log tags the specific syllabus unit covered by the instructor.
    *   **HOD Department-Scoped Overview (`/hod/class-diary/`)**: Branch heads can monitor faculty topic discussions, unit coverage completion pills (U1..U5 with done/pending indicators), syllabus progress percentage (0-100%), and latest topic dates across all branch teaching assignments.
    *   **Admin College-Wide Audit (`/admin-portal/class-diary/`)**: University Administrators have full institutional visibility across all 11 branches with real-time branch filters, institutional syllabus completion metrics, and chronological lecture logs feed.
*   **Faculty Class Discussion Logs & Student Class Diary (`ClassDiary` Model)**:
    *   **Optional Attendance Logging**: Teaching staff can optionally enter the syllabus unit, topics covered, lecture concepts discussed, and homework/reading assignments directly while marking attendance.
    *   **Dedicated Faculty Management Panel (`/faculty/class-diary/`)**: Full CRUD interface for teachers to create, backfill, search, edit, or delete lesson notes.
    *   **Student Daily Lesson Feed (`/student/class-diary/`)**: Students can review what was taught day-by-day in their section, search topic keywords, and check homework tasks, accompanied by a dynamic dashboard overview widget.
*   **Comprehensive Student Counselling Dossier & Official PDF Export (`core/counselling_utils.py`)**:
    *   **Unified Holistic Record**: Aggregates demographic info, family details, parent occupation & contact, permanent & present address, pending tuition fee status, semester-by-semester exam marks (Mid 1, Mid 2, Final Exam, total scores, letter grades, grade points, credits, and SGPA per semester), cumulative CGPA, total credits earned, active backlogs, semester-by-semester subject attendance records, verified achievements, and counsellor periodic remarks.
    *   **Multi-Portal Access Control**: Accessible to students (`/student/counselling-report/`), faculty counsellors and class teachers (`/faculty/student/<id>/counselling-report/`), HODs across their branch (`/hod/students/<id>/counselling-report/`), and Administrators college-wide (`/admin-portal/students/<id>/counselling-report/`).
    *   **Official ReportLab PDF Engine**: Generates multi-page A4 PDF documents with university crest, confidential watermarks, tabular academic and attendance sheets, and 4-tier signature blocks (Student, Counsellor, HOD, Principal) for physical accreditation audits.
*   **Resilient Multi-Format Date Parsing Engine (`core/transfer_utils.py`)**: `parse_flexible_date()` handles standard ISO dates, human-friendly Flatpickr dates (`Fri, 14 Aug 2026`), and multiple calendar formats seamlessly across all AJAX views and forms.
*   **HOD Dashboard & Dual Panel**: Allows Heads of Departments to view departmental stats, assign faculty to subjects/classes, designate counselors/class teachers, manage and publish branch timetables, approve student/faculty achievements, and toggle between HOD administration and Faculty teaching panels.
*   **DEO Dashboard**: Enables Data Entry Operators to add/edit students within their assigned branch, upload marks, and edit attendance records within a strict **1-day editing window** (older edits require HOD authorization).
*   **Unified Notices Board System**: Multi-scoped notifications system allowing Admin, HODs, and DEOs to compose and manage notices targeted to everyone, specific roles, specific branches, specific classes, or single users with quick navbar shortcuts.
*   **Parent & Student SMS Integration**: Utility module (`core/sms_utils.py`) for sending Fast2SMS alerts for absences, exam results, and leave requests.
*   **First-Time Password Flow**: Automatically forces students to set a custom, permanent password on their first login.
*   **Glassmorphism & Cinematic UI**: Fully responsive dark/light mode visual design built with custom CSS tokens, backdrop blur effects, animated gradients, and smooth micro-animations.
*   **Bulk CSV Uploads**: Instantly upload spreadsheets to create thousands of student profiles and populate test marks.
*   **Excel & PDF Export**: Download dynamically generated attendance reports on demand via openpyxl and ReportLab.
*   **Enterprise Security Hardening & Web Application Firewall (WAF)**:
    *   **Global Security Payload Sanitizer (`SecuritySanitizerMiddleware`)**: Intercepts all incoming GET and POST parameters to block SQL Injection (SQLi), Cross-Site Scripting (XSS), Path Traversal (LFI), and Command Injection attack vectors with HTTP 403 Forbidden responses.
    *   **Security Headers Engine (`GlobalSecurityHeadersMiddleware`)**: Automatically injects mandatory security headers (`X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, `X-XSS-Protection: 1; mode=block`, `Permissions-Policy`, `Cross-Origin-Opener-Policy: same-origin`).
    *   **Brute-Force & Credential-Stuffing Defense (`LoginRateLimitMiddleware`)**: Locks out client IPs after 5 failed login attempts in 60 seconds and username targets after 10 failed attempts in 120 seconds.
    *   **Strict Session Hardening**: Enforces `SESSION_COOKIE_HTTPONLY`, `SESSION_COOKIE_SAMESITE='Lax'`, `CSRF_COOKIE_HTTPONLY`, `SESSION_EXPIRE_AT_BROWSER_CLOSE=True`, and 4-hour automatic session timeouts.
*   **AI Attendance Predictor**: Utilizes scikit-learn linear regression to analyze student records and predict semester attendance outcomes.
*   **PostgreSQL Sequence Synchronizer**: Automated script (`scratch/fix_postgres_sequences.py`) to align PostgreSQL primary key sequences with table max IDs, preventing primary key collision errors in production.

---

## 🛠️ Technology Stack

- **Backend**: Django 4.2 (Python 3.11+)
- **Frontend**: Bootstrap 5, Chart.js 4, Font Awesome 6, Vanilla CSS Tokens
- **Database**: SQLite (Development) — PostgreSQL (Production)
- **Caching**: Django LocMemCache (Dev) — Redis (Production)
- **AI / ML**: scikit-learn (Linear Regression for attendance prediction)
- **Exports**: openpyxl (Excel Reports), ReportLab (PDF Certificates & Sheets)
- **Notifications**: Fast2SMS API & Django SMTP Email Handler

---

## 📂 Project Structure

```
VVITU_Portal/
├── VVITU_Portal/          # Django project config
│   ├── settings.py       # Base settings
│   ├── settings_prod.py  # Production settings overrides (HSTS, SSL, Cache)
│   ├── urls.py           # Root URL routing
│   └── middleware.py     # Role-based access and Login Rate Limiter
│
├── accounts/             # Custom User, Student, Faculty, DEOProfile, Achievement models
│   ├── models.py         # User, Student (get_backlogs, total_backlogs_count), Faculty, DEO, Achievement
│   ├── views.py          # Session auth, profiles, password reset flows
│   └── profile_detail_views.py  # Read-only student & faculty detail views for Admin/HOD
│
├── core/                 # Shared academic models, notifications centre, and tasks
│   ├── models.py         # Branch, Section, Subject, Timetable, ClassDiary, FacultyAttendance, FacultyLeaveRequest, Result, Notification
│   ├── notification_views.py # Full notifications CRUD — compose, manage, delete
│   ├── sms_utils.py      # Fast2SMS SMS notification dispatcher
│   └── transfer_utils.py # Free faculty calculator, flexible date parser & class history engine
│
├── student/              # Student dashboard, class diary, results summary, backlogs alert, past papers
├── faculty/              # Mark attendance, class diary, reports, leave applications, class transfers, marks upload
├── admin_dashboard/      # Admin settings, staff management, global CRUD, proxy audit, leave request approvals
├── hod/                  # HOD department manager, approvals, leave applications, timetable editors
├── deo/                  # DEO branch lists, attendance records, upload pages
│
├── templates/            # HTML templates (extends core/base.html)
│   ├── core/base.html    # Master layout: navbar, sidebar, theme switcher, notifications dropdown
│   ├── accounts/         # Profile details, student backlogs card, first-time password reset
│   ├── student/          # Dashboard, class_diary.html, results, backlogs banner, calendar, past papers
│   ├── faculty/          # Dashboard, class_diary.html, attendance sheet, leave requests, reports, marks upload
│   ├── admin_dashboard/  # Admin staff/student managers, class_diary_coverage.html, faculty_class_history.html, leave approvals, bulk CSV
│   ├── hod/              # HOD department manager, class_diary_coverage.html, manage_class_transfers.html, approvals, timetable editors
│   └── deo/              # DEO branch lists, attendance records, upload pages
│
├── static/
│   ├── css/main.css      # Glassmorphism design system & core button styles
│   ├── css/theme_and_calendar.css # Light/Dark theme token overrides & calendar icon styling
│   ├── js/main.js        # Theme switcher, sidebar, Flatpickr, AJAX utilities
│   └── images/           # Logo files & graphics
│
├── scratch/
│   ├── audit_templates.py    # Template syntax audit script (0 errors across 75 templates)
│   ├── test_all_views.py     # Automated route testing script (100% 200 OK across 50+ routes)
│   └── fix_postgres_sequences.py # PostgreSQL primary key sequence synchronizer
│
├── sample_data.py        # Database seeding script (runs automatically on cloud setup)
├── render.yaml           # One-click Render Blueprint Deployment config
└── requirements.txt
```

---

## ⚡ Step-by-Step Setup

### Step 1 — Create and activate a virtual environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux / macOS
python3 -m venv venv
source venv/bin/activate
```

### Step 2 — Install dependencies

```bash
pip install -r requirements.txt
```

### Step 3 — Apply migrations and seed sample database

```bash
python manage.py migrate
python manage.py shell -c "import sample_data; sample_data.run()"
```

### Step 4 — Run sequence synchronizer (PostgreSQL)

```bash
python scratch/fix_postgres_sequences.py
```

### Step 5 — Run local development server

```bash
python manage.py runserver
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000) in your browser.

---

## 🔑 Default Login Credentials

| Role | Username / Portal ID | Password | Access Level |
| :--- | :--- | :--- | :--- |
| **System Admin** | `admin` | `admin123` | Full Global Access |
| **HOD (CSE)** | `EMP001` | `vvit1234` | CSE Department Administration + Teaching |
| **Faculty** | `EMP002` | `vvit1234` | Mark Attendance, Reports, Apply Leaves |
| **DEO (CSE)** | `DEO001` | `vvit1234` | CSE Student Entries & Marks Upload |
| **Student** | `24BQ1A4901` | `student123` | Student Dashboard, Results, Backlogs |

---

## 🔧 Quality Verification & Automated Testing

This repository includes custom verification harnesses:

1. **Django System Check**:
   ```bash
   python manage.py check
   ```
   *Result*: `System check identified no issues (0 silenced).`

2. **Template Syntax Auditor**:
   ```bash
   python scratch/audit_templates.py
   ```
   *Result*: `SUCCESS: All 75 templates compiled with 0 syntax errors!`

3. **Automated Route Test Suite**:
   ```bash
   python scratch/test_all_views.py
   ```
   *Result*: `ALL 50+ PROJECT ROUTES PASSED 100% WITH STATUS 200 OK!`

---

## 🚀 Cloud Deployment (Render Blueprint)

This repository is pre-configured with a `render.yaml` blueprint for one-click deployments:
1. Push this codebase to your GitHub account.
2. Link your GitHub account to [Render](https://render.com).
3. Select the blueprint on Render, which will automatically spin up:
   * A Python web service container running `gunicorn`.
   * A managed PostgreSQL database.
   * Auto-run migrations and auto-seed sample testing accounts.
4. Access your live website URL once the build finishes!

---

*Built for VVITU — Nambur, Guntur District, Andhra Pradesh*
