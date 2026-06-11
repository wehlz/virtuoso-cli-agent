@echo off
setlocal
cd /d "%~dp0"
title Virtuoso Dashboard v2.2

echo.
echo ========================================
echo   Virtuoso Dashboard v2.2
echo ========================================
echo.

REM Use real Python (not Windows Store stub)
set "PYCMD="
where py >nul 2>&1 && set "PYCMD=py -3"
if not defined PYCMD (
  for /f "delims=" %%P in ('where python 2^>nul ^| findstr /i "Programs\\Python"') do set "PYCMD=%%P"
)
if not defined PYCMD set "PYCMD=python"

echo Using: %PYCMD%
%PYCMD% --version >nul 2>&1
if errorlevel 1 (
  echo ERROR: Python not found. Install Python 3.10+ from python.org
  pause
  exit /b 1
)

echo Stopping old dashboard processes on ports 8770 and 8788...
powershell -NoProfile -Command "foreach ($p in 8770,8788) { Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue } }"
ping 127.0.0.1 -n 3 >nul

echo.
echo Starting server...
echo   URL: http://127.0.0.1:8788/
echo.
echo   DO NOT CLOSE THIS WINDOW while using the dashboard.
echo   Opening browser in a few seconds...
echo.

start /b cmd /c "ping -n 4 127.0.0.1 >nul & start http://127.0.0.1:8788/"

%PYCMD% virtuoso.py --dashboard
if errorlevel 1 (
  echo.
  echo Dashboard failed to start. See error above.
  pause
)
