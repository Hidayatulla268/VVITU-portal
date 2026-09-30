@echo off
REM ═══════════════════════════════════════════════════════════════════
REM  🏛️ VVITU University Portal — Windows Firewall Configuration
REM  Allows inbound TCP traffic on Port 8000 for Students & Faculty
REM ═══════════════════════════════════════════════════════════════════

title Opening Firewall Port 8000 for VVITU Portal
color 0A
cls

echo =======================================================================
echo     Opening Port 8000 in Windows Defender Firewall for VVITU Portal
echo =======================================================================
echo.
echo Requesting Administrator privileges to add firewall rule...
echo.

powershell -Command "Start-Process powershell -Verb RunAs -ArgumentList '-NoExit -Command \"Write-Host ''Configuring Windows Firewall for VVITU Portal...'' -ForegroundColor Cyan; Remove-NetFirewallRule -DisplayName ''VVITU ERP Portal (Port 8000)'' -ErrorAction SilentlyContinue; New-NetFirewallRule -DisplayName ''VVITU ERP Portal (Port 8000)'' -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow; Write-Host ''`n[SUCCESS] Port 8000 is now OPEN for all student and faculty devices!'' -ForegroundColor Green; Write-Host ''You can close this window now.''; Start-Sleep -Seconds 5; exit\"'"

echo Done! The firewall elevation prompt has been triggered.
pause
