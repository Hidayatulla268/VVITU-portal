#!/usr/bin/env bash
# Exit on error
set -o errexit

echo "📦 Upgrading pip and installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "🎨 Collecting static assets..."
python manage.py collectstatic --no-input

echo "🗄️ Applying database migrations..."
python manage.py migrate --no-input

echo "✅ VVITU Portal Build Completed Successfully!"
