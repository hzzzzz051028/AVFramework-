# Windows C++ Development Environment Setup Script
# Usage: powershell -ExecutionPolicy Bypass -File setup-cpp-env.ps1

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "`n[$stepCount/$totalSteps] $Message" -ForegroundColor Yellow
    $script:stepCount++
}

$script:stepCount = 1
$script:totalSteps = 4

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "   C++ Development Environment Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Check admin privileges
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "`nError: Please run this script as Administrator" -ForegroundColor Red
    Write-Host "Right-click PowerShell and select 'Run as Administrator'" -ForegroundColor Yellow
    exit 1
}

# Create temp directory
$tempDir = "C:\Users\1000003244\Desktop\video_test\temp"
if (!(Test-Path $tempDir)) {
    New-Item -ItemType Directory -Path $tempDir -Force | Out-Null
}

# ==================== Install CMake ====================
Write-Step "Installing CMake..."

if (Get-Command cmake -ErrorAction SilentlyContinue) {
    Write-Host "  CMake already installed: $(cmake --version)" -ForegroundColor Green
} else {
    $cmakeUrl = 'https://github.com/Kitware/CMake/releases/download/v3.28.1/cmake-3.28.1-windows-x86_64.msi'
    $cmakeInstaller = Join-Path $tempDir 'cmake-installer.msi'

    Write-Host "  Downloading CMake (~40MB)..." -ForegroundColor Cyan
    try {
        Invoke-WebRequest -Uri $cmakeUrl -OutFile $cmakeInstaller -UseBasicParsing
        Write-Host "  Download complete!" -ForegroundColor Green

        Write-Host "  Installing..." -ForegroundColor Cyan
        $process = Start-Process msiexec -ArgumentList '/i', $cmakeInstaller, '/quiet', 'ADD_CMAKE_TO_PATH=System' -Wait -PassThru

        if ($process.ExitCode -eq 0) {
            Write-Host "  CMake installed successfully!" -ForegroundColor Green
            Remove-Item $cmakeInstaller -Force -ErrorAction SilentlyContinue
        } else {
            Write-Host "  Installation failed, error code: $($process.ExitCode)" -ForegroundColor Yellow
        }
    } catch {
        Write-Host "  Installation failed: $_" -ForegroundColor Red
    }
}

# ==================== Check Visual Studio Build Tools ====================
Write-Step "Checking Visual Studio Build Tools..."

$vsInstalled = $false
$vsPaths = @(
    "C:\Program Files\Microsoft Visual Studio\2022\BuildTools",
    "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools",
    "C:\Program Files\Microsoft Visual Studio\2022\Community",
    "C:\Program Files\Microsoft Visual Studio\2022\Professional",
    "C:\Program Files\Microsoft Visual Studio\2022\Enterprise"
)

foreach ($path in $vsPaths) {
    if (Test-Path $path) {
        $vsInstalled = $true
        Write-Host "  Visual Studio found: $path" -ForegroundColor Green
        break
    }
}

if (-not $vsInstalled) {
    Write-Host "  Visual Studio Build Tools not installed" -ForegroundColor Yellow
    Write-Host "  Please download and install manually:" -ForegroundColor Cyan
    Write-Host "  https://aka.ms/vs/17/release/vs_BuildTools.exe" -ForegroundColor White
    Write-Host "`n  During installation, select:" -ForegroundColor Yellow
    Write-Host "    - Desktop development with C++" -ForegroundColor White
    Write-Host "    - MSVC v143 build tools" -ForegroundColor White
    Write-Host "    - Windows SDK" -ForegroundColor White

    $installNow = Read-Host "`n  Open download page now? (Y/N)"
    if ($installNow -eq 'Y' -or $installNow -eq 'y') {
        Start-Process "https://aka.ms/vs/17/release/vs_BuildTools.exe"
        Write-Host "`n  Please run this script again after installation" -ForegroundColor Yellow
        exit 0
    }
}

# ==================== Install vcpkg ====================
Write-Step "Installing vcpkg..."

$vcpkgRoot = "C:\vcpkg"

if (Test-Path $vcpkgRoot) {
    Write-Host "  vcpkg already installed" -ForegroundColor Green
} else {
    Write-Host "  Cloning vcpkg repository (~100MB)..." -ForegroundColor Cyan

    try {
        # Check git
        if (!(Get-Command git -ErrorAction SilentlyContinue)) {
            Write-Host "  Error: Git not installed" -ForegroundColor Red
            Write-Host "  Please install Git first: https://git-scm.com/" -ForegroundColor Yellow
            exit 1
        }

        git clone --depth 1 https://github.com/Microsoft/vcpkg.git $vcpkgRoot 2>$null

        if ($LASTEXITCODE -eq 0) {
            Write-Host "  Clone complete!" -ForegroundColor Green

            Write-Host "  Building vcpkg..." -ForegroundColor Cyan
            & "$vcpkgRoot\bootstrap-vcpkg.bat"

            Write-Host "  Integrating with system..." -ForegroundColor Cyan
            & "$vcpkgRoot\vcpkg" integrate install

            Write-Host "  vcpkg installed successfully!" -ForegroundColor Green
        } else {
            Write-Host "  Clone failed" -ForegroundColor Red
        }
    } catch {
        Write-Host "  Installation failed: $_" -ForegroundColor Red
    }
}

# ==================== Install Project Dependencies ====================
Write-Step "Installing project dependencies..."

$vcpkg = "$vcpkgRoot\vcpkg.exe"

if (Test-Path $vcpkg) {
    Write-Host "  Installing FFmpeg, OpenSSL, nlohmann-json using vcpkg..." -ForegroundColor Cyan
    Write-Host "  This may take 10-20 minutes, please be patient..." -ForegroundColor Yellow

    $dependencies = @(
        "ffmpeg:x64-windows",
        "openssl:x64-windows",
        "nlohmann-json:x64-windows"
    )

    foreach ($dep in $dependencies) {
        Write-Host "`n  Installing $dep..." -ForegroundColor Cyan
        & $vcpkg install $dep
    }

    Write-Host "`n  Project dependencies installed!" -ForegroundColor Green
} else {
    Write-Host "  vcpkg not found, skipping dependency installation" -ForegroundColor Yellow
}

# ==================== Installation Complete ====================
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "   Installation Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan

Write-Host "`nPlease restart terminal for environment variables to take effect" -ForegroundColor Yellow
Write-Host "`nVerify installation:" -ForegroundColor Cyan
Write-Host "  cmake --version" -ForegroundColor Gray
Write-Host "  git --version" -ForegroundColor Gray
Write-Host "  C:\vcpkg\vcpkg version" -ForegroundColor Gray
Write-Host "`nFor compiler, use VS Developer Command Prompt" -ForegroundColor Yellow
Write-Host "  Start Menu -> Visual Studio 2022 -> x64 Native Tools Command Prompt" -ForegroundColor Gray
