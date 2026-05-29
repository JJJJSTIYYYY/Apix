
Write-Host "==== APIX One-click Setup (Windows) ===="

$ROOT = Get-Location

# =========================
# Utils
# =========================

function Ensure-Dir($path) {
    if (!(Test-Path $path)) {
        New-Item -ItemType Directory -Path $path | Out-Null
    }
}

function Docker-Build-Safe($imageName, $contextPath, $force=$false) {
    # Check if image exists locally
    $exists = docker images --format "{{.Repository}}:{{.Tag}}" | Select-String "^$imageName$"

    if ($exists -and -not $force) {
        Write-Host "[SKIP] Image $imageName already exists"
    } else {
        Write-Host "[BUILD] Building $imageName ..."

        docker build -t $imageName $contextPath

        if ($LASTEXITCODE -ne 0) {
            Write-Host "[ERROR] Build failed: $imageName"
            exit 1
        }
    }
}

function Docker-Run-Safe($name, $cmd) {
    $exists = docker ps -a --format "{{.Names}}" | Select-String "^$name$"
    if ($exists) {
        Write-Host "[SKIP] Container $name already exists"
        return
    }

    Invoke-Expression $cmd

    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Failed to start container: $name"
        exit 1
    }
}

# =========================
# Build sandbox
# =========================
Write-Host "[1/7] Building agent sandbox..."

# Pre-pull base image (CRITICAL to avoid docker.io auth issue)
Write-Host "[INFO] Pre-pulling base image ubuntu:22.04..."
docker pull ubuntu:22.04

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Failed to pull ubuntu:22.04"
    exit 1
}

Push-Location "$ROOT\README\script\AgentSandbox"
Docker-Build-Safe "agent-sandbox:latest" "."
Pop-Location

# =========================
# Redis
# =========================
Write-Host "[2/7] Starting Redis..."

Ensure-Dir "$ROOT\MEMORY\memory_module\data\redis\data-redis-memo"

docker pull redis:7

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Failed to pull redis:7"
    exit 1
}

Docker-Run-Safe "redis-memo" "docker run -d --name redis-memo -p 6379:6379 -v $ROOT/MEMORY/memory_module/data/redis/data-redis-memo:/data --restart unless-stopped redis:7"

# =========================
# MySQL
# =========================
Write-Host "[3/7] Starting MySQL..."

Ensure-Dir "$ROOT\MEMORY\memory_module\data\mysql_data"

docker pull mysql:8.0

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Failed to pull mysql:8.0"
    exit 1
}

Docker-Run-Safe "apix-mysql" "docker run -d --name apix-mysql -p 3307:3306 -v $ROOT/MEMORY/memory_module/data/mysql_data:/var/lib/mysql -e MYSQL_ROOT_PASSWORD=your_root_password -e MYSQL_DATABASE=apix_database -e MYSQL_USER=apix -e MYSQL_PASSWORD=apixapix --restart unless-stopped mysql:8.0"

# Waiting MySQL ready
Write-Host "Waiting for MySQL..."
for ($i=0; $i -lt 20; $i++) {
    $result = docker exec apix-mysql mysqladmin ping -h "127.0.0.1" -uroot -pyour_root_password 2>$null
    if ($result -like "*mysqld is alive*") {
        Write-Host "MySQL is ready"
        break
    }
    Start-Sleep -Seconds 2
}

Write-Host "[4/7] Initializing database..."

Get-Content "$ROOT\README\script\init_mysql_backup.sql" -Raw | docker exec -i apix-mysql `
  mysql -u root -pyour_root_password apix_database

# =========================
# Backend
# =========================
Write-Host "[5/7] Init backend..."

pip install -U uv

$modules = @(
  "AGENT/agent_module",
  "MEMORY/memory_module",
  "FILE/file_service",
  "TASK/task_flow_module"
)

foreach ($m in $modules) {
    Push-Location "$ROOT\$m"
    Write-Host "Installing deps: $m"
    uv sync
    Pop-Location
}

# =========================
# Frontend
# =========================
Write-Host "[6/7] Init frontend..."

Push-Location "$ROOT\CLIENT\apix-app"

# Install Volta
if (!(Get-Command volta -ErrorAction SilentlyContinue)) {
    winget install Volta.Volta -e --id Volta.Volta
}

volta install node@22.19.0

npm install

Pop-Location

# =========================
# Done
# =========================
Write-Host "[7/7] DONE"