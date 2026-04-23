@echo off
setlocal enabledelayedexpansion

echo ========================================
echo    Starting Screen Share Server
echo    (Python Edition)
echo ========================================
echo.

REM Install dependencies
echo [1/2] Installing dependencies...
cd /d "%~dp0..\backend"
py -m pip install websockets -q

echo [OK] Dependencies installed
echo.

REM Start server
echo [2/2] Starting server...
echo.
py server.py

pause
