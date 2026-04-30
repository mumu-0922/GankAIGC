# GankAIGC - Windows 构建脚本
# 用于在 Windows 上构建可执行文件

$ErrorActionPreference = "Stop"

function Assert-LastExitCode {
    param([string]$Step)
    if ($LASTEXITCODE -ne 0) {
        throw "命令失败: $Step (exit code: $LASTEXITCODE)"
    }
}

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "GankAIGC - Windows 构建脚本" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

# 检查 Python
Write-Host ""
Write-Host "1. 检查 Python 环境..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    Write-Host $pythonVersion -ForegroundColor Green
    $pythonVersionCheck = python -c "import sys; raise SystemExit(0 if (3, 9) <= sys.version_info[:2] < (3, 13) else 1)"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "错误: 当前打包脚本要求 Python 3.9 - 3.12。请切换到 Python 3.11/3.12 后重试。" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "错误: 未找到可用的 Python 3.9 - 3.12，请先安装或切换环境。" -ForegroundColor Red
    exit 1
}

# 检查 Node.js
Write-Host ""
Write-Host "2. 检查 Node.js 环境..." -ForegroundColor Yellow
try {
    $nodeVersion = node --version 2>&1
    Write-Host $nodeVersion -ForegroundColor Green
} catch {
    Write-Host "错误: 未找到 Node.js，请先安装 Node.js 18+" -ForegroundColor Red
    exit 1
}

# 创建虚拟环境并安装依赖
Write-Host ""
Write-Host "3. 安装后端依赖..." -ForegroundColor Yellow
if (-not (Test-Path "venv")) {
    python -m venv venv
    Assert-LastExitCode "python -m venv venv"
}
& .\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Assert-LastExitCode "python -m pip install -r requirements.txt"

# 构建前端
Write-Host ""
Write-Host "4. 构建前端..." -ForegroundColor Yellow
Set-Location frontend
npm install
Assert-LastExitCode "npm install"
npm run build
Assert-LastExitCode "npm run build"
Set-Location ..

# 复制前端构建产物
Write-Host ""
Write-Host "5. 复制前端构建产物..." -ForegroundColor Yellow
if (Test-Path "static") {
    Remove-Item -Recurse -Force static
}
Copy-Item -Recurse frontend\dist static

# 使用 PyInstaller 打包
Write-Host ""
Write-Host "6. 使用 PyInstaller 打包..." -ForegroundColor Yellow
pyinstaller app.spec --clean
Assert-LastExitCode "pyinstaller app.spec --clean"

if (-not (Test-Path "dist\GankAIGC.exe")) {
    throw "构建失败: dist\GankAIGC.exe 未生成"
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "构建完成!" -ForegroundColor Green
Write-Host "可执行文件位置: dist\GankAIGC.exe" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "运行方式:" -ForegroundColor Yellow
Write-Host "1. 将 dist\GankAIGC.exe 复制到任意目录"
Write-Host "2. 首次运行会自动创建 .env 配置文件"
Write-Host "3. 编辑 .env 文件，填入 API Key 等配置"
Write-Host "4. 再次运行程序，将自动打开浏览器"
Write-Host ""
