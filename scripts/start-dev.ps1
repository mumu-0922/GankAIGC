[CmdletBinding()]
param(
    [switch]$SkipDocker,
    [switch]$NoRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "[start-dev] $Message"
}

function Write-Warn {
    param([string]$Message)
    Write-Warning "[start-dev] $Message"
}

function Fail {
    param([string]$Message)
    Write-Error "[start-dev] $Message"
    exit 1
}

function Get-RepoRoot {
    if ($PSScriptRoot) {
        return (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
    }
    return (Resolve-Path -LiteralPath ".").Path
}

function Get-PortOwner {
    param([int]$Port)

    $connections = @()
    try {
        $connections = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction Stop)
    } catch {
        $connections = @()
    }

    if ($connections.Count -gt 0) {
        return $connections | ForEach-Object {
            $processName = "<unknown>"
            try {
                $processName = (Get-Process -Id $_.OwningProcess -ErrorAction Stop).ProcessName
            } catch {
                $processName = "<exited>"
            }

            [PSCustomObject]@{
                PID = $_.OwningProcess
                ProcessName = $processName
                LocalAddress = $_.LocalAddress
                LocalPort = $_.LocalPort
            }
        }
    }

    return @()
}

function Get-DotEnvValue {
    param(
        [string]$Path,
        [string]$Name
    )

    foreach ($line in Get-Content -LiteralPath $Path) {
        $trimmed = $line.Trim()
        if ($trimmed.Length -eq 0 -or $trimmed.StartsWith("#")) {
            continue
        }
        if ($trimmed -match "^\s*$([regex]::Escape($Name))\s*=\s*(.*)\s*$") {
            $value = $Matches[1].Trim()
            if (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'"))) {
                $value = $value.Substring(1, $value.Length - 2)
            }
            return $value
        }
    }

    return $null
}

function Protect-DatabaseUrl {
    param([string]$Url)

    if ([string]::IsNullOrWhiteSpace($Url)) {
        return "<empty>"
    }

    return ($Url -replace "([a-z][a-z0-9+.-]*://[^:/@?#]+:)([^@/?#]+)(@)", '$1****$3')
}

function Test-DatabaseUrl {
    param([string]$Url)

    if ([string]::IsNullOrWhiteSpace($Url)) {
        Fail "package/.env 中未找到 DATABASE_URL。请参考 README 配置 PostgreSQL 连接。"
    }

    if ($Url -notmatch "^(postgresql|postgresql\+psycopg)://") {
        Fail "DATABASE_URL 必须使用 postgresql:// 或 postgresql+psycopg://，当前为：$(Protect-DatabaseUrl $Url)"
    }

    try {
        [void]([System.Uri]$Url)
    } catch {
        Fail "DATABASE_URL 不是有效 URL，请检查用户名、密码特殊字符是否已 URL 编码。当前值：$(Protect-DatabaseUrl $Url)"
    }
}

function Test-LocalPostgres {
    Write-Step "检查 127.0.0.1:5432 PostgreSQL 端口..."
    try {
        return [bool](Test-NetConnection 127.0.0.1 -Port 5432 -InformationLevel Quiet -WarningAction SilentlyContinue)
    } catch {
        Write-Warn "Test-NetConnection 执行失败：$($_.Exception.Message)"
        return $false
    }
}

function Test-DockerCli {
    $docker = Get-Command docker -ErrorAction SilentlyContinue
    if (-not $docker) {
        return $false
    }

    & docker version --format "{{.Client.Version}}" *> $null
    return ($LASTEXITCODE -eq 0)
}

function Start-PostgresWithDocker {
    param([string]$RepoRoot)

    Write-Step "5432 不通，尝试使用 Docker 启动 PostgreSQL..."
    if (-not (Test-DockerCli)) {
        Write-Warn "Docker CLI 不可用或 Docker Desktop 未启动。"
        return $false
    }

    Write-Step "优先尝试 docker start gankaigc-postgres..."
    & docker start gankaigc-postgres
    if ($LASTEXITCODE -eq 0) {
        Start-Sleep -Seconds 3
        return (Test-LocalPostgres)
    }

    $composeFile = Join-Path $RepoRoot "docker-compose.yml"
    if (-not (Test-Path -LiteralPath $composeFile)) {
        Write-Warn "未找到 docker-compose.yml，无法通过 Compose 启动 postgres 服务。"
        return $false
    }

    Write-Step "未能直接启动 gankaigc-postgres，尝试 docker compose up -d postgres..."
    Push-Location $RepoRoot
    try {
        & docker compose up -d postgres
        if ($LASTEXITCODE -ne 0) {
            Write-Warn "docker compose up -d postgres 失败。若使用 .env.docker，请确认已创建并配置 POSTGRES_PASSWORD。"
            return $false
        }
    } finally {
        Pop-Location
    }

    for ($i = 1; $i -le 10; $i++) {
        Start-Sleep -Seconds 2
        if (Test-LocalPostgres) {
            return $true
        }
        Write-Step "等待 PostgreSQL 监听 5432... ($i/10)"
    }

    return $false
}

$repoRoot = Get-RepoRoot
$packageDir = Join-Path $repoRoot "package"
$envFile = Join-Path $packageDir ".env"
$mainPy = Join-Path $packageDir "main.py"

Write-Step "仓库根目录: $repoRoot"
Write-Step "配置文件: $envFile"
Write-Step "启动入口: $mainPy"

if (-not (Test-Path -LiteralPath $mainPy)) {
    Fail "未找到 package/main.py，请确认从仓库根目录或 scripts/start-dev.ps1 运行。"
}

Write-Step "检查 9800 端口占用..."
$portOwners = @(Get-PortOwner -Port 9800)
if ($portOwners.Count -gt 0) {
    Write-Warn "9800 端口已被占用，脚本默认不会杀进程。"
    $portOwners | Format-Table -AutoSize | Out-String | Write-Host
    Fail "请先关闭对应程序，或确认不是已有 GankAIGC 实例后手动停止进程。"
}
Write-Step "9800 端口可用。"

if (-not (Test-Path -LiteralPath $envFile)) {
    Fail "未找到 package/.env。请参考 README 的配置说明创建 .env，并配置 DATABASE_URL。"
}

$databaseUrl = Get-DotEnvValue -Path $envFile -Name "DATABASE_URL"
Test-DatabaseUrl -Url $databaseUrl
Write-Step "DATABASE_URL: $(Protect-DatabaseUrl $databaseUrl)"

$postgresReady = Test-LocalPostgres
if (-not $postgresReady) {
    if ($SkipDocker) {
        Fail "127.0.0.1:5432 不通，且已指定 -SkipDocker，不会尝试启动 Docker/PostgreSQL。请手动启动 PostgreSQL 后重试。"
    }

    $postgresReady = Start-PostgresWithDocker -RepoRoot $repoRoot
}

if (-not $postgresReady) {
    Fail "PostgreSQL 仍不可连接。请检查 Docker Desktop、gankaigc-postgres 容器、.env.docker/POSTGRES_PASSWORD，或手动启动本地 PostgreSQL。"
}

Write-Step "PostgreSQL 端口可连接。"

if ($NoRun) {
    Write-Step "诊断通过；由于指定 -NoRun，不启动后端。"
    exit 0
}

Write-Step "诊断通过，启动后端: python main.py"
Push-Location $packageDir
try {
    & python main.py
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
