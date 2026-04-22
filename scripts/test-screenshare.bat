@echo off
echo ========================================
echo    Opening Screen Share System
echo ========================================
echo.

REM 打开两个浏览器标签页用于测试
echo [1/2] Opening first browser tab (Share Screen)...
start "" frontend\screenshare.html

timeout /t 2 /nobreak > nul

echo [2/2] Opening second browser tab (Viewer)...
start "" frontend\screenshare.html

echo.
echo ========================================
echo    Instructions
echo ========================================
echo.
echo TAB 1 (Share Screen):
echo   1. Click "开始共享" button
echo   2. Select screen/window to share
echo   3. Copy the Session ID
echo.
echo TAB 2 (Viewer):
echo   1. Switch to "观看屏幕" mode
echo   2. Enter the Session ID
echo   3. Click "连接" button
echo.
echo Server status: http://localhost:8080/health
echo.
echo ========================================
echo.

pause
