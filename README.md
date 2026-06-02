# VVITU Portal — Complete ERP System
### Vasireddy Venkatadri International Institute of Technology, Nambur, Guntur

A production-grade college ERP web application built with Django, featuring a glassmorphism UI, role-based access control, AI attendance prediction, Excel/PDF exports, automatic cloud seeding, and scalability for 300,000+ concurrent students.

---

## 🚀 Key Features

*   **Role-Based Access Control**: Highly secure dashboard routing for Students, Faculty, HODs, DEOs, and Admin.
*   **HOD Dashboard**: Allows Heads of Departments to view departmental stats, assign faculty to subjects/classes, designate counselors/class teachers, manage and publish branch timetables, approve student/faculty achievements, and override branch attendance.
*   **DEO Dashboard**: Enables Data Entry Operators to add/edit students within their assigned branch, upload marks, and edit attendance records within a strict **1-day editing window** (older edits must go through the HOD).
*   **Unified Mail/Notices Board System**: Multi-scoped notifications system allowing Admin, HODs, and DEOs to compose and manage notices targeted to everyone, specific roles, specific branches, specific classes, or single users.
*   **Achievements System**: Allows students and faculty to submit academic (curricular) and co-curricular achievements for HOD verification and display on profiles.
*   **First-Time Password Flow**: Automatically forces students to set a custom, permanent password on their first login, locking it against client modification (only admins can reset it).
*   **Bulk CSV Uploads**: Instantly upload spreadsheets to create thousands of student profiles and populate test marks.
*   **Faculty Student Results View**: Class Teachers and Counsellors can monitor and review the grades of their assigned students.
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
├── accounts/             # Custom User, Student, Faculty, DEO models + details
├── core/                 # Shared academic models, notifications logic, and tasks
│   └── management/commands/ # Custom django-admin commands (seed_data, send_low_attendance_alerts)
├── student/              # Student dashboard, results summary, achievements submit
├── faculty/              # Mark attendance, reports, marks upload, achievements submit
├── admin_dashboard/      # Admin settings, staff role management, global CRUD
├── hod/                  # HOD dashboard, branch assignments, timetable publishing, approvals
├── deo/                  # DEO dashboard, student CRUD, attendance entries, marks uploads
│
├── templates/            # HTML templates (extends core/base.html)
│   ├── core/base.html    # Master layout: navbar, sidebar, notifications dropdown
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

This creates branches, faculty accounts, students, a full timetable for CSE-II-A, 45 days of attendance records, exam results, and academic calendar events—everything you need to explore the portal immediately. Note: This command is idempotent and will skip seeding if data already exists in the database.

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

| Role      | Username    | Password   | Description |
|-----------|-------------|------------|-------------|
| Admin     | `admin`     | `vvit@1234`| Full System Access & CRUD |
| HOD       | `HOD001`    | `vvit@1234`| HOD CSE (Full Branch Management) |
| DEO       | `DEO001`    | `vvit@1234`| DEO CSE (Branch Data Operator) |
| Faculty   | `EMP001`    | `vvit@1234`| Class Teacher & Counsellor |
| Student   | `24BQ1A4942`| `vvit@1234`| Student Login (first login forces password setup) |

> [!WARNING]
> **Production Password Security**: Change these default passwords immediately when deploying in any live or public-facing environment.

---

## Key URL Reference

| URL                              | Who can access   | Purpose                         |
|----------------------------------|------------------|---------------------------------|
| `/accounts/login/`               | Everyone         | Main login page                 |
| `/accounts/set-password/`        | Students (First) | Forces student to set custom permanent password |
| `/accounts/students/<id>/detail/`| Staff / Owner    | Detailed read-only student profile, results, and achievements |
| `/accounts/faculty/<id>/detail/` | Staff / Owner    | Detailed read-only faculty profile, timetable, and subjects |
| `/student/`                      | Students         | Dashboard with charts + AI Prediction |
| `/student/results/`              | Students         | Consolidated results (Mid1, Mid2, Sem Final) |
| `/student/add-achievement/`      | Students         | Submit academic or co-curricular achievements |
| `/faculty/`                      | Faculty/HOD/Lab  | Faculty dashboard & assignments |
| `/faculty/upload-marks/`         | Faculty          | Subject/Exam/Class upload page  |
| `/faculty/add-achievement/`      | Faculty          | Submit faculty achievements     |
| `/hod/`                          | HODs             | HOD Dashboard with branch stats |
| `/hod/timetable/`                | HODs             | Assign faculty & publish timetables |
| `/hod/verify-achievements/`      | HODs             | Review and approve achievements |
| `/deo/`                          | DEOs             | DEO Dashboard (restricted to branch) |
| `/deo/attendance/`               | DEOs             | List/edit attendance (1-day limit) |
| `/deo/upload-marks/`             | DEOs             | Upload branch exam marks        |
| `/notifications/manage/`         | Admin/HOD/DEO    | notice composition & target manager |
| `/admin-portal/`                 | Admin            | Statistics overview             |
| `/admin-portal/students/`        | Admin            | CRUD student management         |
| `/admin-portal/students/bulk-upload/` | Admin       | Bulk upload students via CSV    |
| `/admin-portal/results/bulk-upload/`  | Admin       | Bulk upload results via CSV     |
| `/admin/`                        | Superuser        | Django admin panel              |

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
