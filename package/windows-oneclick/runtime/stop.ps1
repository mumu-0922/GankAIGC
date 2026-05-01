Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$BundleRoot = Split-Path -Parent $PSScriptRoot
$EnvPath = Join-Path $BundleRoot '.env'
$DataDir = Join-Path $BundleRoot 'data\postgres'
$PgCtl = Join-Path $BundleRoot 'postgres\bin\pg_ctl.exe'

function Write-Step([string]$Message) {
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Write-Ok([string]$Message) {
    Write-Host "✓ $Message" -ForegroundColor Green
}

function Read-DotEnv([string]$Path) {
    $settings = @{}
    if (-not (Test-Path -LiteralPath $Path)) { return $settings }
    foreach ($line in [System.IO.File]::ReadLines($Path, [System.Text.Encoding]::UTF8)) {
        $trimmed = $line.Trim()
        if ($trimmed.Length -eq 0 -or $trimmed.StartsWith('#')) { continue }
        $idx = $trimmed.IndexOf('=')
        if ($idx -le 0) { continue }
        $settings[$trimmed.Substring(0, $idx).Trim()] = $trimmed.Substring($idx + 1).Trim()
    }
    return $settings
}

function Stop-GankAIGCProcesses() {
    Write-Step '关闭当前一键包启动的 GankAIGC.exe...'
    $targetExe = Join-Path $BundleRoot 'GankAIGC.exe'
    $targets = Get-CimInstance Win32_Process -Filter "name = 'GankAIGC.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.ExecutablePath -and [string]::Equals($_.ExecutablePath, $targetExe, [System.StringComparison]::OrdinalIgnoreCase) }

    if (-not $targets) {
        Write-Ok '没有发现需要关闭的 GankAIGC.exe'
        return
    }

    foreach ($proc in $targets) {
        Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
        Write-Ok "已关闭 GankAIGC.exe PID=$($proc.ProcessId)"
    }
}

function Stop-Postgres() {
    if (-not (Test-Path -LiteralPath $PgCtl)) {
        Write-Ok '未找到 pg_ctl.exe，跳过 PostgreSQL 停止'
        return
    }
    if (-not (Test-Path -LiteralPath (Join-Path $DataDir 'PG_VERSION'))) {
        Write-Ok '未找到 PostgreSQL 数据目录，跳过 PostgreSQL 停止'
        return
    }

    Write-Step '停止内置 PostgreSQL...'
    & $PgCtl -D $DataDir stop -m fast
    if ($LASTEXITCODE -eq 0) {
        Write-Ok 'PostgreSQL 已停止'
    } else {
        Write-Host 'PostgreSQL 可能本来就没有运行。' -ForegroundColor Yellow
    }
}

try {
    Write-Host ''
    Write-Host '==========================================' -ForegroundColor Cyan
    Write-Host ' GankAIGC Windows 一键停止' -ForegroundColor Cyan
    Write-Host '==========================================' -ForegroundColor Cyan

    $null = Read-DotEnv $EnvPath
    Stop-GankAIGCProcesses
    Stop-Postgres
    Write-Ok '停止流程完成'
} catch {
    Write-Host ''
    Write-Host '❌ 停止失败：' -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}

