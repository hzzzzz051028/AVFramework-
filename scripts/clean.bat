@echo off
setlocal enabledelayedexpansion

echo ========================================
echo    Cleaning Project - Removing Redundant Files
echo ========================================
echo.

set PROJECT_DIR=C:\Users\1000003244\Desktop\video_test

REM 删除构建产物
echo [1/6] Removing build artifacts...
if exist "%PROJECT_DIR%\backend\build" rmdir /s /q "%PROJECT_DIR%\backend\build"
if exist "%PROJECT_DIR%\backend\test_build" rmdir /s /q "%PROJECT_DIR%\backend\test_build"
if exist "%PROJECT_DIR%\frontend\node_modules" rmdir /s /q "%PROJECT_DIR%\frontend\node_modules"
if exist "%PROJECT_DIR%\frontend\dist" rmdir /s /q "%PROJECT_DIR%\frontend\dist"
echo   Build artifacts removed

REM 删除临时文件
echo [2/6] Removing temporary files...
if exist "%PROJECT_DIR%\backend\temp" rmdir /s /q "%PROJECT_DIR%\backend\temp"
if exist "%PROJECT_DIR%\backend\hls" rmdir /s /q "%PROJECT_DIR%\backend\hls"
del /f /q "*.log" 2>nul
del /f /q "*.tmp" 2>nul
echo   Temporary files removed

REM 删除测试文件
echo [3/6] Removing test files...
if exist "%PROJECT_DIR%\backend\src\demo_main.cpp" del /f /q "%PROJECT_DIR%\backend\src\demo_main.cpp"
if exist "%PROJECT_DIR%\backend\test_main.cpp" del /f /q "%PROJECT_DIR%\backend\test_main.cpp"
if exist "%PROJECT_DIR%\backend\CMakeLists.test.txt" del /f /q "%PROJECT_DIR%\backend\CMakeLists.test.txt"
echo   Test files removed

REM 删除可执行文件和 DLL
echo [4/6] Removing executables and DLLs...
for /r "%PROJECT_DIR%\backend" %%f in (*.exe) do del /f /q "%%f" 2>nul
for /r "%PROJECT_DIR%\backend" %%f in (*.dll) do del /f /q "%%f" 2>nul
for /r "%PROJECT_DIR%\backend" %%f in (*.obj) do del /f /q "%%f" 2>nul
echo   Executables and DLLs removed

REM 删除编辑器临时文件
echo [5/6] Removing editor temporary files...
for /r "%PROJECT_DIR%" %%f in (*.swp) do del /f /q "%%f" 2>nul
for /r "%PROJECT_DIR%" %%f in (*.swo) do del /f /q "%%f" 2>nul
for /r "%PROJECT_DIR%" %%f in (*.tmp) do del /f /q "%%f" 2>nul
for /r "%PROJECT_DIR%" %%f in (Thumbs.db) do del /f /q "%%f" 2>nul
echo   Editor files removed

REM 删除空的 .claude 目录
echo [6/6] Cleaning Claude Code workspace...
if exist "%PROJECT_DIR%\.claude" rmdir /s /q "%PROJECT_DIR%\.claude"
echo   Workspace cleaned

echo.
echo ========================================
echo    Cleanup Complete!
echo ========================================
echo.
echo Remaining directories:
echo   • backend\src\     - Source code
echo   • backend\include\ - Header files
echo   • frontend\src\    - Frontend source
echo   • scripts\         - Build scripts
echo   • docs\            - Documentation
echo.

endlocal
