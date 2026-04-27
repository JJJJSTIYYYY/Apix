
param(
    [string]$cmd
)

$ROOT = Get-Location

$SERVICES = @(
    "AGENT/agent_module",
    "MEMORY/memory_module",
    "FILE/file_service",
    "TOOLS/tools_module",
    "TASK/task_flow_module"
)

$LOG_DIR = Join-Path $ROOT "logs"
$PID_FILE = Join-Path $ROOT ".apix_pids"

# =========================
# Utils
# =========================

function Ensure-Dir($path) {
    if (!(Test-Path $path)) {
        New-Item -ItemType Directory -Path $path | Out-Null
    }
}

function Get-UV-Path() {
    $cmd = Get-Command uv -ErrorAction SilentlyContinue
    if ($cmd) {
        return $cmd.Source
    } else {
        Write-Host "[ERROR] uv not found in PATH"
        exit 1
    }
}

function Start-Service($path) {
    $name = $path -replace "/", "_"
    $logFile = Join-Path $LOG_DIR "$name.log"

    Write-Host ("[START] {0}" -f $path)

    $uvPath = Get-UV-Path

    $proc = Start-Process -FilePath $uvPath -ArgumentList "run main.py" -WorkingDirectory (Join-Path $ROOT $path) -RedirectStandardError $logFile -PassThru

    if (!$proc) {
        Write-Host ("[ERROR] Failed to start {0}" -f $name)
        exit 1
    }

    return ("{0},{1}" -f $proc.Id, $name)
}

function Stop-ProcessSafe($pid) {
    try {
        Stop-Process -Id $pid -Force -ErrorAction Stop
    } catch {
        Write-Host ("[WARN] Failed to stop {0}" -f $pid)
    }
}

# =========================
# Commands
# =========================

function Up() {
    Write-Host "==== Starting APIX Services ===="

    Ensure-Dir $LOG_DIR

    $records = @()

    foreach ($svc in $SERVICES) {
        $record = Start-Service $svc
        $records += $record
    }

    $records | Out-File -FilePath $PID_FILE -Encoding utf8

    Write-Host ""
    Write-Host "All services started ✅"
}

function Down() {
    if (!(Test-Path $PID_FILE)) {
        Write-Host "No running services"
        return
    }

    Write-Host "==== Stopping APIX Services ===="

    Get-Content $PID_FILE | ForEach-Object {
        if (![string]::IsNullOrWhiteSpace($_)) {
            $parts = $_ -split ","

            if ($parts.Length -ge 2) {
                $pid = [int]$parts[0]
                $name = $parts[1]

                Write-Host ("``[STOP``] {0} ({1})" -f $name, $pid)
                Stop-ProcessSafe $pid
            }
        }
    }

    Remove-Item $PID_FILE -ErrorAction SilentlyContinue

    Write-Host "All services stopped ✅"
}

function Logs() {
    Write-Host ("Logs directory: {0}" -f $LOG_DIR)
}

# =========================
# Entry
# =========================

switch ($cmd) {
    "up" { Up }
    "down" { Down }
    "logs" { Logs }
    default { Write-Host "Usage: ./apix.ps1 [up|down|logs]" }
}