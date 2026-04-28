[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string]$DatabaseUrl = $env:DATABASE_URL,
    [string]$OutputDir = "",
    [switch]$Help
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Show-Help {
    Write-Host "Usage: PowerShell -File scripts/backup-postgres.ps1 [-OutputDir backups]"
    Write-Host ""
    Write-Host "Requires DATABASE_URL, for example:"
    Write-Host '  $env:DATABASE_URL="postgresql://ai_polish:password@127.0.0.1:5432/ai_polish"'
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

if (-not $OutputDir) {
    $OutputDir = Join-Path $PSScriptRoot "..\backups"
}

if (-not $DatabaseUrl) {
    if ($WhatIfPreference) {
        $DatabaseUrl = "postgresql://ai_polish:placeholder@127.0.0.1:5432/ai_polish"
    } else {
        Show-Help
        throw "DATABASE_URL is required"
    }
}

$connection = Convert-DatabaseUrl -Url $DatabaseUrl
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$dumpFileName = "gankaigc_$($connection.Database)_$timestamp.dump"
$dumpPath = Join-Path $OutputDir $dumpFileName
$oldPassword = $env:PGPASSWORD

try {
    if ($PSCmdlet.ShouldProcess($connection.Database, "Back up PostgreSQL database to $dumpPath")) {
        New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
        $env:PGPASSWORD = $connection.Password
        & pg_dump `
            --format=custom `
            --file="$dumpPath" `
            --host="$($connection.Host)" `
            --port="$($connection.Port)" `
            --username="$($connection.Username)" `
            --dbname="$($connection.Database)"

        if ($LASTEXITCODE -ne 0) {
            throw "pg_dump failed with exit code $LASTEXITCODE"
        }
        Write-Host "Backup created: $dumpPath"
    }
} finally {
    $env:PGPASSWORD = $oldPassword
}
