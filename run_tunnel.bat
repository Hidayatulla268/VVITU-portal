@echo off
REM ═══════════════════════════════════════════════════════════════════
REM  🌐 VVITU University Portal — Cloudflare Public Tunnel
REM  Exposes http://localhost:8000 to the worldwide internet via HTTPS
REM ═══════════════════════════════════════════════════════════════════

title VVITU Cloudflare Public Internet Tunnel
color 0D
cls

echo =======================================================================
echo         VVITU UNIVERSITY ERP PORTAL - PUBLIC INTERNET TUNNEL
echo =======================================================================
echo.
echo Connecting to Cloudflare edge network...
echo.
echo Look for the line below starting with 'https://' ending in '.trycloudflare.com'.
echo That is your worldwide public HTTPS link!
echo.
echo =======================================================================
echo.

cloudflared tunnel --url http://localhost:8000

pause
