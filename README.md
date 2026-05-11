# VVIT Portal — Complete ERP System
### Vasireddy Venkatadri Institute of Technology, Nambur, Guntur

A production-grade college ERP web application built with Django, featuring
glassmorphism UI, role-based access control, AI attendance prediction,
Excel/PDF exports, and scalability for 20,000+ concurrent students.

---

## Technology Stack

- **Backend**: Django 4.2 (Python 3.10+)
- **Frontend**: Bootstrap 5, Chart.js 4, Font Awesome 6
- **Database**: SQLite (dev) — PostgreSQL recommended for production
- **Caching**: Django LocMemCache (dev) — Redis recommended for production
- **AI**: scikit-learn linear regression for attendance prediction
- **Exports**: openpyxl (Excel), reportlab (PDF)

---

## Project Structure

```
vvit_portal/
├── vvit_portal/          # Django project config
│   ├── settings.py       # All settings (DB, cache, auth, etc.)
│   ├── urls.py           # Root URL routing
│   └── middleware.py     # Role-based access control middleware
│
├── accounts/             # Custom User, Student, Faculty models + login
├── core/                 # All shared academic models (Branch, Subject, etc.)
├── student/              # Student dashboard, timetable, results, calendar
├── faculty/              # Mark attendance, reports, export, counselling
├── admin_dashboard/      # Full CRUD admin control panel
│
├── templates/            # All HTML templates (extends core/base.html)
│   ├── core/base.html    # Master layout: navbar, sidebar, toasts
│   ├── accounts/         # Login page
│   ├── student/          # Dashboard, timetable, results, calendar, papers
│   ├── faculty/          # Dashboard, mark attendance, reports, counselling
│   └── admin_dashboard/  # All admin management views
│
├── static/
│   ├── css/main.css      # Complete glassmorphism design system
│   ├── css/login.css     # Premium split-panel login page
│   ├── js/main.js        # Sidebar, animations, AJAX utilities
│   └── images/           # Logo files (add vvit_logo.png here)
│
├── management/commands/
│   └── send_low_attendance_alerts.py   # Email notification command
│
├── sample_data.py        # Quick-start sample data population script
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

If scikit-learn or reportlab cause issues, install the others first and add
those two separately — the application degrades gracefully without them.

### Step 3 — Apply database migrations

```bash
python manage.py makemigrations accounts
python manage.py makemigrations core
python manage.py makemigrations
python manage.py migrate
```

### Step 4 — Create the Django superuser

```bash
python manage.py createsuperuser
# Recommended: username=admin, email=admin@vvit.net, password=vvit@1234
```

### Step 5 — Collect static files (required in production, optional in dev)

```bash
python manage.py collectstatic --no-input
```

### Step 6 — Load sample data (optional but highly recommended for testing)

```bash
python manage.py shell < sample_data.py
```

This creates three branches, faculty accounts, seven students, a full
timetable for CSE-II-A, 45 days of attendance records, exam results,
and academic calendar events — everything you need to explore every
feature of the portal immediately.

### Step 7 — Start the development server

```bash
python manage.py runserver
```

The application is now available at `http://127.0.0.1:8000/`.

---

## Default Login Credentials (after loading sample data)

| Role      | Username    | Password   |
|-----------|-------------|------------|
| Admin     | admin       | vvit@1234  |
| Faculty 1 | EMP001      | vvit@1234  |
| Faculty 2 | EMP002      | vvit@1234  |
| Student 1 | 24BQ1A4901  | vvit@1234  |
| Student 7 | 24BQ1A4942  | vvit@1234  |

After login the middleware automatically redirects each user to their
role-specific dashboard — students go to `/student/`, faculty to
`/faculty/`, and admins to `/admin-portal/`.

---

## Key URL Reference

| URL                              | Who can access   | Purpose                         |
|----------------------------------|------------------|---------------------------------|
| `/accounts/login/`               | Everyone         | Main login page                 |
| `/student/`                      | Students         | Dashboard with chart + AI       |
| `/student/timetable/`            | Students         | Section timetable grid          |
| `/student/results/`              | Students         | Paginated exam results          |
| `/student/academic-calendar/`    | Students         | Events / holidays               |
| `/student/question-papers/`      | Students         | Download past papers            |
| `/faculty/`                      | Faculty/HOD/Lab  | Faculty dashboard               |
| `/faculty/mark-attendance/`      | Faculty/HOD/Lab  | AJAX radio-button attendance    |
| `/faculty/reports/`              | Faculty/HOD/Lab  | Attendance report + export      |
| `/faculty/counselled-students/`  | Faculty/HOD/Lab  | List of counselled students     |
| `/admin-portal/`                 | Admin            | Statistics overview             |
| `/admin-portal/students/`        | Admin            | CRUD student management         |
| `/admin-portal/faculty/`         | Admin            | CRUD faculty management         |
| `/admin-portal/attendance/`      | Admin            | Override any attendance record  |
| `/admin/`                        | Superuser        | Django admin panel              |

---

## Adding the VVIT Logo

The application uses `vvit_logo.png` from `/static/images/`. If the file is
missing, the SVG fallback (`vvit_logo_fallback.svg`) is automatically shown.

To use the real VVIT logo, download it from the official website
`https://www.vvit.net` and save it as:

```
static/images/vvit_logo.png
```

Then run `python manage.py collectstatic` if you are in production mode.

---

## Scheduling the Low-Attendance Email Alert

The management command `send_low_attendance_alerts` sends warning emails
to any student whose attendance drops below the threshold in `settings.py`.

```bash
# Test without sending emails
python manage.py send_low_attendance_alerts --dry-run

# Send real emails (requires EMAIL_BACKEND configured in settings.py)
python manage.py send_low_attendance_alerts

# Override the threshold for a single run
python manage.py send_low_attendance_alerts --threshold 65
```

Add it to cron (Linux example — every Monday at 8:00 AM):

```cron
0 8 * * 1 /path/to/venv/bin/python /path/to/manage.py send_low_attendance_alerts
```

---

## Production Deployment Notes

For a production deployment handling 20,000+ students, make the following
changes in `settings.py`:

**Database** — Switch from SQLite to PostgreSQL for true concurrency:
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'vvit_portal',
        'USER': 'vvit_user',
        'PASSWORD': 'your-secure-password',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
```

**Caching** — Switch from LocMemCache to Redis for shared caching:
```python
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
        'OPTIONS': {'CLIENT_CLASS': 'django_redis.client.DefaultClient'},
    }
}
```

**Security** — Always set these in production:
```python
DEBUG = False
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY')  # use env variable
ALLOWED_HOSTS = ['your-domain.com', 'www.your-domain.com']
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
```

**Email** — Configure SMTP for real email delivery:
```python
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.environ.get('EMAIL_USER')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_PASSWORD')
```

**Web Server** — Use Gunicorn behind Nginx for production:
```bash
pip install gunicorn
gunicorn vvit_portal.wsgi:application --workers 4 --bind 0.0.0.0:8000
```

---

## Performance Design Decisions

The codebase is designed with 20,000 concurrent students in mind. Every
model foreign key has `db_index=True`. Attendance queries use
`select_related` on `timetable_entry__subject` to avoid N+1 problems.
The academic calendar view caches its results per (branch, year) pair
for 5 minutes using Django's cache framework — when hundreds of students
load the page simultaneously, only the first request hits the database.
All list views (results, question papers, attendance) are paginated.
The `only()` and `defer()` patterns are used wherever full model
instances are not needed (e.g., the AJAX student-list endpoint).

---

*Built for VVIT — Nambur, Guntur District, Andhra Pradesh*
