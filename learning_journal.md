# VVITU Portal — Learning Journal
This journal details the system design, directory structure, commands, key code constructs, technical learnings, architectural decisions, and recently added features of the VVITU ERP Portal.

---

## 1. Executive Overview & System Architecture

Adding features to a live college ERP platform requires balancing **relational integrity, role security, auditability, accessibility, and user experience**.

The VVITU Portal is architected around five distinct roles:
1. **Admin**: System-wide administrative privileges (backups, leave approvals, staff CRUD, global reports, results release).
2. **HOD**: Department-scoped administration (faculty assignment, subject mapping, timetable publishing, leave approval/application, achievement verification).
3. **Faculty**: Academic operations (marking attendance, class period transfers, uploading marks, applying for leave, viewing reports).
4. **DEO**: Data entry operations scoped to assigned branch (adding/editing students, attendance entries with a 1-day lock window, marks upload).
5. **Student**: Self-service portal (dashboard, results, active backlog tracking, attendance history, achievements submission).

---

## 2. Key Architecture Patterns & Technical Learnings

### A. Dual Approval Multi-Role Leave Management
*   **Problem:** Faculty members submit leave requests that need review by both academic heads (HOD) and executive management (Admin), while HODs themselves need a mechanism to submit leave requests to Admin.
*   **Implementation:**
    *   `FacultyLeaveRequest` model tracks `faculty`, `leave_type`, `start_date`, `end_date`, `reason`, `substitute_notes`, and `status` (`pending`, `approved`, `rejected`, `cancelled`).
    *   Faculty requests can be actioned by **either** the HOD of their department or the College Admin.
    *   HOD leave requests are routed exclusively to Admin for approval.
    *   **Multi-Channel Dispatch**: Upon submission, the system triggers In-App notifications (`Notification`), HTML email notifications (`send_mail`), and Fast2SMS alerts (`send_sms`) to relevant HODs and Admins.

### B. Dynamic Student Active Backlog Engine
*   **Problem:** Academic profiles often display raw historical grades without distinguishing active pending backlogs from cleared subjects, causing confusion for students, advisors, and registrars.
*   **Implementation:**
    *   `Student.get_backlogs()` inspects all released semester final exam results (`Result` objects where `exam.exam_type` in `['final', 'sem', 'SEM']` and `exam.release.released=True`).
    *   Filters subjects where the latest attempt has a failing/absent grade (`F`, `Ab`, `AB`, `FAIL` or `marks_obtained < 40`).
    *   `Student.total_backlogs_count` provides the integer count.
    *   **Conditional UI Rendering**: The Backlogs Card is rendered **ONLY** when `total_backlogs_count > 0` on Profile, Results, and Detail pages, keeping clean profiles clutter-free while drawing immediate attention to students with backlogs.

### C. Theme-Adaptive CSS Token Architecture & Accessibility Fix
*   **Problem:** When toggling between Dark Mode and Light Mode, hardcoded white text (`#ffffff` or `text-white`) on light cards resulted in white-on-white invisible text.
*   **Implementation:**
    *   Replaced hardcoded inline colors with CSS custom property tokens (`var(--text-primary)`, `var(--text-secondary)`, `var(--clr-surface)`).
    *   In `theme_and_calendar.css`, added explicit `[data-theme="light"] .text-white { color: #0f172a !important; }` rules, while preserving crisp white text on solid colored badges (`.badge.bg-danger`, `.btn-vvit-primary`).
    *   **Interactive Calendar Symbols**: Applied CSS `filter: invert(...)` and `pointer-events: auto; cursor: pointer;` on `.cal-icon` and `::-webkit-calendar-picker-indicator`, making native and custom date/month pickers 100% visible and clickable in both modes.

### D. PostgreSQL Primary Key Sequence Synchronization
*   **Problem:** Inserting records with hardcoded explicit IDs (during seed scripts or migrations) in PostgreSQL can leave the underlying sequence (`tablename_id_seq`) behind max(id), causing future `get_or_create` or `save()` calls to crash with `duplicate key value violates unique constraint`.
*   **Implementation:**
    *   Created `scratch/fix_postgres_sequences.py` which inspects all models in the Django project, queries `SELECT MAX(id) FROM table`, and executes `SELECT setval('table_id_seq', MAX(id))` for PostgreSQL databases.

### E. Automated Route Testing & Template Syntax Auditing
*   **Problem:** Large multi-role applications can suffer from silent template syntax errors or broken view decorators after refactoring.
*   **Implementation:**
    *   `scratch/audit_templates.py`: Compiles all 75 project templates using `django.template.loader.get_template()` to catch syntax errors.
    *   `scratch/test_all_views.py`: Uses Django `Client` to simulate authenticated GET requests across 50+ routes for Student, Faculty, HOD, DEO, and Admin roles, verifying `200 OK` status codes.

---

## 3. Directory Structure & File Roles

```
VVITU_Portal/
├── VVITU_Portal/          # Django Root Configuration
│   ├── settings.py       # Core settings (Database, Apps, Middlewares)
│   ├── settings_prod.py  # Production configuration (Security headers, SSL, caching)
│   ├── urls.py           # Root URL Router
│   └── middleware.py     # Role-based middleware & Login Brute Force protection
│
├── accounts/             # User Profile & Identity App
│   ├── models.py         # User, Student (get_backlogs, total_backlogs_count), Faculty, DEO, Achievement
│   ├── views.py          # Session auth, profiles, password reset flows
│   └── profile_detail_views.py  # Read-only student & faculty detail views
│
├── core/                 # Shared Academic Logic App
│   ├── models.py         # Branch, Section, Subject, Timetable, FacultyAttendance, FacultyLeaveRequest, Result, Notification
│   ├── notification_views.py # Notices CRUD logic
│   └── sms_utils.py      # Fast2SMS SMS notification dispatcher
│
├── admin_dashboard/      # Administrator App (leave approvals, staff CRUD, backups)
├── hod/                  # Head of Department App (leave applications, branch timetable, approvals)
├── deo/                  # Data Entry Operator App (student CRUD, attendance entries, marks)
├── student/              # Student App (dashboard, results, active backlogs banner)
├── faculty/              # Teaching Staff App (attendance, leave applications, class transfers, reports)
│
├── templates/            # HTML Template Registry (extends core/base.html)
├── static/               # CSS Design System & JavaScript utilities
├── scratch/              # Verification & maintenance scripts (audit_templates, test_all_views, fix_postgres_sequences)
└── README.md             # GitHub Project Documentation
```

---

## 4. Key Management Commands & Maintenance Tools

```bash
# 1. Django System Diagnostics
python manage.py check

# 2. Run Template Syntax Auditor (75 templates)
python scratch/audit_templates.py

# 3. Run Comprehensive Route Test Suite (50+ routes)
python scratch/test_all_views.py

# 4. Synchronize PostgreSQL Primary Key Sequences
python scratch/fix_postgres_sequences.py

# 5. Database Seed Script
python manage.py shell -c "import sample_data; sample_data.run()"
```

---

*Documented for VVITU ERP Platform Engineering Team*
