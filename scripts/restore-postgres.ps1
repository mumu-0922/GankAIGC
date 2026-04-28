[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [string]$DumpFile,
    [string]$DatabaseUrl = $env:DATABASE_URL,
    [switch]$Help
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Show-Help {
    Write-Host "Usage: PowerShell -File scripts/restore-postgres.ps1 <dump-file>"
    Write-Host ""
    Write-Host "Requires DATABASE_URL, for example:"
    Write-Host '  $env:DATABASE_URL="postgresql://ai_polish:password@127.0.0.1:5432/ai_polish"'
    Write-Host "Restore uses: pg_restore --clean --if-exists"
}

function Convert-DatabaseUrl {
    param([string]$Url)

    $uri = [Uri]$Url
    if ($uri.Scheme -notin @("postgresql", "postgresql+psycopg")) {
        throw "DATABASE_URL must start with postgresql:// or postgresql+psycopg://"
    }

    $userInfo = $uri.UserInfo.Split(":", 2)
    if ($userInfo.Count -lt 2) {
        throw "DATABASE_URL must include username and password"
    }

    return [pscustomobject]@{
        Host = $uri.Host
        Port = if ($uri.Port -gt 0) { $uri.Port } else { 5432 }
        Database = $uri.AbsolutePath.TrimStart("/")
        Username = [Uri]::UnescapeDataString($userInfo[0])
        Password = [Uri]::UnescapeDataString($userInfo[1])
    }
}

if ($Help) {
    Show-Help
    exit 0
}

if (-not $DumpFile) {
    Show-Help
    throw "Dump file path is required"
}

if (-not (Test-Path -LiteralPath $DumpFile)) {
    throw "Dump file not found: $DumpFile"
}

if (-not $DatabaseUrl) {
    Show-Help
    throw "DATABASE_URL is required"
}

$connection = Convert-DatabaseUrl -Url $DatabaseUrl
$oldPassword = $env:PGPASSWORD

try {
    $env:PGPASSWORD = $connection.Password
    & pg_restore `
        --clean `
        --if-exists `
        --no-owner `
        --host="$($connection.Host)" `
        --port="$($connection.Port)" `
        --username="$($connection.Username)" `
        --dbname="$($connection.Database)" `
        "$DumpFile"

    if ($LASTEXITCODE -ne 0) {
        throw "pg_restore failed with exit code $LASTEXITCODE"
    }
    Write-Host "Restore completed into database: $($connection.Database)"
} finally {
    $env:PGPASSWORD = $oldPassword
}
