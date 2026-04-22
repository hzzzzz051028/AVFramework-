# CMake 安装脚本
Write-Host "[1/4] 安装 CMake..." -ForegroundColor Yellow

# 创建临时目录
$tempDir = "C:\Users\1000003244\Desktop\video_test\temp"
if (!(Test-Path $tempDir)) {
    New-Item -ItemType Directory -Path $tempDir -Force | Out-Null
}

# 下载 CMake
$cmakeUrl = 'https://github.com/Kitware/CMake/releases/download/v3.28.1/cmake-3.28.1-windows-x86_64.msi'
$cmakeInstaller = Join-Path $tempDir 'cmake-installer.msi'

Write-Host "  下载 CMake..." -ForegroundColor Cyan
try {
    Invoke-WebRequest -Uri $cmakeUrl -OutFile $cmakeInstaller -UseBasicParsing
    Write-Host "  下载完成!" -ForegroundColor Green
} catch {
    Write-Host "  下载失败: $_" -ForegroundColor Red
    exit 1
}

Write-Host "  安装 CMake..." -ForegroundColor Cyan
try {
    $process = Start-Process msiexec -ArgumentList '/i', $cmakeInstaller, '/quiet', 'ADD_CMAKE_TO_PATH=System' -Wait -PassThru
    if ($process.ExitCode -eq 0) {
        Write-Host "  CMake 安装完成!" -ForegroundColor Green

        # 清理
        Remove-Item $cmakeInstaller -Force -ErrorAction SilentlyContinue
    } else {
        Write-Host "  安装失败，错误代码: $($process.ExitCode)" -ForegroundColor Red
    }
} catch {
    Write-Host "  安装失败: $_" -ForegroundColor Red
}
