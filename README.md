# VVITU Portal — Complete ERP System
### Vasireddy Venkatadri International Institute of Technology, Nambur, Guntur

A production-grade college ERP web application built with Django, featuring a glassmorphism UI, role-based access control, AI attendance prediction, Excel/PDF exports, automatic cloud seeding, and scalability for 300,000+ concurrent students.

---

## 🚀 Key Features

*   **Role-Based Access Control**: Highly secure dashboard routing for Students, Faculty, and Admin.
*   **First-Time Password Flow**: Automatically forces students to set a custom, permanent password on their first login, locking it against client modification (only admins can reset it).
*   **Bulk CSV Uploads**: Instantly upload spreadsheets to create thousands of student profiles and populate test marks.
*   **Faculty Student Results View**: Class Teachers and Counsellors can monitor and review the grades of their assigned students.
*   **Advanced Security Hardening**: Incorporates client-side rate limiting (5 attempts/min per IP on login) to block brute-force/credential-stuffing, HSTS, SameSite/HttpOnly session cookies, and Referrer-Policy headers.
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
├── accounts/             # Custom User, Student, Faculty models + login
├── core/                 # Shared academic models (Branch, Subject, Result, etc.)
├── student/              # Student dashboard, timetable, results, calendar
├── faculty/              # Mark attendance, reports, exports, counselling
├── admin_dashboard/      # Admin CRUD controllers & bulk upload handlers
│
├── templates/            # HTML templates (extends core/base.html)
│   ├── core/base.html    # Master layout: navbar, sidebar, notifications
│   ├── accounts/         # Login and first-time set password pages
│   ├── student/          # Dashboard, timetable, results, calendar, papers
│   ├── faculty/          # Dashboard, mark attendance, reports, results
│   └── admin_dashboard/  # Admin management and CSV upload pages
│
├── static/
│   ├── css/main.css      # Complete glassmorphism design system
│   ├── css/login.css     # Premium split-panel login page
│   ├── js/main.js        # Sidebar, animations, AJAX utilities
│   └── images/           # Logo files
│
├── management/commands/
│   └── send_low_attendance_alerts.py   # Email alert command
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
python manage.py makemigrations accounts
python manage.py makemigrations core
python manage.py makemigrations
python manage.py migrate
```

### Step 4 — Load sample data (highly recommended for testing)

```bash
python manage.py shell -c "exec(open('sample_data.py').read())"
```

This creates branches, faculty accounts, students, a full timetable for CSE-II-A, 45 days of attendance records, exam results, and academic calendar events—everything you need to explore the portal immediately.

### Step 5 — Start the development server

```bash
python manage.py runserver
```

The application is now available at `http://127.0.0.1:8000/`.

---

## Default Login Credentials (after loading sample data)

| Role      | Username    | Password   | Description |
|-----------|-------------|------------|-------------|
| Admin     | `admin`     | `vvit@1234`| Full CRUD Access |
| Faculty   | `EMP001`    | `vvit@1234`| Class Teacher & Counsellor |
| Student   | `24BQ1A4942`| `vvit@1234`| Student Login (first login forces password setup) |

---

## Key URL Reference

| URL                              | Who can access   | Purpose                         |
|----------------------------------|------------------|---------------------------------|
| `/accounts/login/`               | Everyone         | Main login page                 |
| `/accounts/set-password/`        | Students (First) | Forces student to set custom permanent password |
| `/student/`                      | Students         | Dashboard with chart + AI       |
| `/student/timetable/`            | Students         | Section timetable grid          |
| `/student/results/`              | Students         | Paginated exam results          |
| `/student/academic-calendar/`    | Students         | Events / holidays               |
| `/student/question-papers/`      | Students         | Download past papers            |
| `/faculty/`                      | Faculty/HOD/Lab  | Faculty dashboard               |
| `/faculty/mark-attendance/`      | Faculty/HOD/Lab  | AJAX radio-button attendance    |
| `/faculty/reports/`              | Faculty/HOD/Lab  | Attendance report + export      |
| `/faculty/student-results/`      | Faculty/HOD/Lab  | View results of assigned students |
| `/faculty/counselled-students/`  | Faculty/HOD/Lab  | List of counselled students     |
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
