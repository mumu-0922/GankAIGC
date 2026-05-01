param(
    [string]$PostgresRoot = "",
    [string]$PostgresZip = "",
    [string]$PostgresZipUrl = "",
    [string]$OutputDir = "",
    [switch]$SkipExeBuild,
    [switch]$CreateZip
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$PackageDir = $PSScriptRoot
$RepoRoot = Split-Path -Parent $PackageDir
if ([string]::IsNullOrWhiteSpace($OutputDir)) {
    $OutputDir = Join-Path $PackageDir 'dist\GankAIGC-Windows'
}

function Write-Step([string]$Message) {
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Write-Ok([string]$Message) {
    Write-Host "✓ $Message" -ForegroundColor Green
}

function Assert-LastExitCode([string]$CommandName) {
    if ($LASTEXITCODE -ne 0) {
        throw "$CommandName 执行失败，退出码: $LASTEXITCODE"
    }
}

function Test-PostgresRoot([string]$Root) {
    if ([string]::IsNullOrWhiteSpace($Root)) { return $false }
    return (
        (Test-Path -LiteralPath (Join-Path $Root 'bin\initdb.exe')) -and
        (Test-Path -LiteralPath (Join-Path $Root 'bin\pg_ctl.exe')) -and
        (Test-Path -LiteralPath (Join-Path $Root 'bin\psql.exe')) -and
        (Test-Path -LiteralPath (Join-Path $Root 'bin\createdb.exe')) -and
        (Test-Path -LiteralPath (Join-Path $Root 'lib')) -and
        (Test-Path -LiteralPath (Join-Path $Root 'share'))
    )
}

function Find-PostgresRoot([string]$SearchRoot) {
    if (Test-PostgresRoot $SearchRoot) { return (Resolve-Path -LiteralPath $SearchRoot).Path }

    $candidate = Get-ChildItem -LiteralPath $SearchRoot -Recurse -Filter initdb.exe -File -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($null -eq $candidate) { return $null }

    $binDir = Split-Path -Parent $candidate.FullName
    $root = Split-Path -Parent $binDir
    if (Test-PostgresRoot $root) { return (Resolve-Path -LiteralPath $root).Path }
    return $null
}


function Expand-PostgresArchive([string]$ZipPath, [string]$DestinationPath) {
    New-Item -ItemType Directory -Force -Path $DestinationPath | Out-Null

    $tar = Get-Command tar.exe -ErrorAction SilentlyContinue
    if ($null -ne $tar) {
        Write-Step '使用 tar.exe 解压 PostgreSQL ZIP'
        & $tar.Source -xf $ZipPath -C $DestinationPath
        if ($LASTEXITCODE -eq 0) { return }
        Write-Host 'tar.exe 解压失败，尝试 PowerShell Expand-Archive...' -ForegroundColor Yellow
    }

    Expand-Archive -LiteralPath $ZipPath -DestinationPath $DestinationPath -Force
}

function Resolve-PortablePostgresRoot() {
    $tempRoot = $null

    if (-not [string]::IsNullOrWhiteSpace($PostgresZipUrl)) {
        $tempRoot = Join-Path $env:TEMP ('gankaigc-pg-' + [Guid]::NewGuid().ToString('N'))
        New-Item -ItemType Directory -Force -Path $tempRoot | Out-Null
        $downloadPath = Join-Path $tempRoot 'postgres.zip'
        Write-Step "下载便携 PostgreSQL：$PostgresZipUrl"
        Invoke-WebRequest -Uri $PostgresZipUrl -OutFile $downloadPath
        $script:PostgresZip = $downloadPath
    }

    if (-not [string]::IsNullOrWhiteSpace($PostgresZip)) {
        if (-not (Test-Path -LiteralPath $PostgresZip)) {
            throw "找不到 PostgreSQL ZIP：$PostgresZip"
        }
        if ($null -eq $tempRoot) {
            $tempRoot = Join-Path $env:TEMP ('gankaigc-pg-' + [Guid]::NewGuid().ToString('N'))
            New-Item -ItemType Directory -Force -Path $tempRoot | Out-Null
        }
        $extractDir = Join-Path $tempRoot 'extract'
        Write-Step "解压便携 PostgreSQL：$PostgresZip"
        Expand-PostgresArchive -ZipPath $PostgresZip -DestinationPath $extractDir
        $root = Find-PostgresRoot $extractDir
        if ($null -eq $root) { throw 'ZIP 中没有找到可用的 PostgreSQL bin/initdb.exe。' }
        return $root
    }

    if (-not [string]::IsNullOrWhiteSpace($PostgresRoot)) {
        if (-not (Test-Path -LiteralPath $PostgresRoot)) {
            throw "找不到 PostgreSQL 目录：$PostgresRoot"
        }
        $root = Find-PostgresRoot $PostgresRoot
        if ($null -eq $root) { throw "指定目录不是可用的 PostgreSQL 目录：$PostgresRoot" }
        return $root
    }

    $defaultRoot = Join-Path $PackageDir 'postgres-portable'
    if (Test-Path -LiteralPath $defaultRoot) {
        $root = Find-PostgresRoot $defaultRoot
        if ($null -ne $root) { return $root }
    }

    throw @"
未提供便携 PostgreSQL。
任选一种方式：
1. 下载 PostgreSQL Windows x86-64 binaries ZIP，然后运行：
   .\build-oneclick.ps1 -PostgresZip C:\path\postgresql-windows-x64-binaries.zip
2. 传入已解压目录，例如：
   .\build-oneclick.ps1 -PostgresRoot C:\pgsql
3. 把已解压的 pgsql 内容放到 package\postgres-portable 后再运行：
   .\build-oneclick.ps1
"@
}

function Copy-PortablePostgres([string]$SourceRoot, [string]$DestinationRoot) {
    Write-Step "复制便携 PostgreSQL：$SourceRoot"
    New-Item -ItemType Directory -Force -Path $DestinationRoot | Out-Null
    foreach ($name in @('bin', 'lib', 'share')) {
        $src = Join-Path $SourceRoot $name
        if (-not (Test-Path -LiteralPath $src)) { throw "PostgreSQL 缺少必要目录：$src" }
        Copy-Item -LiteralPath $src -Destination (Join-Path $DestinationRoot $name) -Recurse -Force
    }
    foreach ($name in @('include', 'doc')) {
        $src = Join-Path $SourceRoot $name
        if (Test-Path -LiteralPath $src) {
            Copy-Item -LiteralPath $src -Destination (Join-Path $DestinationRoot $name) -Recurse -Force
        }
    }
}

function Remove-OutputDirSafely([string]$Dir) {
    if (-not (Test-Path -LiteralPath $Dir)) { return }
    $resolved = (Resolve-Path -LiteralPath $Dir).Path
    $distRoot = (Resolve-Path -LiteralPath (Join-Path $PackageDir 'dist')).Path
    if (-not $resolved.StartsWith($distRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "拒绝删除非 package\dist 下的输出目录：$resolved"
    }
    Remove-Item -LiteralPath $resolved -Recurse -Force
}

try {
    Write-Host ''
    Write-Host '==========================================' -ForegroundColor Cyan
    Write-Host ' GankAIGC Windows 一键整合包构建' -ForegroundColor Cyan
    Write-Host '==========================================' -ForegroundColor Cyan

    Set-Location $PackageDir

    if (-not $SkipExeBuild) {
        Write-Step '构建 GankAIGC.exe'
        & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PackageDir 'build.ps1')
        Assert-LastExitCode 'build.ps1'
    }

    $exePath = Join-Path $PackageDir 'dist\GankAIGC.exe'
    if (-not (Test-Path -LiteralPath $exePath)) {
        throw "找不到 $exePath。请先运行 package\build.ps1，或去掉 -SkipExeBuild。"
    }

    $pgRoot = Resolve-PortablePostgresRoot

    $outputFull = [System.IO.Path]::GetFullPath($OutputDir)
    $distDir = Join-Path $PackageDir 'dist'
    New-Item -ItemType Directory -Force -Path $distDir | Out-Null
    Remove-OutputDirSafely $outputFull
    New-Item -ItemType Directory -Force -Path $outputFull | Out-Null

    Write-Step "生成一键包目录：$outputFull"
    Copy-Item -LiteralPath $exePath -Destination (Join-Path $outputFull 'GankAIGC.exe') -Force
    Copy-Item -LiteralPath (Join-Path $PackageDir 'windows-oneclick\start.bat') -Destination (Join-Path $outputFull 'start.bat') -Force
    Copy-Item -LiteralPath (Join-Path $PackageDir 'windows-oneclick\stop.bat') -Destination (Join-Path $outputFull 'stop.bat') -Force
    Copy-Item -LiteralPath (Join-Path $PackageDir 'windows-oneclick\.env.template') -Destination (Join-Path $outputFull '.env') -Force
    Copy-Item -LiteralPath (Join-Path $PackageDir 'windows-oneclick\.env.template') -Destination (Join-Path $outputFull '.env.template') -Force
    Copy-Item -LiteralPath (Join-Path $PackageDir 'windows-oneclick\README.txt') -Destination (Join-Path $outputFull 'README.txt') -Force
    Copy-Item -LiteralPath (Join-Path $PackageDir 'windows-oneclick\runtime') -Destination (Join-Path $outputFull 'runtime') -Recurse -Force
    Copy-PortablePostgres $pgRoot (Join-Path $outputFull 'postgres')
    New-Item -ItemType Directory -Force -Path (Join-Path $outputFull 'data') | Out-Null
    New-Item -ItemType Directory -Force -Path (Join-Path $outputFull 'logs') | Out-Null

    if ($CreateZip) {
        $zipPath = Join-Path $PackageDir 'dist\GankAIGC-Windows-OneClick.zip'
        if (Test-Path -LiteralPath $zipPath) { Remove-Item -LiteralPath $zipPath -Force }
        Write-Step "压缩一键包：$zipPath"
        Compress-Archive -LiteralPath $outputFull -DestinationPath $zipPath -Force
        Write-Ok "ZIP 已生成：$zipPath"
    }

    Write-Host ''
    Write-Host '==========================================' -ForegroundColor Cyan
    Write-Ok 'Windows 一键整合包构建完成'
    Write-Host "目录：$outputFull" -ForegroundColor Green
    Write-Host '运行：双击 start.bat' -ForegroundColor Yellow
    Write-Host '停止：双击 stop.bat' -ForegroundColor Yellow
    Write-Host '==========================================' -ForegroundColor Cyan
} catch {
    Write-Host ''
    Write-Host '❌ 构建失败：' -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}
