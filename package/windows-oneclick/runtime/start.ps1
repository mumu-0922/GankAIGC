Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$BundleRoot = Split-Path -Parent $PSScriptRoot
$EnvPath = Join-Path $BundleRoot '.env'
$EnvTemplatePath = Join-Path $BundleRoot '.env.template'
$LogDir = Join-Path $BundleRoot 'logs'
$DataDir = Join-Path $BundleRoot 'data\postgres'
$PgBin = Join-Path $BundleRoot 'postgres\bin'

function Write-Step([string]$Message) {
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Write-Ok([string]$Message) {
    Write-Host "✓ $Message" -ForegroundColor Green
}

function Write-Warn([string]$Message) {
    Write-Host "⚠ $Message" -ForegroundColor Yellow
}

function New-RandomBytes([int]$Length) {
    $bytes = New-Object byte[] $Length
    [System.Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
    return $bytes
}

function New-RandomHex([int]$Bytes) {
    $bytes = New-RandomBytes $Bytes
    return ([BitConverter]::ToString($bytes) -replace '-', '').ToLowerInvariant()
}

function New-UrlSafeBase64([int]$Bytes) {
    $raw = [Convert]::ToBase64String((New-RandomBytes $Bytes))
    return $raw.Replace('+', '-').Replace('/', '_')
}

function Test-Placeholder([AllowNull()][string]$Value) {
    if ([string]::IsNullOrWhiteSpace($Value)) { return $true }
    $v = $Value.Trim()
    return (
        $v.StartsWith('replace-with') -or
        $v.StartsWith('please-change') -or
        $v -eq 'your-api-key-here'
    )
}

function Read-DotEnv([string]$Path) {
    $settings = [ordered]@{}
    if (-not (Test-Path -LiteralPath $Path)) { return $settings }

    foreach ($line in [System.IO.File]::ReadLines($Path, [System.Text.Encoding]::UTF8)) {
        $trimmed = $line.Trim()
        if ($trimmed.Length -eq 0 -or $trimmed.StartsWith('#')) { continue }
        $idx = $trimmed.IndexOf('=')
        if ($idx -le 0) { continue }
        $key = $trimmed.Substring(0, $idx).Trim()
        $value = $trimmed.Substring($idx + 1).Trim()
        if (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'"))) {
            $value = $value.Substring(1, $value.Length - 2)
        }
        $settings[$key] = $value
    }
    return $settings
}

function Get-Setting($Settings, [string]$Name, [string]$Default) {
    if ($Settings.Contains($Name) -and -not [string]::IsNullOrWhiteSpace([string]$Settings[$Name])) {
        return [string]$Settings[$Name]
    }
    return $Default
}

function Set-Default($Settings, [string]$Name, [string]$Default) {
    if (-not $Settings.Contains($Name) -or [string]::IsNullOrWhiteSpace([string]$Settings[$Name])) {
        $Settings[$Name] = $Default
    }
}

function Write-DotEnv($Settings, [string]$Path) {
    $Settings['DATABASE_URL'] = "postgresql://$($Settings['POSTGRES_USER']):$($Settings['POSTGRES_PASSWORD'])@$($Settings['POSTGRES_HOST']):$($Settings['POSTGRES_PORT'])/$($Settings['POSTGRES_DB'])"

    $lines = @(
        '# GankAIGC Windows 一键整合包配置',
        '# 可修改 API Key、模型、后台密码；不要删除 POSTGRES_* 和 DATABASE_URL。',
        '',
        'SERVER_HOST=' + $Settings['SERVER_HOST'],
        'SERVER_PORT=' + $Settings['SERVER_PORT'],
        'APP_ENV=' + $Settings['APP_ENV'],
        'ALLOWED_ORIGINS=' + $Settings['ALLOWED_ORIGINS'],
        'AUTO_OPEN_BROWSER=' + $Settings['AUTO_OPEN_BROWSER'],
        'ENABLE_VERBOSE_AI_LOGS=' + $Settings['ENABLE_VERBOSE_AI_LOGS'],
        '',
        'POSTGRES_HOST=' + $Settings['POSTGRES_HOST'],
        'POSTGRES_PORT=' + $Settings['POSTGRES_PORT'],
        'POSTGRES_DB=' + $Settings['POSTGRES_DB'],
        'POSTGRES_USER=' + $Settings['POSTGRES_USER'],
        'POSTGRES_PASSWORD=' + $Settings['POSTGRES_PASSWORD'],
        'DATABASE_URL=' + $Settings['DATABASE_URL'],
        'REDIS_URL=' + $Settings['REDIS_URL'],
        '',
        'AUTH_RATE_LIMIT_PER_MINUTE=' + $Settings['AUTH_RATE_LIMIT_PER_MINUTE'],
        'REDEEM_RATE_LIMIT_PER_MINUTE=' + $Settings['REDEEM_RATE_LIMIT_PER_MINUTE'],
        'REGISTRATION_ENABLED=' + $Settings['REGISTRATION_ENABLED'],
        'WORD_FORMATTER_ENABLED=' + $Settings['WORD_FORMATTER_ENABLED'],
        'ADMIN_DATABASE_MANAGER_ENABLED=' + $Settings['ADMIN_DATABASE_MANAGER_ENABLED'],
        'ADMIN_DATABASE_WRITE_ENABLED=' + $Settings['ADMIN_DATABASE_WRITE_ENABLED'],
        'INLINE_TASK_WORKER_ENABLED=' + $Settings['INLINE_TASK_WORKER_ENABLED'],
        'TASK_WORKER_POLL_INTERVAL=' + $Settings['TASK_WORKER_POLL_INTERVAL'],
        'TASK_WORKER_HEARTBEAT_INTERVAL=' + $Settings['TASK_WORKER_HEARTBEAT_INTERVAL'],
        'TASK_WORKER_STALE_TIMEOUT_SECONDS=' + $Settings['TASK_WORKER_STALE_TIMEOUT_SECONDS'],
        '',
        'OPENAI_API_KEY=' + $Settings['OPENAI_API_KEY'],
        'OPENAI_BASE_URL=' + $Settings['OPENAI_BASE_URL'],
        'POLISH_MODEL=' + $Settings['POLISH_MODEL'],
        'POLISH_API_KEY=' + $Settings['POLISH_API_KEY'],
        'POLISH_BASE_URL=' + $Settings['POLISH_BASE_URL'],
        'ENHANCE_MODEL=' + $Settings['ENHANCE_MODEL'],
        'ENHANCE_API_KEY=' + $Settings['ENHANCE_API_KEY'],
        'ENHANCE_BASE_URL=' + $Settings['ENHANCE_BASE_URL'],
        'EMOTION_MODEL=' + $Settings['EMOTION_MODEL'],
        'EMOTION_API_KEY=' + $Settings['EMOTION_API_KEY'],
        'EMOTION_BASE_URL=' + $Settings['EMOTION_BASE_URL'],
        'COMPRESSION_MODEL=' + $Settings['COMPRESSION_MODEL'],
        'COMPRESSION_API_KEY=' + $Settings['COMPRESSION_API_KEY'],
        'COMPRESSION_BASE_URL=' + $Settings['COMPRESSION_BASE_URL'],
        '',
        'SECRET_KEY=' + $Settings['SECRET_KEY'],
        'ENCRYPTION_KEY=' + $Settings['ENCRYPTION_KEY'],
        'ALGORITHM=' + $Settings['ALGORITHM'],
        'ACCESS_TOKEN_EXPIRE_MINUTES=' + $Settings['ACCESS_TOKEN_EXPIRE_MINUTES'],
        'USER_ACCESS_TOKEN_EXPIRE_MINUTES=' + $Settings['USER_ACCESS_TOKEN_EXPIRE_MINUTES'],
        'ADMIN_USERNAME=' + $Settings['ADMIN_USERNAME'],
        'ADMIN_PASSWORD=' + $Settings['ADMIN_PASSWORD'],
        'DEFAULT_USAGE_LIMIT=' + $Settings['DEFAULT_USAGE_LIMIT'],
        'SEGMENT_SKIP_THRESHOLD=' + $Settings['SEGMENT_SKIP_THRESHOLD']
    )

    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, (($lines -join [Environment]::NewLine) + [Environment]::NewLine), $utf8NoBom)
}

function Ensure-EnvFile() {
    New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

    if (-not (Test-Path -LiteralPath $EnvPath)) {
        if (Test-Path -LiteralPath $EnvTemplatePath) {
            Copy-Item -LiteralPath $EnvTemplatePath -Destination $EnvPath
        } else {
            New-Item -ItemType File -Force -Path $EnvPath | Out-Null
        }
    }

    $settings = Read-DotEnv $EnvPath

    Set-Default $settings 'SERVER_HOST' '127.0.0.1'
    Set-Default $settings 'SERVER_PORT' '9800'
    Set-Default $settings 'APP_ENV' 'desktop'
    Set-Default $settings 'ALLOWED_ORIGINS' 'http://localhost:9800,http://127.0.0.1:9800'
    Set-Default $settings 'AUTO_OPEN_BROWSER' 'true'
    Set-Default $settings 'ENABLE_VERBOSE_AI_LOGS' 'false'

    Set-Default $settings 'POSTGRES_HOST' '127.0.0.1'
    Set-Default $settings 'POSTGRES_PORT' '55432'
    Set-Default $settings 'POSTGRES_DB' 'ai_polish'
    Set-Default $settings 'POSTGRES_USER' 'ai_polish'
    Set-Default $settings 'POSTGRES_PASSWORD' 'replace-with-generated-postgres-password'
    Set-Default $settings 'DATABASE_URL' ''
    Set-Default $settings 'REDIS_URL' 'redis://localhost:6379/0'

    Set-Default $settings 'AUTH_RATE_LIMIT_PER_MINUTE' '10'
    Set-Default $settings 'REDEEM_RATE_LIMIT_PER_MINUTE' '20'
    Set-Default $settings 'REGISTRATION_ENABLED' 'true'
    Set-Default $settings 'WORD_FORMATTER_ENABLED' 'false'
    Set-Default $settings 'ADMIN_DATABASE_MANAGER_ENABLED' 'true'
    Set-Default $settings 'ADMIN_DATABASE_WRITE_ENABLED' 'false'
    Set-Default $settings 'INLINE_TASK_WORKER_ENABLED' 'true'
    Set-Default $settings 'TASK_WORKER_POLL_INTERVAL' '2'
    Set-Default $settings 'TASK_WORKER_HEARTBEAT_INTERVAL' '30'
    Set-Default $settings 'TASK_WORKER_STALE_TIMEOUT_SECONDS' '1800'

    Set-Default $settings 'OPENAI_API_KEY' 'your-api-key-here'
    Set-Default $settings 'OPENAI_BASE_URL' 'https://api.openai.com/v1'
    Set-Default $settings 'POLISH_MODEL' 'gpt-5.5'
    Set-Default $settings 'POLISH_API_KEY' 'your-api-key-here'
    Set-Default $settings 'POLISH_BASE_URL' 'https://api.openai.com/v1'
    Set-Default $settings 'ENHANCE_MODEL' 'gpt-5.5'
    Set-Default $settings 'ENHANCE_API_KEY' 'your-api-key-here'
    Set-Default $settings 'ENHANCE_BASE_URL' 'https://api.openai.com/v1'
    Set-Default $settings 'EMOTION_MODEL' 'gpt-5.5'
    Set-Default $settings 'EMOTION_API_KEY' 'your-api-key-here'
    Set-Default $settings 'EMOTION_BASE_URL' 'https://api.openai.com/v1'
    Set-Default $settings 'COMPRESSION_MODEL' 'gpt-5.5'
    Set-Default $settings 'COMPRESSION_API_KEY' 'your-api-key-here'
    Set-Default $settings 'COMPRESSION_BASE_URL' 'https://api.openai.com/v1'

    Set-Default $settings 'SECRET_KEY' 'replace-with-generated-secret-key'
    Set-Default $settings 'ENCRYPTION_KEY' 'replace-with-generated-encryption-key'
    Set-Default $settings 'ALGORITHM' 'HS256'
    Set-Default $settings 'ACCESS_TOKEN_EXPIRE_MINUTES' '60'
    Set-Default $settings 'USER_ACCESS_TOKEN_EXPIRE_MINUTES' '10080'
    Set-Default $settings 'ADMIN_USERNAME' 'admin'
    Set-Default $settings 'ADMIN_PASSWORD' 'replace-with-generated-admin-password'
    Set-Default $settings 'DEFAULT_USAGE_LIMIT' '1'
    Set-Default $settings 'SEGMENT_SKIP_THRESHOLD' '15'

    $generatedAdmin = $false
    if (Test-Placeholder $settings['POSTGRES_PASSWORD']) { $settings['POSTGRES_PASSWORD'] = 'pg_' + (New-RandomHex 16) }
    if (Test-Placeholder $settings['SECRET_KEY']) { $settings['SECRET_KEY'] = New-UrlSafeBase64 32 }
    if (Test-Placeholder $settings['ENCRYPTION_KEY']) { $settings['ENCRYPTION_KEY'] = New-UrlSafeBase64 32 }
    if (Test-Placeholder $settings['ADMIN_PASSWORD']) {
        $settings['ADMIN_PASSWORD'] = 'admin_' + (New-RandomHex 8)
        $generatedAdmin = $true
    }

    Write-DotEnv $settings $EnvPath

    if ($generatedAdmin) {
        $adminInfo = Join-Path $LogDir 'first-run-admin.txt'
        $content = @(
            'GankAIGC 首次运行后台账号',
            '========================',
            '后台地址: http://localhost:' + $settings['SERVER_PORT'] + '/admin',
            '用户名: ' + $settings['ADMIN_USERNAME'],
            '密码: ' + $settings['ADMIN_PASSWORD'],
            '',
            '如需修改密码，请编辑程序目录下的 .env：',
            'ADMIN_PASSWORD=你的新密码'
        ) -join [Environment]::NewLine
        $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
        [System.IO.File]::WriteAllText($adminInfo, $content + [Environment]::NewLine, $utf8NoBom)
        Write-Warn "首次生成后台密码，已保存到：$adminInfo"
        Write-Host "后台用户名：$($settings['ADMIN_USERNAME'])" -ForegroundColor Yellow
        Write-Host "后台密码：$($settings['ADMIN_PASSWORD'])" -ForegroundColor Yellow
    }

    return $settings
}

function Assert-File([string]$Path, [string]$Message) {
    if (-not (Test-Path -LiteralPath $Path)) {
        throw $Message
    }
}

function Test-TcpPort([string]$HostName, [int]$Port) {
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $async = $client.BeginConnect($HostName, $Port, $null, $null)
        if (-not $async.AsyncWaitHandle.WaitOne(1000, $false)) { return $false }
        $client.EndConnect($async)
        return $true
    } catch {
        return $false
    } finally {
        $client.Close()
    }
}

function Invoke-WithPgPassword([string]$Password, [scriptblock]$Script) {
    $oldPassword = $env:PGPASSWORD
    try {
        $env:PGPASSWORD = $Password
        & $Script
    } finally {
        if ($null -eq $oldPassword) {
            Remove-Item Env:\PGPASSWORD -ErrorAction SilentlyContinue
        } else {
            $env:PGPASSWORD = $oldPassword
        }
    }
}

function Test-PostgresLogin([string]$Psql, [string]$HostName, [string]$Port, [string]$User, [string]$Password) {
    Invoke-WithPgPassword $Password {
        & $Psql -h $HostName -p $Port -U $User -d postgres -tAc 'SELECT 1' > $null 2> $null
    }
    return ($LASTEXITCODE -eq 0)
}

function Initialize-Postgres($Settings) {
    $initDb = Join-Path $PgBin 'initdb.exe'
    Assert-File $initDb '缺少 postgres\bin\initdb.exe，请确认一键包内已包含便携 PostgreSQL。'

    if (Test-Path -LiteralPath (Join-Path $DataDir 'PG_VERSION')) {
        return
    }

    if ((Test-Path -LiteralPath $DataDir) -and ((Get-ChildItem -LiteralPath $DataDir -Force | Select-Object -First 1) -ne $null)) {
        throw "数据目录已存在但不是 PostgreSQL 数据目录：$DataDir。请先备份后再处理。"
    }

    New-Item -ItemType Directory -Force -Path $DataDir | Out-Null
    $passwordFile = Join-Path $env:TEMP ('gankaigc-pgpass-' + [Guid]::NewGuid().ToString('N') + '.txt')
    try {
        [System.IO.File]::WriteAllText($passwordFile, [string]$Settings['POSTGRES_PASSWORD'], [System.Text.Encoding]::ASCII)
        Write-Step '首次运行：初始化内置 PostgreSQL 数据目录...'
        & $initDb -D $DataDir -U $Settings['POSTGRES_USER'] -A scram-sha-256 --pwfile $passwordFile -E UTF8
        if ($LASTEXITCODE -ne 0) { throw 'initdb 初始化失败，请查看上方输出。' }
        Write-Ok 'PostgreSQL 初始化完成'
    } finally {
        Remove-Item -LiteralPath $passwordFile -Force -ErrorAction SilentlyContinue
    }
}

function Start-Postgres($Settings) {
    $pgCtl = Join-Path $PgBin 'pg_ctl.exe'
    $psql = Join-Path $PgBin 'psql.exe'
    $createdb = Join-Path $PgBin 'createdb.exe'
    Assert-File $pgCtl '缺少 postgres\bin\pg_ctl.exe，请确认一键包内已包含便携 PostgreSQL。'
    Assert-File $psql '缺少 postgres\bin\psql.exe，请确认一键包内已包含便携 PostgreSQL。'
    Assert-File $createdb '缺少 postgres\bin\createdb.exe，请确认一键包内已包含便携 PostgreSQL。'

    $hostName = [string]$Settings['POSTGRES_HOST']
    $port = [string]$Settings['POSTGRES_PORT']
    $user = [string]$Settings['POSTGRES_USER']
    $password = [string]$Settings['POSTGRES_PASSWORD']
    $db = [string]$Settings['POSTGRES_DB']

    Initialize-Postgres $Settings

    if (Test-PostgresLogin $psql $hostName $port $user $password) {
        Write-Ok "PostgreSQL 已在 $hostName`:$port 运行"
    } else {
        if (Test-TcpPort $hostName ([int]$port)) {
            throw "端口 $hostName`:$port 已被占用，且不是当前一键包数据库。请修改 .env 里的 POSTGRES_PORT 后重试。"
        }

        $postgresLog = Join-Path $LogDir 'postgres.log'
        Write-Step "启动内置 PostgreSQL：$hostName`:$port"
        & $pgCtl -D $DataDir -l $postgresLog -o "-p $port -h $hostName" start
        if ($LASTEXITCODE -ne 0) { throw "PostgreSQL 启动失败，请查看：$postgresLog" }

        $ready = $false
        for ($i = 0; $i -lt 30; $i++) {
            Start-Sleep -Seconds 1
            if (Test-PostgresLogin $psql $hostName $port $user $password) {
                $ready = $true
                break
            }
        }
        if (-not $ready) { throw "PostgreSQL 启动超时，请查看：$postgresLog" }
        Write-Ok 'PostgreSQL 启动完成'
    }

    $exists = ''
    Invoke-WithPgPassword $password {
        $script:dbExistsOutput = & $psql -h $hostName -p $port -U $user -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname = '$db';" 2> $null
    }
    $exists = (($script:dbExistsOutput | Out-String).Trim())
    if ($LASTEXITCODE -ne 0) { throw '检查数据库是否存在失败。' }

    if ($exists -ne '1') {
        Write-Step "创建数据库：$db"
        Invoke-WithPgPassword $password {
            & $createdb -h $hostName -p $port -U $user $db
        }
        if ($LASTEXITCODE -ne 0) { throw "创建数据库 $db 失败。" }
        Write-Ok "数据库 $db 已创建"
    }
}

function Test-GankAIGCRunning([string]$AppExe) {
    $targets = Get-CimInstance Win32_Process -Filter "name = 'GankAIGC.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.ExecutablePath -and [string]::Equals($_.ExecutablePath, $AppExe, [System.StringComparison]::OrdinalIgnoreCase) }
    return ($null -ne ($targets | Select-Object -First 1))
}

function Start-GankAIGC($Settings) {
    $appExe = Join-Path $BundleRoot 'GankAIGC.exe'
    Assert-File $appExe '缺少 GankAIGC.exe，请确认一键包完整。'

    $url = 'http://localhost:' + $Settings['SERVER_PORT']
    if (Test-GankAIGCRunning $appExe) {
        Write-Warn 'GankAIGC.exe 已经在运行，本次不重复启动。'
        Write-Host "正在打开浏览器：$url" -ForegroundColor Yellow
        Start-Process $url
        exit 0
    }

    Write-Step '启动 GankAIGC...'
    Write-Host "浏览器会自动打开；如果没有打开，请访问 $url" -ForegroundColor Yellow
    Write-Host '停止应用请在此窗口按 Ctrl+C；完全停止数据库请再运行 stop.bat。' -ForegroundColor Yellow
    Write-Host ''

    Set-Location $BundleRoot
    & $appExe
    exit $LASTEXITCODE
}

try {
    Write-Host ''
    Write-Host '==========================================' -ForegroundColor Cyan
    Write-Host ' GankAIGC Windows 一键启动' -ForegroundColor Cyan
    Write-Host '==========================================' -ForegroundColor Cyan

    $settings = Ensure-EnvFile
    Start-Postgres $settings
    Start-GankAIGC $settings
} catch {
    Write-Host ''
    Write-Host '❌ 启动失败：' -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host ''
    Write-Host '可查看 logs\postgres.log，或把本窗口错误截图发给维护者。' -ForegroundColor Yellow
    exit 1
}



