# Windows C++ 开发环境自动安装脚本
# 使用方法: 在 PowerShell (管理员) 中运行: .\scripts\install-dev-env.ps1

#Requires -RunAsAdministrator

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   Windows C++ 开发环境配置工具" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 检查 winget 是否可用
function Test-Winget {
    try {
        winget --version | Out-Null
        return $true
    } catch {
        return $false
    }
}

# 检查并安装 Chocolatey
function Install-Chocolatey {
    if (!(Get-Command choco -ErrorAction SilentlyContinue)) {
        Write-Host "[1/6] 安装 Chocolatey 包管理器..." -ForegroundColor Yellow
        Set-ExecutionPolicy Bypass -Scope Process -Force
        [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
        Invoke-Expression ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
        Write-Host "   Chocolatey 安装完成!" -ForegroundColor Green
    } else {
        Write-Host "[1/6] Chocolatey 已安装" -ForegroundColor Green
    }
}

# 安装 Git
function Install-Git {
    if (!(Get-Command git -ErrorAction SilentlyContinue)) {
        Write-Host "[2/6] 安装 Git..." -ForegroundColor Yellow
        if (Test-Winget) {
            winget install --id Git.Git -e --accept-source-agreements --accept-package-agreements
        } else {
            choco install git -y
        }

        # 刷新环境变量
        refreshenv
        Write-Host "   Git 安装完成!" -ForegroundColor Green
    } else {
        Write-Host "[2/6] Git 已安装: $(git --version)" -ForegroundColor Green
    }
}

# 安装 CMake
function Install-CMake {
    if (!(Get-Command cmake -ErrorAction SilentlyContinue)) {
        Write-Host "[3/6] 安装 CMake..." -ForegroundColor Yellow
        if (Test-Winget) {
            winget install Kitware.CMake -e --accept-source-agreements --accept-package-agreements
        } else {
            choco install cmake -y
        }

        refreshenv
        Write-Host "   CMake 安装完成!" -ForegroundColor Green
    } else {
        Write-Host "[3/6] CMake 已安装: $(cmake --version)" -ForegroundColor Green
    }
}

# 安装 Visual Studio Build Tools
function Install-VSBuildTools {
    $vsWhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
    if (Test-Path $vsWhere) {
        $version = & $vsWhere -latest -property displayVersion
        if ($version) {
            Write-Host "[4/6] Visual Studio 已安装: $version" -ForegroundColor Green
            return
        }
    }

    Write-Host "[4/6] 安装 Visual Studio Build Tools..." -ForegroundColor Yellow
    Write-Host "   这将下载较大文件 (~5GB)，请耐心等待..." -ForegroundColor Cyan

    $vsInstaller = "$env:TEMP\vs_BuildTools.exe"
    $vsUrl = "https://aka.ms/vs/17/release/vs_BuildTools.exe"

    Write-Host "   下载中..." -ForegroundColor Cyan
    Invoke-WebRequest -Uri $vsUrl -OutFile $vsInstaller -UseBasicParsing

    Write-Host "   安装中 (这可能需要 15-30 分钟)..." -ForegroundColor Cyan
    $args = @(
        "--quiet",
        "--wait",
        "--norestart",
        "--nocache",
        "--add", "Microsoft.VisualStudio.Workload.VCTools",
        "--add", "Microsoft.VisualStudio.Workload.NativeDesktop",
        "--includeRecommended"
    )

    $process = Start-Process -FilePath $vsInstaller -ArgumentList $args -Wait -PassThru

    Remove-Item $vsInstaller -Force

    if ($process.ExitCode -eq 0) {
        Write-Host "   Visual Studio Build Tools 安装完成!" -ForegroundColor Green
    } else {
        Write-Host "   安装可能未完成，请手动检查" -ForegroundColor Yellow
    }
}

# 安装 vcpkg
function Install-Vcpkg {
    $vcpkgRoot = "C:\vcpkg"

    if (!(Test-Path $vcpkgRoot)) {
        Write-Host "[5/6] 安装 vcpkg..." -ForegroundColor Yellow

        Write-Host "   克隆 vcpkg 仓库..." -ForegroundColor Cyan
        git clone https://github.com/Microsoft/vcpkg.git $vcpkgRoot

        Write-Host "   构建 vcpkg..." -ForegroundColor Cyan
        & "$vcpkgRoot\bootstrap-vcpkg.bat"

        Write-Host "   集成到系统..." -ForegroundColor Cyan
        & "$vcpkgRoot\vcpkg" integrate install

        Write-Host "   vcpkg 安装完成!" -ForegroundColor Green
    } else {
        Write-Host "[5/6] vcpkg 已安装" -ForegroundColor Green
    }
}

# 安装项目依赖
function Install-ProjectDependencies {
    Write-Host "[6/6] 安装项目依赖..." -ForegroundColor Yellow

    $vcpkgRoot = "C:\vcpkg"
    $vcpkg = "$vcpkgRoot\vcpkg.exe"

    if (!(Test-Path $vcpkg)) {
        Write-Host "   vcpkg 未找到，跳过依赖安装" -ForegroundColor Yellow
        return
    }

    $dependencies = @(
        "ffmpeg:x64-windows",
        "openssl:x64-windows",
        "nlohmann-json:x64-windows"
    )

    foreach ($dep in $dependencies) {
        Write-Host "   安装 $dep..." -ForegroundColor Cyan
        & $vcpkg install $dep
    }

    Write-Host "   项目依赖安装完成!" -ForegroundColor Green
}

# 创建环境变量配置脚本
function Create-EnvScript {
    $scriptPath = "$PSScriptRoot\cpp-dev-env.cmd"

    $content = @"
@echo off
REM C++ 开发环境变量配置脚本
REM 使用方法: 在每次打开新终端时运行此脚本

echo 设置 C++ 开发环境变量...

REM Visual Studio
if exist "C:\Program Files\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat" (
    call "C:\Program Files\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
) else if exist "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat" (
    call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
)

REM CMake
if exist "C:\Program Files\CMake\bin\cmake.exe" (
    set "PATH=%PATH%;C:\Program Files\CMake\bin"
)

REM vcpkg
if exist "C:\vcpkg\vcpkg.exe" (
    set "VCPKG_ROOT=C:\vcpkg"
    set "PATH=%PATH%;C:\vcpkg"
)

echo 环境变量设置完成!
echo.
"@

    $content | Out-File -FilePath $scriptPath -Encoding ASCII
    Write-Host "   环境变量脚本已创建: $scriptPath" -ForegroundColor Green
}

# 主函数
function Main {
    Write-Host "检查系统环境..." -ForegroundColor Cyan
    Write-Host ""

    # 显示选择菜单
    Write-Host "请选择安装选项:" -ForegroundColor Cyan
    Write-Host "1. 完整安装 (推荐) - Git, CMake, VS Build Tools, vcpkg, 项目依赖" -ForegroundColor White
    Write-Host "2. 基础安装 - Git, CMake, VS Build Tools" -ForegroundColor White
    Write-Host "3. 仅安装 vcpkg 和项目依赖" -ForegroundColor White
    Write-Host "4. 退出" -ForegroundColor White
    Write-Host ""

    $choice = Read-Host "请输入选项 (1-4)"

    switch ($choice) {
        "1" {
            Install-Chocolatey
            Install-Git
            Install-CMake
            Install-VSBuildTools
            Install-Vcpkg
            Install-ProjectDependencies
            Create-EnvScript
        }
        "2" {
            Install-Chocolatey
            Install-Git
            Install-CMake
            Install-VSBuildTools
            Create-EnvScript
        }
        "3" {
            Install-Vcpkg
            Install-ProjectDependencies
            Create-EnvScript
        }
        "4" {
            Write-Host "退出安装" -ForegroundColor Yellow
            exit
        }
        default {
            Write-Host "无效选项" -ForegroundColor Red
            exit 1
        }
    }

    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "   安装完成!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "后续步骤:" -ForegroundColor Yellow
    Write-Host "1. 重启终端以使环境变量生效" -ForegroundColor White
    Write-Host "2. 或运行: scripts\cpp-dev-env.cmd" -ForegroundColor White
    Write-Host "3. 验证安装:" -ForegroundColor White
    Write-Host "   cmake --version" -ForegroundColor Gray
    Write-Host "   git --version" -ForegroundColor Gray
    Write-Host "   cl (VS 开发者命令提示符)" -ForegroundColor Gray
    Write-Host ""
}

# 运行主函数
Main
