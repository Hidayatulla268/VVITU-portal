# 🏛️ VVITU University Portal — College Server Production Deployment Guide

This guide details how to deploy and run the **VVITU University Portal** 24/7 on your college's **on-premise or cloud-dedicated Linux / Windows servers**.

---

## 🏗️ Architecture Overview

```
[ Students, Faculty, Parents, Staff Devices ]
                     │
                     │ (HTTPS / Port 443 & HTTP / Port 80)
                     ▼
          ┌─────────────────────┐
          │     Nginx / SSL     │  <-- Serves /static/ & /media/ directly
          └──────────┬──────────┘
                     │
                     │ (Reverse Proxy -> 127.0.0.1:8000)
                     ▼
          ┌─────────────────────┐
          │  Gunicorn (Systemd) │  <-- Python WSGI Application Server
          └──────────┬──────────┘
                     │
                     ▼
          ┌─────────────────────┐
          │  PostgreSQL Server  │  <-- Institutional Database (on-campus)
          └─────────────────────┘
```

---

## 💻 Recommended Server Specifications

* **Operating System**: Ubuntu 22.04 / 24.04 LTS (recommended) or Debian 12 / Windows Server 2022
* **Processor**: 4 vCPUs or higher
* **RAM**: 8 GB or 16 GB (handles concurrent student portal traffic during attendance and exam result releases)
* **Storage**: 50 GB+ SSD / NVMe
* **Database**: PostgreSQL 14 / 15 / 16

---

## 🚀 1-Click Automated Linux Setup

If you are using **Ubuntu / Debian Linux**, run:

```bash
cd /var/www/vvitu
chmod +x deploy/setup_college_server.sh
sudo ./deploy/setup_college_server.sh
```

---

## 🛠️ Step-by-Step Manual Linux Deployment

### Step 1: Install Required System Packages
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-pip python3-venv python3-dev \
    postgresql postgresql-contrib libpq-dev \
    nginx git curl libjpeg-dev zlib1g-dev \
    certbot python3-certbot-nginx
```

### Step 2: Clone Repository & Create Virtual Environment
```bash
sudo mkdir -p /var/www/vvitu
sudo chown -R $USER:www-data /var/www/vvitu
git clone https://github.com/Hidayatulla268/VVITU-portal.git /var/www/vvitu

cd /var/www/vvitu
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 3: Configure On-Premise PostgreSQL Database
```bash
sudo -u postgres psql
```
Inside the `psql` console:
```sql
CREATE DATABASE vvitu_db;
CREATE USER vvitu_admin WITH PASSWORD 'CollegeStrongPassword@2026';
GRANT ALL PRIVILEGES ON DATABASE vvitu_db TO vvitu_admin;
ALTER DATABASE vvitu_db OWNER TO vvitu_admin;
\q
```

### Step 4: Configure Production Environment Variables (`.env`)
Create `/var/www/vvitu/.env`:
```ini
DEBUG=False
SECRET_KEY=generate_a_long_random_secret_string_here
ALLOWED_HOSTS=portal.vvit.net,www.portal.vvit.net,192.168.1.100,localhost,127.0.0.1
DATABASE_URL=postgres://vvitu_admin:CollegeStrongPassword@2026@localhost:5432/vvitu_db
DJANGO_SETTINGS_MODULE=VVITU_Portal.settings_prod

# Optional: Email Notifications (Gmail / College SMTP Relay)
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=portal@vvitu.ac.in
EMAIL_HOST_PASSWORD=your_app_password
DEFAULT_FROM_EMAIL=VVITU Portal <noreply@vvitu.ac.in>

# Optional: AI Chatbot (Gemini API)
GEMINI_API_KEY=your_gemini_api_key_here
```

### Step 5: Migrate Database & Collect Static Assets
```bash
source venv/bin/activate
python manage.py migrate
python manage.py collectstatic --no-input
```

### Step 6: Configure Systemd Daemon Service (`vvitu.service`)
```bash
sudo cp deploy/vvitu.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable vvitu
sudo systemctl start vvitu
sudo systemctl status vvitu
```

### Step 7: Configure Nginx Web Server & SSL
```bash
sudo cp deploy/nginx_vvitu.conf /etc/nginx/sites-available/vvitu
sudo ln -sf /etc/nginx/sites-available/vvitu /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# Test Nginx configuration
sudo nginx -t

# Obtain Free SSL Certificate via Let's Encrypt (if domain is pointed to server)
sudo certbot --nginx -d portal.vvit.net -d www.portal.vvit.net

# Restart Nginx
sudo systemctl restart nginx
```

---

## 🪟 Windows Server Deployment (Alternative)

1. Install Python 3.11/3.12 and PostgreSQL on the Windows Server.
2. Clone repository to `C:\inetpub\vvitu_portal`.
3. Create `.env` file with production settings.
4. Run `deploy\setup_windows_server.bat` to apply migrations and launch the server.
5. (Optional) Use **NSSM** (Non-Sucking Service Manager) to run Gunicorn/Waitress as a permanent Windows Service.

---

## 💾 Automated Daily Database Backups

To automatically back up the database every night at 2:00 AM:
```bash
sudo chmod +x /var/www/vvitu/deploy/backup_database.sh
sudo crontab -e
```
Add the line:
```cron
0 2 * * * /var/www/vvitu/deploy/backup_database.sh >> /var/log/vvitu/backup.log 2>&1
```

---

## 🔄 Routine Portal Maintenance Commands

| Task | Command |
| :--- | :--- |
| **Check Portal Status** | `sudo systemctl status vvitu` |
| **Restart Portal Application** | `sudo systemctl restart vvitu` |
| **View Live Gunicorn Logs** | `sudo journalctl -u vvitu -f` |
| **View Nginx Access / Error Logs** | `sudo tail -f /var/log/nginx/vvitu_access.log` |
| **Pull New Code & Deploy Update** | `git pull && python manage.py migrate && python manage.py collectstatic --no-input && sudo systemctl restart vvitu` |
