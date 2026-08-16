#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════
# VVITU University Portal — Automated College Server Setup Script
# Target OS: Ubuntu 22.04 LTS / 24.04 LTS / Debian 12
# ═══════════════════════════════════════════════════════════════════

set -e

echo "============================================================"
echo "  VVITU UNIVERSITY PORTAL — ON-PREMISE SERVER SETUP"
echo "============================================================"

# 1. Update OS packages
echo "[1/7] Updating system packages..."
sudo apt update && sudo apt upgrade -y

# 2. Install Python, PostgreSQL, Nginx, Git, and build tools
echo "[2/7] Installing Python 3, PostgreSQL, Nginx, and dependencies..."
sudo apt install -y python3 python3-pip python3-venv python3-dev \
    postgresql postgresql-contrib libpq-dev \
    nginx git curl libjpeg-dev zlib1g-dev \
    certbot python3-certbot-nginx

# 3. Create Web Directory & Logs Directory
echo "[3/7] Setting up project filesystem & permissions..."
sudo mkdir -p /var/www/vvitu
sudo mkdir -p /var/log/vvitu
sudo chown -R $USER:www-data /var/www/vvitu
sudo chown -R www-data:www-data /var/log/vvitu

# 4. Setup Python Virtual Environment
echo "[4/7] Creating Python virtual environment..."
python3 -m venv /var/www/vvitu/venv
source /var/www/vvitu/venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install -r /var/www/vvitu/requirements.txt

# 5. Setup PostgreSQL Database & User
echo "[5/7] Configuring PostgreSQL database..."
sudo -u postgres psql -c "CREATE DATABASE vvitu_db;" || true
sudo -u postgres psql -c "CREATE USER vvitu_admin WITH PASSWORD 'CollegeSecret@2026';" || true
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE vvitu_db TO vvitu_admin;" || true
sudo -u postgres psql -c "ALTER DATABASE vvitu_db OWNER TO vvitu_admin;" || true

# 6. Django Database Migration & Static Files Collection
echo "[6/7] Running database migrations & collecting static files..."
export DJANGO_SETTINGS_MODULE=VVITU_Portal.settings_prod
python /var/www/vvitu/manage.py migrate
python /var/www/vvitu/manage.py collectstatic --no-input

# 7. Configure Systemd & Nginx
echo "[7/7] Installing Systemd service and Nginx configuration..."
sudo cp /var/www/vvitu/deploy/vvitu.service /etc/systemd/system/
sudo cp /var/www/vvitu/deploy/nginx_vvitu.conf /etc/nginx/sites-available/vvitu
sudo ln -sf /etc/nginx/sites-available/vvitu /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

sudo systemctl daemon-reload
sudo systemctl enable vvitu
sudo systemctl restart vvitu
sudo nginx -t && sudo systemctl restart nginx

echo "============================================================"
echo "  ✅ VVITU PORTAL SERVER DEPLOYMENT COMPLETED SUCCESSFULLY! "
echo "  Portal is running on: http://127.0.0.1:8000 & Nginx port 80/443"
echo "============================================================"
