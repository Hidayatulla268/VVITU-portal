# VVITU Portal — Complete ERP System
### Vasireddy Venkatadri International Technological University, Nambur, Guntur

A production-grade college ERP web application built with Django, featuring a glassmorphism UI, role-based access control, AI attendance prediction, Excel/PDF exports, automatic cloud seeding, and scalability for 300,000+ concurrent students.

---

## 🚀 Key Features

*   **Role-Based Access Control**: Highly secure dashboard routing for Students, Faculty, HODs, DEOs, and Admin — each with tailored sidebar navigation and scoped permissions.
*   **HOD Dashboard**: Allows Heads of Departments to view departmental stats, assign faculty to subjects/classes, designate counselors/class teachers, manage and publish branch timetables, approve student/faculty achievements, and override branch attendance at any time.
*   **DEO Dashboard**: Enables Data Entry Operators to add/edit students within their assigned branch, upload marks, and edit attendance records within a strict **1-day editing window** (older edits must go through the HOD).
*   **HOD + Teaching Dual-Panel**: HOD users can seamlessly toggle between their HOD administrative panel and their personal Faculty teaching panel using header toggle buttons — both fully accessible from a single login.
*   **Unified Mail/Notices Board System**: Multi-scoped notifications system allowing Admin, HODs, and DEOs to compose and manage notices targeted to everyone, specific roles, specific branches, specific classes, or single users. Quick "Send" shortcut available in the navbar notification dropdown for all authorized roles.
*   **Achievements System**: Allows students and faculty to submit academic (curricular) and co-curricular achievements for HOD verification and display on profiles.
*   **First-Time Password Flow**: Automatically forces students to set a custom, permanent password on their first login, locking it against client modification (only admins can reset it).
*   **Bulk CSV Uploads**: Instantly upload spreadsheets to create thousands of student profiles and populate test marks.
*   **Faculty Student Results View**: Class Teachers and Counsellors can monitor and review the grades of their assigned students.
*   **Comprehensive Profile Pages**: Each role (Student, Faculty/HOD, DEO, Admin) has a tailored profile page displaying relevant details — branch, department, employee ID, joining date, and access level.
*   **Clickable Roll-Number/Employee-ID Links**: Admin can click any student roll number or faculty employee ID in management tables to open a full read-only detail view.
*   **Name Validation**: Server-side validation enforces minimum character lengths for first name (3 chars) and last name (1 char) on add/edit forms.
*   **Advanced Security Hardening**: Incorporates server-side rate limiting (5 attempts/min per IP on login) to block brute-force/credential-stuffing, HSTS, SameSite/HttpOnly session cookies, and Referrer-Policy headers.
*   **Excel & PDF Export**: Download dynamically generated attendance reports on demand.
*   **AI Attendance Predictor**: Utilizes scikit-learn to analyze student records and predict semester attendance outcomes.

---

## Technology Stack

- **Backend**: Django 4.2 (Python 3.11+)
- **Frontend**: Bootstrap 5, Chart.js 4, Font Awesome 6
- **Database**: SQLite (dev) — PostgreSQL (production)
- **Caching**: Django LocMemCache (dev) — Redis (production)
- **AI**: scikit-learn linear regression for attendance prediction
- **Exports**: openpyxl (Excel), reportlab (PDF)

---

## Project Structure

```
VVITU_Portal/
├── VVITU_Portal/          # Django project config
│   ├── settings.py       # Base settings
│   ├── settings_prod.py  # Production settings overrides (HSTS, SSL, Cache)
│   ├── urls.py           # Root URL routing
│   └── middleware.py     # Role-based access and Login Rate Limiter
│
├── accounts/             # Custom User, Student, Faculty, DEOProfile, Achievement models
│   ├── views.py          # Login, logout, profile, first-login password set
│   └── profile_detail_views.py  # Read-only student/faculty detail views for Admin/HOD
├── core/                 # Shared academic models, notifications centre, and tasks
│   ├── models.py         # Branch, Section, Subject, Timetable, Notification, etc.
│   ├── notification_views.py # Full notifications CRUD — compose, manage, delete
│   └── management/commands/ # seed_data, send_low_attendance_alerts
├── student/              # Student dashboard, results summary, achievements submit
├── faculty/              # Mark attendance, reports, marks upload, achievements submit
├── admin_dashboard/      # Admin settings, staff role management, global CRUD
├── hod/                  # HOD dashboard, branch assignments, timetable publishing, approvals
├── deo/                  # DEO dashboard, student CRUD, attendance entries, marks uploads
│
├── templates/            # HTML templates (extends core/base.html)
│   ├── core/base.html    # Master layout: navbar, sidebar, notifications dropdown
│   ├── core/create_notification.html # Compose/edit notices with live preview
│   ├── core/manage_notifications.html # Sent notices list with edit/delete
│   ├── accounts/         # Profile details, login, and first-time password reset
│   ├── student/          # Dashboard, results, calendar, past papers, achievements
│   ├── faculty/          # Dashboard, attendance sheet, reports, marks upload
│   ├── admin_dashboard/  # Admin staff/student managers, bulk CSV pages
│   ├── hod/              # HOD department manager, approvals, timetable editors
│   └── deo/              # DEO branch lists, attendance records, upload pages
│
├── static/
│   ├── css/main.css      # Complete glassmorphism design system
│   ├── css/login.css     # Premium split-panel login page
│   ├── js/main.js        # Sidebar, dropdowns, AJAX polling utilities
│   └── images/           # Logo files
│
├── sample_data.py        # Database seeding script (runs automatically on Render)
├── render.yaml           # One-click Render Blueprint Deployment config
└── requirements.txt
```

---

## Step-by-Step Setup

### Step 1 — Create and activate a virtual environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### Step 2 — Install all dependencies

```bash
pip install -r requirements.txt
```

### Step 3 — Apply database migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

### Step 4 — Load sample data (highly recommended for testing)

```bash
python manage.py seed_data
```

This creates branches, faculty accounts, students, a full timetable for CSE-II-A, 45 days of attendance records, exam results, and academic calendar events — everything you need to explore the portal immediately. Note: This command is idempotent and will skip seeding if data already exists in the database.

### Step 5 — Start the development server

```bash
python manage.py runserver
```

The application is now available at `http://127.0.0.1:8000/`.

### Step 6 — (Optional) Running PostgreSQL locally with Docker

To avoid SQLite/PostgreSQL mismatches in local development, run a local PostgreSQL container:

```bash
docker run --name vvit-postgres -p 5432:5432 -e POSTGRES_DB=vvitu_portal -e POSTGRES_USER=vvitu_user -e POSTGRES_PASSWORD=pass -d postgres
```

And update your `.env` file to reference this local database:
```ini
DATABASE_URL=postgres://vvitu_user:pass@localhost:5432/vvitu_portal
```

---

## Default Login Credentials (after loading sample data)

All accounts share the default password: **`vvit@1234`**

| Role | Username / Range | Branch / Scope | Description |
|---|---|---|---|
| **Admin** | `admin` | Global | Full System Access & CRUD |
| **HODs** | `HOD001` to `HOD008` | CSE (`HOD001`), ECE (`HOD002`), EEE (`HOD003`), IT (`HOD004`), CSM (`HOD005`), CSD (`HOD006`), CIVIL (`HOD007`), MECH (`HOD008`) | Full Branch Management & Teaching Panel |
| **DEOs** | `DEO001` to `DEO008` | CSE (`DEO001`), ECE (`DEO002`), EEE (`DEO003`), IT (`DEO004`), CSM (`DEO005`), CSD (`DEO006`), CIVIL (`DEO007`), MECH (`DEO008`) | Branch-scoped Data Operator |
| **Faculty** | `EMP001` to `EMP016` | 2 per branch (e.g. `EMP001`-`EMP002` CSE, `EMP003`-`EMP004` ECE, etc.) | Class Teachers, Counsellors, and Subject Instructors |
| **Students** | `24BQ1A4942` (CSE A) <br> `24BQ1A0401` (ECE A) <br> `24BQ1A4201` (CSM A) <br> (66 total students across branches) | Various | Students across Years 1-4 with branch-specific roll numbers |


> [!WARNING]
> **Production Password Security**: Change these default passwords immediately when deploying in any live or public-facing environment.

---

## Key URL Reference

| URL                                     | Who can access       | Purpose                                           |
|-----------------------------------------|----------------------|---------------------------------------------------|
| `/accounts/login/`                      | Everyone             | Main login page                                   |
| `/accounts/profile/`                    | All roles            | Personal profile page (role-specific details)     |
| `/accounts/set-password/`               | Students (First)     | Forces student to set custom permanent password   |
| `/accounts/students/<id>/detail/`       | Admin / HOD / DEO    | Read-only student profile, results, achievements  |
| `/accounts/faculty/<id>/detail/`        | Admin / HOD / DEO    | Read-only faculty profile, subjects               |
| `/student/`                             | Students             | Dashboard with charts + AI Prediction             |
| `/student/results/`                     | Students             | Consolidated results (Mid1, Mid2, Sem Final)      |
| `/student/add-achievement/`             | Students             | Submit academic or co-curricular achievements     |
| `/faculty/`                             | Faculty / HOD / Lab  | Faculty dashboard & assignments                   |
| `/faculty/upload-marks/`                | Faculty              | Subject/Exam/Class marks upload page              |
| `/faculty/add-achievement/`             | Faculty              | Submit faculty achievements                       |
| `/hod/`                                 | HODs                 | HOD Dashboard with branch stats                   |
| `/hod/timetable/`                       | HODs                 | Assign faculty & publish timetables               |
| `/hod/verify-achievements/`             | HODs                 | Review and approve achievements                   |
| `/deo/`                                 | DEOs                 | DEO Dashboard (restricted to assigned branch)     |
| `/deo/attendance/`                      | DEOs                 | List/edit attendance (1-day time limit)           |
| `/deo/upload-marks/`                    | DEOs                 | Upload branch exam marks                          |
| `/notifications/`                       | All roles            | Full notification centre (inbox view)             |
| `/notifications/manage/`               | Admin / HOD / DEO    | Sent notices list — compose, edit, delete         |
| `/notifications/create/`               | Admin / HOD / DEO    | Compose & send a new notice with live preview     |
| `/admin-portal/`                        | Admin                | Statistics overview                               |
| `/admin-portal/students/`              | Admin                | CRUD student management                           |
| `/admin-portal/students/bulk-upload/`  | Admin                | Bulk upload students via CSV                      |
| `/admin-portal/results/bulk-upload/`   | Admin                | Bulk upload results via CSV                       |
| `/admin/`                               | Superuser            | Django admin panel                                |

---

## 🔧 Recent Fixes & Improvements

### Bug Fixes — July 2026

- **Backup filename format bug** (`admin_dashboard/views.py`): Corrected a malformed `strftime` format string `'%Y%md_%H%M%S'` that embedded a literal `d` in every backup filename (e.g. `db_backup_202607d_123456.json`). Fixed to `'%Y%m%d_%H%M%S'` for correct ISO-style dates.

- **Grade not recalculated on result update** (`admin_dashboard/views.py`): `Result.save()` auto-computes grade only when `self.grade` is falsy. When updating existing records via "Add Results" or "Bulk Upload Results", the old stale grade was retained even after marks changed. Fixed by explicitly passing `'grade': ''` in the `update_or_create` defaults for both the manual entry and CSV bulk-upload result flows, forcing a fresh grade calculation on every save.

- **Broken `transaction.atomic()` rollback in Bulk Upload Students** (`admin_dashboard/views.py`): The `raise Exception(...)` that was intended to trigger a database rollback on CSV errors was placed **outside** the `with transaction.atomic()` block, meaning the rollback never actually occurred. Additionally, a misleading **"Successfully imported X students"** flash message was queued to the request before the exception propagated, so users saw a success notice even when all data was being silently rolled back. Fixed by moving the error-check-and-raise **inside** the atomic block, and placing the success message after the block exits cleanly.

- **Chained `dict_get` template filter broken in Add Results form** (`templates/admin_dashboard/add_results.html`): The expression `existing_results|dict_get:sid|default:''|dict_get:'marks_obtained'` used `|default:''` as a mid-chain fallback. When a student had no existing result, `dict_get` returned `None`, then `|default:''` converted it to the empty string `''`, and the second `dict_get` was called on a string — not a dict — always returning `None`. This prevented existing marks from being pre-filled in the form. Fixed by changing `|default:''` → `|default:{}` (empty dict), so the second `dict_get` receives a dict and the trailing `|default` value renders correctly.

---

### Earlier Fixes

- **Notification "Send" button**: Quick-compose link in the navbar dropdown is now visible to HOD and DEO users, not just Admin.
- **Sidebar active state accuracy**: Faculty sidebar navigation links now correctly use `app_name` matching to prevent false active highlights when HOD users browse from the "My Teaching" section.
- **DEO profile page**: DEO users now see their assigned branch, employee ID, and access level on their personal profile page.
- **Notification Server 500 fix**: Added safe `try-except` guards around HOD/DEO profile lookups in the notification query builder to prevent crashes when profiles are missing.
- **Template syntax fix**: Resolved Django `TemplateSyntaxError` in the notification compose page caused by unsupported parentheses in template `if` conditions.
- **HOD teaching panel toggle**: HOD users can toggle between the HOD administrative panel and their personal Faculty teaching panel via header buttons on both dashboards.

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
