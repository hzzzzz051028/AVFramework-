@echo off
echo ========================================
echo    CMake 快速安装
echo ========================================
echo.

set TEMP_DIR=%USERPROFILE%\Desktop\video_test\temp
if not exist "%TEMP_DIR%" mkdir "%TEMP_DIR%"

echo [1/3] 下载 CMake...
powershell -Command "& {[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://github.com/Kitware/CMake/releases/download/v3.28.1/cmake-3.28.1-windows-x86_64.msi' -OutFile '%TEMP_DIR%\cmake-installer.msi' -UseBasicParsing}"

if %ERRORLEVEL% NEQ 0 (
    echo 下载失败!
    pause
    exit /b 1
)

echo [2/3] 安装 CMake...
msiexec /i "%TEMP_DIR%\cmake-installer.msi" /quiet ADD_CMAKE_TO_PATH=System

echo [3/3] 清理临时文件...
del "%TEMP_DIR%\cmake-installer.msi"

echo.
echo ========================================
echo    CMake 安装完成!
echo ========================================
echo.
echo 请关闭并重新打开命令提示符以使环境变量生效
echo 验证安装: cmake --version
echo.
pause
