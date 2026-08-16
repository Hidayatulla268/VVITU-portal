@echo off
REM ═══════════════════════════════════════════════════════════════════
REM VVITU University Portal — Windows Server Startup & Service Script
REM ═══════════════════════════════════════════════════════════════════

echo ============================================================
echo   Starting VVITU University Portal on Windows Server
echo ============================================================

cd /d "%~dp0\.."

REM Activate virtual environment
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
) else (
    echo [ERROR] Python virtual environment not found in .\venv!
    pause
    exit /b 1
)

REM Run migrations
echo [1/3] Applying database migrations...
python manage.py migrate --noinput

REM Collect static files
echo [2/3] Collecting static files...
python manage.py collectstatic --no-input

REM Launch production server via Waitress / Gunicorn / Daphne
echo [3/3] Launching VVITU Portal Server on Port 8000...
echo Visit: http://localhost:8000 or http://127.0.0.1:8000
python manage.py runserver 0.0.0.0:8000

pause
