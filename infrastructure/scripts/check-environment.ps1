#  Environment check - Sprint 0
#  Verifies developer tooling on Windows 10 without changing any system state.
#
#  ASCII-only on purpose: Windows PowerShell 5.1 reads .ps1 files as ANSI,
#  so non-ASCII characters here would break the parser.
#
#  Usage (from the project root):
#      powershell -ExecutionPolicy Bypass -File infrastructure/scripts/check-environment.ps1

$ErrorActionPreference = 'Stop'

function Get-ToolStatus {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [string]$VersionArg = '--version'
    )

    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if ($null -eq $command) {
        return [pscustomobject]@{ Tool = $Name; Status = 'MISSING'; Version = ''; Path = '' }
    }

    $version = ''
    try {
        $version = (& $command.Source $VersionArg 2>&1 | Select-Object -First 1)
        if ($null -ne $version) { $version = $version.ToString().Trim() }
    }
    catch {
        $version = '(version check failed)'
    }

    return [pscustomobject]@{
        Tool    = $Name
        Status  = 'OK'
        Version = $version
        Path    = $command.Source
    }
}

Write-Host ''
Write-Host '=== Education Platform - environment check ===' -ForegroundColor Cyan
Write-Host ''

$results = @(
    Get-ToolStatus -Name 'git'
    Get-ToolStatus -Name 'node'
    Get-ToolStatus -Name 'npm.cmd'
    Get-ToolStatus -Name 'py'
    Get-ToolStatus -Name 'python'
    Get-ToolStatus -Name 'docker'
)

$results | Format-Table -AutoSize

# --- Docker Compose ---------------------------------------------------------
$compose = Get-Command 'docker-compose' -ErrorAction SilentlyContinue
if ($null -ne $compose) {
    Write-Host "docker-compose standalone: $($compose.Source)" -ForegroundColor Green
}
else {
    Write-Host 'docker-compose standalone: not installed (Docker Compose v2 plugin "docker compose" is expected instead)' -ForegroundColor Yellow
}

# --- WSL --------------------------------------------------------------------
$wsl = Get-Command 'wsl' -ErrorAction SilentlyContinue
if ($null -eq $wsl) {
    Write-Host 'WSL: not available (Docker Desktop needs WSL2 on Windows 10)' -ForegroundColor Yellow
}
else {
    # `wsl -l` writes UTF-16; PowerShell 5.1 decodes native output with the OEM
    # code page, so switch the output encoding for the duration of the call.
    # When no distribution exists, `wsl` prints its help text instead of a list.
    $previousEncoding = [Console]::OutputEncoding
    try {
        [Console]::OutputEncoding = [System.Text.Encoding]::Unicode
        $distros = ((& wsl --list --quiet 2>&1) -join ' ')
    }
    finally {
        [Console]::OutputEncoding = $previousEncoding
    }

    if ([string]::IsNullOrWhiteSpace($distros) -or $distros -match 'wsl\.exe\s*\[' ) {
        Write-Host 'WSL: command present, but no Linux distribution is installed' -ForegroundColor Yellow
    }
    else {
        Write-Host "WSL: installed distributions -> $($distros.Trim())" -ForegroundColor Green
    }
}

# --- Docker engine ----------------------------------------------------------
Write-Host ''
if ($null -eq (Get-Command 'docker' -ErrorAction SilentlyContinue)) {
    Write-Host 'DOCKER: NOT INSTALLED - PostgreSQL cannot be started yet.' -ForegroundColor Red
    Write-Host 'Docker-dependent checks are NOT verified.' -ForegroundColor Yellow
    Write-Host 'See README.md -> Docker Desktop / WSL2 installation section.'
    exit 1
}

try {
    $serverVersion = (& docker info --format '{{.ServerVersion}}' 2>&1) -join ''
    if ($serverVersion -match 'error') { throw $serverVersion }
    Write-Host "DOCKER: engine reachable (server $serverVersion)" -ForegroundColor Green
    exit 0
}
catch {
    Write-Host 'DOCKER: installed, but the engine is not running. Start Docker Desktop.' -ForegroundColor Yellow
    exit 1
}
