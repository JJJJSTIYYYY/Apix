# Start all APIX backend services in Docker Compose.
# The Electron frontend should still run on the host.

$ROOT = Get-Location

# Stop legacy infrastructure containers started by setup.ps1 so Compose can own them.
$legacy = @("apix-mysql", "redis-memo")
foreach ($name in $legacy) {
    $exists = docker ps -a --format "{{.Names}}" | Select-String "^$name$"
    if ($exists) {
        Write-Host "[INFO] Stopping legacy container: $name"
        docker stop $name | Out-Null
        docker rm $name | Out-Null
    }
}

# Resolve host-side paths so AGENT can spawn sandbox containers correctly.
$hostBaseDir = (Resolve-Path "$ROOT\AGENT\apix_running_time" -ErrorAction SilentlyContinue)
if (-not $hostBaseDir) {
    $hostBaseDir = "$ROOT\AGENT\apix_running_time"
    New-Item -ItemType Directory -Path $hostBaseDir -Force | Out-Null
    $hostBaseDir = (Resolve-Path $hostBaseDir).Path
}

$env:HOST_BASE_DIR = $hostBaseDir

Write-Host "HOST_BASE_DIR set to: $hostBaseDir"
Write-Host "Starting APIX services with Docker Compose..."

docker compose -f "$ROOT\docker-compose.yml" up -d --build

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Docker Compose failed to start."
    exit 1
}

Write-Host "Docker Compose started."
Write-Host "Use 'docker compose logs -f' to view logs."
