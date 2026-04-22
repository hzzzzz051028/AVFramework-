@echo off
setlocal enabledelayedexpansion

echo ========================================
echo    Starting Screen Share System
echo ========================================
echo.

cd /d "%~dp0.."

echo [1/3] Installing Node.js dependencies...
cd backend
call npm install
if errorlevel 1 (
    echo Failed to install dependencies!
    echo Make sure Node.js is installed: https://nodejs.org/
    pause
    exit /b 1
)

echo [2/3] Starting signaling server...
start "Signaling Server" cmd /k "cd /d "%CD%" && npm start"

timeout /t 2 /nobreak > nul

echo [3/3] Opening web interface...
start "" frontend\screenshare.html

echo.
echo ========================================
echo    System Started!
echo ========================================
echo.
echo Signaling server running in separate window.
echo Browser should open with screenshare.html
echo.
echo If browser didn't open, manually open:
echo   frontend\screenshare.html
echo.
echo Press Ctrl+C in server window to stop.
echo.

pause
