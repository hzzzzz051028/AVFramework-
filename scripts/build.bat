@echo off
setlocal enabledelayedexpansion

echo Building AVFramework...

set SCRIPT_DIR=%~dp0
set PROJECT_DIR=%SCRIPT_DIR%..

echo Building backend...
cd /d "%PROJECT_DIR%\backend"

if not exist build mkdir build
cd build

cmake .. -G "Visual Studio 17 2022" -A x64
if errorlevel 1 (
    echo CMake generation failed!
    exit /b 1
)

cmake --build . --config Release
if errorlevel 1 (
    echo Backend build failed!
    exit /b 1
)

echo Backend built successfully!

echo Building frontend...
cd /d "%PROJECT_DIR%\frontend"

call npm install
if errorlevel 1 (
    echo npm install failed!
    exit /b 1
)

call npm run build
if errorlevel 1 (
    echo Frontend build failed!
    exit /b 1
)

echo Frontend built successfully!

echo AVFramework build complete!

endlocal
