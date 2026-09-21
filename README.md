# VVITU Portal — Complete ERP System
### Vasireddy Venkatadri International Technological University, Nambur, Guntur

A production-grade college ERP web application built with Django, featuring a glassmorphism UI, role-based access control, AI attendance prediction, multi-role leave management, student backlog tracking, dark/light theme switching, Excel/PDF exports, automatic cloud seeding, and scalability for 300,000+ concurrent students.

---

## 🚀 Key Features

*   **Role-Based Access Control**: Highly secure dashboard routing for **Students, Faculty, HODs, DEOs, and Admin** — each with tailored sidebar navigation, scoped permissions, and dedicated action portals.
*   **Faculty Monthly Leave Quotas & Emergency Over-Limit System**:
    *   **Customizable Leave Limits**: Administrators can set individual monthly leave quotas per faculty member (default: 2 days/month).
    *   **Live Balance Tracker**: Faculty can see their current month's total limit, days used, and remaining balance directly when applying.
    *   **Emergency Leave Processing**: Applications exceeding the monthly limit are automatically tagged as `EMERGENCY LEAVE`, notifying HOD and Admin with high-priority alerts.
    *   **Red Emergency Approval Cards**: Applications exceeding limits are visually highlighted with bright red cards and warning badges across HOD and Admin review dashboards.
*   **Subject Syllabus Topic Timetable & Exam Milestones System**:
    *   **Topic Schedule Plan Editor (HOD & Admin)**: Unit-by-unit (Units 1 to 5) curriculum scheduler with target completion dates, sequence ordering, and milestone tags (`mid1`, `mid2`, `final`).
    *   **Exam Milestones & Target Unit Requirements**: Configurable exam timetables (Mid-1, Mid-2, Semester Final) with mandatory syllabus completion targets (e.g. **2.5 units before Mid-1**, 5.0 units before Mid-2) and faculty completion deadlines.
    *   **Auto-Matching with Attendance & Class Diary**: When faculty mark daily attendance and log taught topics in the Class Diary, the system fuzzy-matches the topic name against the planned syllabus and automatically marks it completed with timestamp and teacher credentials.
    *   **Faculty Syllabus Tracker (`/faculty/syllabus-tracker/`)**: Interactive unit-by-unit checklist with progress bar, Mid-1 milestone compliance box, and live AJAX complete/undo toggle.
    *   **Student Syllabus Coverage Tracker (`/student/syllabus/`)**: Enables students to transparently monitor which topics have been covered in class, remaining units, and upcoming topics before Mid-1/Mid-2 exams.
    *   **Strict Targeted Notifications**: Incomplete/overdue topics or delayed Mid-1 milestones trigger In-App, Email, and SMS reminders **strictly to the respective Faculty and Department HOD** (Admin receives zero routine topic delay notifications).
*   **HOD Dual Role & Admin-Only Leave Approvals**:
    *   **Full Teaching Access for HODs**: HODs who teach subjects have direct access to all regular faculty features: Mark Attendance, Class Diary, My Syllabus Tracker, Attendance Reports, Class Transfers (Proxy), and Counselled Students.
    *   **HOD Dashboard "My Teaching" Hub**: Displays today's teaching schedule with classroom locations, quick Mark buttons, and faculty action shortcuts directly on the HOD dashboard.
    *   **Admin-Only HOD Leave Approvals**: When an HOD applies for leave, the application is strictly routed to **College Administration (Admin)** for approval. HODs are blocked from self-approving their own leave.
    *   **Admin HOD Leave Queue**: Admin dashboard features dedicated filter tabs (`All`, `👑 HOD Leaves Only`, `⚠️ Emergency Leaves Only`, `Regular Faculty`) with prominent HOD badges and 1-click approvals.
*   **Real-Time Class Transfer, Proxy Conduction & Attendance Sync**:
    *   **Peer Substitutions & Official Proxies**: Full support for both mutual faculty peer substitutions and official HOD/Admin proxy designations.
    *   **Instant Substitute Attendance Authorization**: Substitute faculty can immediately mark attendance for assigned proxy slots. Attendance rows record `marked_by = substitute_faculty`, and `ClassTransfer` automatically transitions to `completed`.
    *   **Instant Reversion / Cancellation**: HODs and Administrators can cancel any active transfer with 1 click (`cancel_proxy`), immediately restoring the regular instructor in all timetables and audits.
*   **Department & Institutional Faculty Class Attendance Audit Consoles**:
    *   **HOD Audit Console (`/hod/faculty-class-audit/`)**: Period-by-period class conduction matrix with live compliance %, attendance submitted counts, unmarked class alerts, proxy tags, and printable period registers.
    *   **Admin Institutional Audit Console (`/admin-portal/faculty-class-audit/`)**: University-wide class conduction matrix across all 11 branches with branch filtering, biometric faculty presence cross-checks, and syllabus topic notes.
    *   **Deep-Dive Class Session Audit (`class_attendance_detail`)**: Full student roster breakdown (Present/Absent/Leave), teacher-in-class identification, and lesson discussion summaries.
*   **Student Academic Detention & Junior Readmission Resolution Workflow**:
    *   **Automated Detention Tagging**: Detects and tracks students detained due to attendance shortage (<65%) or credit shortage.
    *   **Junior Batch Readmission Portal**: Students apply for junior batch readmission (`StudentReadmissionRequest`) with previous & target junior year/section mappings.
    *   **Two-Tier Approval & Execution**: Department HOD recommends approval, and University Administration executes reassignment, updating student year/section, clearing detention flags, and dispatching SMS alerts.
*   **Student On-Duty (OD) & Medical Leave Attendance Exemption Engine**:
    *   **Student Leave Portal (`/student/leaves/apply/`)**: Enables students to apply for Medical, OD (Hackathons/Sports/Conferences), and Personal leaves with document attachments.
    *   **Automatic Historical Attendance Exemption**: Approved OD/Medical leaves automatically convert all historical attendance records within the date range from `Absent ('A')` to `Leave ('L')`, safeguarding examination eligibility.
*   **Official ReportLab PDF Generation Engines (`core/pdf_utils.py` & `core/counselling_utils.py`)**:
    *   **Student Monthly Attendance Report PDF (`/student/attendance/monthly-pdf/`)**: Official monthly attendance summary with subject-wise percentages, OD exemptions, and university seal.
    *   **Semester Grade Card Marksheet PDF (`/student/results/grade-card-pdf/`)**: Official university grade card with course credits, internal/external scores, letter grades, SGPA, CGPA, and Registrar signatures.
    *   **Student Counselling Dossier PDF (`/student/counselling-report/pdf/`)**: Multi-page A4 dossier with demographic cards, semester marks sheets, attendance records, and 4-tier signature blocks.
    *   **Consolidated Database Audit Report PDF (`/admin-portal/export/database-pdf/`)**: Comprehensive institutional snapshot including student registry, faculty staff, curriculum, student CGPA summaries, active exam milestone schedules, and faculty monthly leave quotas.
    *   **Student Results & Attendance PDF Exports**: Exportable on-demand for academic audits and record keeping.
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
*   **Cyber Neon Glowing Timetable Experience**:
    *   **Dynamic Active Day Column Glow (`#00e676` / `#10b981`)**: Auto-detects the current day of the week, illuminating the active day column in vibrant neon green with glowing borders and badges.
    *   **Real-Time Interactive Day Switcher**: Click any day header (`MONDAY` through `SATURDAY`) to dynamically shift the green neon column instantly with zero page reload.
    *   **Universal Deployment Across All Schedule Views**: Unified across Faculty Dashboard (`/faculty/`), Faculty Timetable (`/faculty/timetable/`), Student Timetable (`/student/timetable/`), HOD Timetables (`/hod/timetable/`), Admin Timetables (`/admin-portal/timetable/`), and DEO Timetables (`/deo/timetable/`).
    *   **Dual-View Mode & Break Rows**: Integrated rows for Morning Break, Tea Break, and Lunch Break (`🍴 REFRESHMENT & LUNCH BREAK ☕`), with toggle between interactive Cyber Glow View and clean Paper Document View (`@media print` black-and-white for A4 institutional printing).
*   **Student Feedback & Institutional Questionnaire Platform (`core/feedback_service.py`)**:
    *   **Targeted Questionnaire Scoping**: Admin and HODs can create feedback forms scoped to Branch, Year, Semester, and Section.
    *   **Official Document Attachments**: Upload and attach physical questionnaire templates (Photo JPG/PNG or PDF).
    *   **1-Click Questionnaire Presets**: 10-Point Faculty Teaching Evaluation, 5-Point Course & Curriculum Feedback, 6-Point Campus Infrastructure & Facilities.
    *   **Online Digital 5-Star Submissions**: Interactive 5-star rating inputs with real-time score indicators, text comments, and single-submission enforcement.
    *   **Offline Physical Questionnaire Workflow**: Download blank official printable PDF forms (`generate_feedback_blank_printable_pdf`) for physical paper completion.
    *   **Authenticated Student Summary PDF (`generate_student_feedback_summary_pdf`)**: Students can download an authenticated summary PDF with a unique reference number (`VVIT/FB/2026/XXXXX`) and digital seal.
    *   **HOD & Admin Analytics Dashboard (`generate_feedback_analytics_pdf`)**: Real-time statistical analysis with question-by-question averages, satisfaction %, star breakdown, and downloadable PDF report.
    *   **100% Dark Glassmorphic Styling**: Full visual integration across all 7 feedback views adhering to the portal dark theme.
*   **Proxy Class Request & Single-Period Faculty Collision Engine (`core/timetable_service.py`)**:
    *   **Two-Way Substitute Approval**: Substitute faculty receive in-app notifications with Accept and Decline actions; timetables and audits update only upon confirmation.
    *   **Single-Period Faculty Constraint**: Prevents faculty from having more than one class at the same time slot across all branches/sections.
    *   **Interactive Modal Conflict Resolution**: "Fix That Period & Remove Past Period" vs "Fix Only Past Period".
*   **Comprehensive Security & Reliability Hardening**:
    *   **Strict File Upload Validation (`core/file_validators.py`)**: Whitelist enforcement (`.pdf`, `.jpg`, `.jpeg`, `.png`), 5MB size limits, and binary magic-byte inspection (`%PDF-`, `\xff\xd8\xff`, `\x89PNG\r\n\x1a\n`) preventing disguised file uploads and MIME spoofing.
    *   **Private Media Delivery Architecture (`core/views_media.py`)**: Sensitive documents (student medical certificates, feedback attachments) routed through authenticated, role-authorized views with `X-Content-Type-Options: nosniff`.
    *   **XSS Elimination in Dynamic UI**: Eliminated `innerHTML` injection in timetable upload previews and dynamic attendance marking rows by constructing DOM nodes safely with `textContent` and URL encoding.
    *   **Memory & Upload Bounds**: Enforced 5MB size limits before reading uploads into RAM; configured `DATA_UPLOAD_MAX_MEMORY_SIZE` and `FILE_UPLOAD_MAX_MEMORY_SIZE` to 5MB in `settings.py`.
    *   **Anti-DoS Login Rate Limiting (`middleware.py`)**: Bound throttling to canonical `REMOTE_ADDR`, incrementing failed attempts only on authentication failure (HTTP 200) and clearing on success (HTTP 302) to prevent attacker-driven account lockouts.
    *   **Production Configuration Fail-Safe**: Fails fast with `ImproperlyConfigured` if `DEBUG=False` with the fallback secret key. Secure cookie flags and HTTPS redirects activate automatically in production.
    *   **Non-Blocking WAF Telemetry**: Routes suspicious SQL query keywords into audit logging telemetry without falsely blocking legitimate academic curriculum text.
    *   **Persistent Static Asset Caching**: `APP_VERSION = '2.5.0'` via `core/context_processors.py` replaces per-request timestamps, restoring browser and CDN caching.
    *   **Accessibility & Reduced Motion**: Added `@media (prefers-reduced-motion: reduce)` in `login.css` and optimized floating background layers for mobile devices (`@media (max-width: 768px)`).
*   **Official ReportLab PDF Generation Engines (`core/pdf_utils.py`)**:
    *   **Student Monthly Attendance PDF** (`generate_monthly_attendance_pdf`)
    *   **Semester Grade Card Marksheet PDF** (`generate_semester_grade_card_pdf`)
    *   **Student Feedback Summary PDF** (`generate_student_feedback_summary_pdf`)
    *   **Blank Printable Feedback Form PDF** (`generate_feedback_blank_printable_pdf`)
    *   **Consolidated Feedback Analytics PDF** (`generate_feedback_analytics_pdf`)
    *   **Student Counselling Dossier PDF** (`generate_counselling_report_pdf`)
*   **VBot AI Study Assistant (Google Gemini 1.5 Flash)**:
    *   **Context-Aware Student Chatbot**: Integrated conversational study widget providing instant curriculum guidance, study schedules, and exam rules tailored to each student's branch, year, semester, and enrolled subjects.
    *   **One-Variable Activation (`GEMINI_API_KEY`)**: Activates automatically by setting a free Gemini API key in `.env`; gracefully falls back with helpful guidance if unconfigured.
    *   **Multimodal Schedule Extraction**: Supports automated timetable document parsing using Google Gemini Vision API.
*   **College Bulk Data Ingestion (Students, Marks & Timetables)**:
    *   **Bulk CSV Student Admissions (`/admin-portal/upload-students/`)**: Rapidly ingests student rosters from CSV/Excel, generating User accounts and assigning sections with zero manual entry.
    *   **Exam Marks Ingestion**: Batch upload of Mid-1, Mid-2, Internal Lab, and Semester Final marks via `/faculty/upload-marks/` or DEO portal.
    *   **Drag-and-Drop Timetable Ingestion**: Instant schedule upload with client-side modal preview and faculty period conflict checking.
    *   **PostgreSQL Sequence Synchronizer**: Script (`scratch/fix_postgres_sequences.py`) to align PostgreSQL primary key sequences with table max IDs, preventing primary key collision errors in production.
*   **Recent Stability Hardening & Bug Fixes (September 2026)**:
    *   **Counselling Dossier PDF (`core/counselling_utils.py`)**: Fixed missing `import os` causing `NameError` on profile picture retrieval. Guarded marks percentage calculations against `None`/`TypeError`.
    *   **Student Views (`student/views.py`)**: Removed invalid `is_deleted=False` lookups on `Year` and `Section` models, eliminating `FieldError` and unexpected error redirects. Imported `FeedbackQuestion` and initialized logger. Handled unsubmitted feedback gracefully in summary and PDF export views.
    *   **HOD Views (`hod/views.py`)**: Corrected `AcademicCalendar` query date delta from undefined `datetime.timedelta(days=30)` to `dt.timedelta(days=30)`. Simplified comprehension in `marked_by_fac_map`.
    *   **Admin & DEO Views**: Removed dead unreachable code in `admin_dashboard/views.py` and redundant duplicate redirects in `deo/views.py`.
    *   **Exception Middleware (`VVITU_Portal/middleware.py`)**: Refined `GlobalExceptionRedirectMiddleware` so standard `Http404` and `PermissionDenied` propagate cleanly instead of converting to unexpected error redirects.
    *   **Template Colspans**: Fixed table column alignment in empty states for `manage_students.html` (10) and `manage_faculty.html` (8) across HOD and Admin portals.
*   **Secure Student Account Onboarding & Automated Credentials Dispatch (Method 2)**:
    *   **Cryptographic Temporary Password Generator**: `generate_secure_temp_password()` uses `secrets.choice` across upper/lower letters, digits, and symbols to generate secure, unguessable temporary passwords upon student account creation, eliminating all static hardcoded passwords.
    *   **Automated Welcome Email Delivery (`accounts/email_utils.py`)**: Immediately on student creation (Single Admin/HOD/DEO creation or Bulk CSV Ingestion), dispatches a personalized welcome email containing Roll Number, Temporary Password, Portal Login URL, and first-time instructions.
    *   **Mandatory First-Time Password Change**: Flags newly created students with `force_password_change = True`, requiring students to choose a secure, private permanent password immediately upon initial login before accessing academic tools.
*   **Academic Calendar Event Notification & Attendance Daemon (`core/management/commands/`)**:
    *   **Upcoming Event Reminders (`send_event_reminders`)**: Automated management command scanning university events within the 24-hour window, dispatching targeted in-app bell notices and emails to students, faculty, and HODs.
    *   **Low Attendance Warning Engine**: Scans student attendance rates, automatically dispatching warning notices and parental emails to any student falling below the 75% university eligibility threshold.
*   **Production Deployment Hardening & Security Assurance**:
    *   **Zero Fallback Secret Key**: `settings_prod.py` raises `django.core.exceptions.ImproperlyConfigured` immediately on startup if `SECRET_KEY` is not provided in environment variables, guaranteeing production never boots with a weak fallback key.
    *   **CSRF-Protected POST-Only Logout**: Enforced `@require_POST` on `/accounts/logout/` and wired `#globalLogoutForm` across all navbar, sidebar, and dock power-off buttons, preventing cross-site GET logouts.
    *   **Strict WhiteNoise Static Manifest**: Configured `WHITENOISE_MANIFEST_STRICT = True` across development and production, catching missing or misnamed static files at build/collection time.
    *   **Static Application Security Testing (SAST) & Audit**: Project toolchain integrates `bandit` (0 High, 0 Medium issues across 20,362 lines of code) and `pip-audit` (0 known dependency vulnerabilities).
*   **AI Attendance Predictor**: Utilizes scikit-learn linear regression to analyze student records and predict semester attendance outcomes.

---

## 🛠️ Technology Stack

- **Backend**: Django 5.2 LTS (Python 3.11 – 3.14)
- **Frontend**: Bootstrap 5, Chart.js 4, Font Awesome 6, Vanilla CSS Tokens
- **Database**: SQLite (Development) — PostgreSQL 14+ (Production)
- **Static Assets**: WhiteNoise 6.9+ (Strict Manifest Storage)
- **Security & SAST**: Bandit 1.8+, pip-audit 2.7+, Django Cryptographic Signer & Secrets Engine
- **Caching**: Django LocMemCache (Dev) — Redis (Production)
- **AI / ML**: Google Gemini 1.5 Flash (VBot) & scikit-learn (Linear Regression)
- **Exports**: openpyxl (Excel Reports), ReportLab (PDF Certificates & Sheets)
- **Notifications**: Fast2SMS API & Django SMTP Transactional Email Handler

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
| **System Admin** | `admin` | `admin123` | Full Global Institutional Control |
| **HOD (CSE)** | `HOD001` / `hod001` | `vvit@1234` | CSE Department Administration + Teaching Panel |
| **HOD (ECE)** | `HOD002` / `hod002` | `vvit@1234` | ECE Department Administration + Teaching Panel |
| **Faculty** | `EMP001` / `emp001` | `vvit@1234` | Mark Attendance, Class Diary, Syllabus Tracker, Proxy |
| **DEO (CSE)** | `DEO001` / `deo001` | `vvit@1234` | CSE Branch Student Management & Marks Entry |
| **Student (Demo)** | `24BQ1A4942` / `24bq1a4942` | `vvit@1234` | Student Dashboard, Results, Backlogs, OD Leaves |

> **Student Account Onboarding & First-Time Login (Method 2)**:
> - Seeded demo accounts use the initial password `vvit@1234`.
> - In live production, when a new student account is registered (via Admin, HOD, DEO, or Bulk CSV upload), the system automatically generates a unique cryptographically secure temporary password (via `generate_secure_temp_password()`) and immediately dispatches a personalized welcome email (`send_welcome_credentials_email()`) containing their Roll Number, Temporary Password, and Portal Login URL.
> - Upon their very first login, students are required (`force_password_change = True`) to set a private, permanent password before accessing academic services.

---

## 🔧 Quality Verification & Automated Testing Suite

The repository features an enterprise-grade automated testing and security audit suite:

### 1. Complete 10-Tier Master Test Suite (`run_vvitu_test_suite.py`)
Run the unified 10-tier test suite across all architectural layers against an isolated test database:

```bash
python run_vvitu_test_suite.py
```

```
                          VVITU PORTAL
                               │
                               ↓
                      ┌─────────────────┐
                      │ Unit Testing    │  [PASS] 14 Tests (8.53s)
                      └────────┬────────┘
                               ↓
                      ┌─────────────────┐
                      │ Integration     │  [PASS] 3 Tests (4.90s)
                      │ Testing         │
                      └────────┬────────┘
                               ↓
                      ┌─────────────────┐
                      │ Functional      │  [PASS] 5 Tests (26.54s)
                      │ Testing         │
                      └────────┬────────┘
                               ↓
                      ┌─────────────────┐
                      │ System Testing  │  [PASS] 4 Tests (0.23s)
                      └────────┬────────┘
                               ↓
                      ┌─────────────────┐
                      │ Security        │  [PASS] 6 Tests (6.64s)
                      │ Testing         │
                      └────────┬────────┘
                               ↓
                      ┌─────────────────┐
                      │ Performance     │  [PASS] 3 Tests (9.31s)
                      └────────┬────────┘
                               ↓
                      ┌─────────────────┐
                      │ Compatibility   │  [PASS] 4 Tests (4.53s)
                      └────────┬────────┘
                               ↓
                      ┌─────────────────┐
                      │ Regression      │  [PASS] 4 Tests (4.22s)
                      └────────┬────────┘
                               ↓
                      ┌─────────────────┐
                      │ UAT             │  [PASS] 3 Tests (9.00s)
                      └────────┬────────┘
                               ↓
                      ┌─────────────────┐
                      │ Enterprise      │  [PASS] 14 Tests (42.19s)
                      │ Issue Audit     │
                      └─────────────────┘

TOTAL TESTS EXECUTED : 60
PASSED               : 60 (100% SUCCESS)
FAILED / ERRORS      : 0
TOTAL DURATION       : 116.13 seconds
```

### 2. Dependency Vulnerability Audit (`pip-audit`)
Scans all locked dependencies in `requirements.txt` against the PyPI Advisory Database:
```bash
python -m pip_audit -r requirements.txt
# No known vulnerabilities found
```

### 3. Static Application Security Testing (`bandit`)
Performs deep AST security scanning across all 20,000+ lines of codebase:
```bash
python -m bandit -r accounts core faculty hod admin_dashboard exam_cell dean VVITU_Portal -ll
# 0 High, 0 Medium issues found across 20,362 lines of code
```

### 4. Production Deployment Security Check
```bash
SECRET_KEY="your-prod-secret" python manage.py check --deploy --settings=VVITU_Portal.settings_prod
# System check identified no issues (0 silenced).
```

### 5. Template Syntax Auditor
```bash
python scratch/audit_templates.py
# SUCCESS: All templates compiled with 0 syntax errors!
```

---

## 🏛️ On-Campus College Server Deployment

For deploying 24/7 on an institutional Linux or Windows server machine:

1. **1-Click Linux Automated Installer**:
   ```bash
   chmod +x deploy/setup_college_server.sh
   sudo ./deploy/setup_college_server.sh
   ```
   Provisions Nginx, Gunicorn, PostgreSQL, `vvitu.service` systemd daemon, and static asset collection.

2. **Campus Wi-Fi / LAN vs Public Internet**:
   * **Intranet**: Point college router DNS (`portal.vvit.net` ➡️ Server Local IP e.g. `192.168.1.100`).
   * **Public Internet**: Forward ports 80/443 to server IP and attach Let's Encrypt SSL (`sudo certbot --nginx`).

3. **Detailed Deployment Guide**:
   * See [`DEPLOY.md`](./DEPLOY.md) for step-by-step production configuration.
   * See [`../../running_in_server_clg.txt`](../../running_in_server_clg.txt) for college IT administration reference.

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
