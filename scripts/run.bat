@echo off
setlocal enabledelayedexpansion

if "%1"=="" goto :usage
if "%1"=="backend" goto :backend
if "%1"=="frontend" goto :frontend
if "%1"=="docker" goto :docker
if "%1"=="stop" goto :stop
goto :usage

:backend
echo Starting backend server...
cd /d "%~dp0..\backend\build\Release"
start avframework.exe
goto :end

:frontend
echo Starting frontend server...
cd /d "%~dp0..\frontend"
start npm run dev
goto :end

:docker
echo Starting with Docker...
cd /d "%~dp0.."
docker-compose up -d
echo Services started!
echo Frontend: http://localhost
echo Backend API: http://localhost:8080
echo WebSocket: ws://localhost:8081
goto :end

:stop
echo Stopping Docker services...
cd /d "%~dp0.."
docker-compose down
goto :end

:usage
echo Usage: %0 {backend^|frontend^|docker^|stop}
exit /b 1

:end
endlocal
