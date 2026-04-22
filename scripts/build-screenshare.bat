@echo off
setlocal enabledelayedexpansion

echo ========================================
echo    Building Screen Share Server
echo ========================================
echo.

cd /d "%~dp0..\backend"

REM 备份原有的 CMakeLists.txt
if exist CMakeLists.txt (
    copy /Y CMakeLists.txt CMakeLists.txt.backup > nul
)

REM 使用屏幕共享配置
copy /Y CMakeLists.screenshare.txt CMakeLists.txt > nul

if not exist build mkdir build
cd build

echo [1/3] Configuring project...
cmake .. -G "Visual Studio 17 2022" -A x64

if errorlevel 1 (
    echo Configuration failed!
    cd ..
    copy /Y CMakeLists.txt.backup CMakeLists.txt > nul
    pause
    exit /b 1
)

echo [2/3] Building project...
cmake --build . --config Release

if errorlevel 1 (
    echo Build failed!
    cd ..
    copy /Y CMakeLists.txt.backup CMakeLists.txt > nul
    pause
    exit /b 1
)

cd ..

REM 恢复原有的 CMakeLists.txt
if exist CMakeLists.txt.backup (
    copy /Y CMakeLists.txt.backup CMakeLists.txt > nul
    del CMakeLists.txt.backup
)

echo [3/3] Build complete!
echo.
echo ========================================
echo    Build Successful!
echo ========================================
echo.
echo Executable: build\bin\Release\screenshare-server.exe
echo.
echo To start the server:
echo   cd build\bin\Release
echo   screenshare-server.exe
echo.

pause
