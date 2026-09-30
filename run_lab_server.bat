@echo off
REM ═══════════════════════════════════════════════════════════════════
REM  🏛️ VVITU University Portal — Live Lab Server Runner
REM  Configured for 200 concurrent Students & Faculty on Windows LAN
REM ═══════════════════════════════════════════════════════════════════

title VVITU University Portal - Live Production Server
color 0B
cls

echo =======================================================================
echo          VVITU UNIVERSITY ERP PORTAL - LIVE LAB SERVER
echo =======================================================================
echo.

cd /d "%~dp0"

REM 1. Activate Python Virtual Environment
if exist secenv\Scripts\activate.bat (
    call secenv\Scripts\activate.bat
) else if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
) else (
    color 0C
    echo [ERROR] Virtual environment not found in .\secenv or .\venv!
    echo Please make sure the virtual environment is set up.
    pause
    exit /b 1
)

REM 2. Apply Migrations & Collect Static Files
echo [1/3] Verifying database schema...
python manage.py migrate --no-input >nul 2>&1

echo [2/3] Verifying static assets...
python manage.py collectstatic --no-input >nul 2>&1

REM 3. Detect and display Local Network IP
echo [3/3] Detecting Lab Network IP Address...
for /f "tokens=*" %%a in ('python -c "import socket; print(socket.gethostbyname(socket.gethostname()))"') do set "LAB_IP=%%a"

cls
echo =======================================================================
echo          🏛️ VVITU UNIVERSITY ERP PORTAL IS NOW LIVE!
echo =======================================================================
echo.
echo   Capacity:      Configured for 200+ Students & Faculty (16 WSGI Threads)
echo   Engine:        Waitress Multi-Threaded Production WSGI Server
echo.
echo   -------------------------------------------------------------
echo   ACCESS LINKS:
echo   -------------------------------------------------------------
echo   [On This Lab PC]:   http://localhost:8000
echo                       http://127.0.0.1:8000
echo.
if not "%LAB_IP%"=="" (
echo   [For Students]:     http://%LAB_IP%:8000
echo   [For Faculty]:      http://%LAB_IP%:8000
echo.
echo   Share this URL with students/faculty connected to College Wi-Fi/LAN!
) else (
echo   [Students/Faculty]: http://<YOUR_LAB_PC_IP>:8000
)
echo   -------------------------------------------------------------
echo.
echo   * IMPORTANT: If other devices cannot open the link, right-click
echo     'deploy\allow_firewall.bat' and select 'Run as Administrator'.
echo.
echo   Press CTRL + C at any time to stop the server.
echo =======================================================================
echo.

REM 4. Launch Production Waitress WSGI Server (16 threads to easily handle 200 users)
python -m waitress --host=0.0.0.0 --port=8000 --threads=16 --channel-timeout=60 VVITU_Portal.wsgi:application

pause
