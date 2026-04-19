# =========================
# Config
# =========================

$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path

$SERVICES = @(
    "AGENT/agent_module",
    "MEMORY/memory_module",
    "FILE/file_service",
    "TOOLS/tools_module",
    "LOGIN_REGISTER/login_register_module",
    "TASK/task_flow_module"
)

$LOG_DIR = Join-Path $ROOT "logs"
$PID_FILE = Join-Path $ROOT ".apix_pids"

if (!(Test-Path $LOG_DIR)) {
    New-Item -ItemType Directory -Path $LOG_DIR | Out-Null
}

# =========================
# Utils
# =========================

function Start-Service($path) {
    $name = $path -replace "/", "_"
    $logFile = Join-Path $LOG_DIR "$name.log"

    Write-Host "[START] $path"

    $proc = Start-Process -FilePath "uv" -ArgumentList "run main.py" -WorkingDirectory (Join-Path $ROOT $path) -RedirectStandardOutput $logFile -RedirectStandardError $logFile -PassThru

    return "$($proc.Id),$name"
}

function Stop-ProcessByPid($pid) {
    try {
        Stop-Process -Id $pid -Force -ErrorAction Stop
    } catch {
        Write-Host "[WARN] Failed to stop $pid"
    }
}

# =========================
# Commands
# =========================

function Up() {
    Write-Host "==== Starting APIX Services ===="

    $records = @()

    foreach ($svc in $SERVICES) {
        $record = Start-Service $svc
        $records += $record
    }

    $records | Out-File -FilePath $PID_FILE -Encoding utf8

    Write-Host "`nAll services started ✅"
}

function Down() {
    if (!(Test-Path $PID_FILE)) {
        Write-Host "No running services"
        return
    }

    Write-Host "==== Stopping APIX Services ===="

    Get-Content $PID_FILE | ForEach-Object {
        $parts = $_ -split ","
        $pid = [int]$parts[0]
        $name = $parts[1]

        Write-Host "[STOP] $name ($pid)"
        Stop-ProcessByPid $pid
    }

    Remove-Item $PID_FILE -ErrorAction SilentlyContinue

    Write-Host "All services stopped ✅"
}

function Logs() {
    Write-Host "Logs directory: $LOG_DIR"
}

# =========================
# Entry
# =========================

param(
    [string]$cmd
)

switch ($cmd) {
    "up" { Up }
    "down" { Down }
    "logs" { Logs }
    default { Write-Host "Usage: ./apix.ps1 [up|down|logs]" }
}