@echo off
REM ═══════════════════════════════════════════════════════════════════
REM VVITU University Portal — Windows Server Startup & Service Script
REM ═══════════════════════════════════════════════════════════════════

echo ============================================================
echo   Starting VVITU University Portal on Windows Server
echo ============================================================

cd /d "%~dp0\.."

REM Activate virtual environment
if exist secenv\Scripts\activate.bat (
    call secenv\Scripts\activate.bat
) else if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
) else (
    echo [ERROR] Python virtual environment not found in .\secenv or .\venv!
    pause
    exit /b 1
)

REM Run migrations
echo [1/3] Applying database migrations...
python manage.py migrate --noinput

REM Collect static files
echo [2/3] Collecting static files...
python manage.py collectstatic --no-input

REM Launch production server via Waitress WSGI Server (16 threads for 200+ users)
echo [3/3] Launching VVITU Portal Production Server on Port 8000...
for /f "tokens=*" %%a in ('python -c "import socket; print(socket.gethostbyname(socket.gethostname()))"') do set "LAB_IP=%%a"
echo Local Access:   http://localhost:8000
if not "%LAB_IP%"=="" echo Network Access: http://%LAB_IP%:8000
python -m waitress --host=0.0.0.0 --port=8000 --threads=16 --channel-timeout=60 VVITU_Portal.wsgi:application

pause
