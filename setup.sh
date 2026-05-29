#!/usr/bin/env bash

set -e  # exit on error

echo "==== APIX One-click Setup (Linux/macOS) ===="

ROOT=$(pwd)

# =========================
# Utils
# =========================

Ensure_Dir() {
    local path="$1"
    if [ ! -d "$path" ]; then
        mkdir -p "$path"
    fi
}

Docker_Build_Safe() {
    local imageName="$1"
    local contextPath="$2"
    local force="${3:-false}"

    # Check if image exists
    if docker images --format "{{.Repository}}:{{.Tag}}" | grep -q "^${imageName}$" && [ "$force" != "true" ]; then
        echo "[SKIP] Image $imageName already exists"
    else
        echo "[BUILD] Building $imageName ..."
        docker build -t "$imageName" "$contextPath"
    fi
}

Docker_Run_Safe() {
    local name="$1"
    shift
    local cmd="$@"

    if docker ps -a --format "{{.Names}}" | grep -q "^${name}$"; then
        echo "[SKIP] Container $name already exists"
        return
    fi

    eval "$cmd"
}

# =========================
# Build sandbox
# =========================
echo "[1/7] Building agent sandbox..."

echo "[INFO] Pre-pulling base image ubuntu:22.04..."
docker pull ubuntu:22.04

pushd "$ROOT/README/script/AgentSandbox" >/dev/null
Docker_Build_Safe "agent-sandbox:latest" "."
popd >/dev/null

# =========================
# Redis
# =========================
echo "[2/7] Starting Redis..."

Ensure_Dir "$ROOT/MEMORY/memory_module/data/redis/data-redis-memo"

docker pull redis:7

Docker_Run_Safe "redis-memo" \
docker run -d --name redis-memo -p 6379:6379 \
-v "$ROOT/MEMORY/memory_module/data/redis/data-redis-memo:/data" \
--restart unless-stopped redis:7

# =========================
# MySQL
# =========================
echo "[3/7] Starting MySQL..."

Ensure_Dir "$ROOT/MEMORY/memory_module/data/mysql_data"

docker pull mysql:8.0

Docker_Run_Safe "apix-mysql" \
docker run -d --name apix-mysql -p 3307:3306 \
-v "$ROOT/MEMORY/memory_module/data/mysql_data:/var/lib/mysql" \
-e MYSQL_ROOT_PASSWORD=your_root_password \
-e MYSQL_DATABASE=apix_database \
-e MYSQL_USER=apix \
-e MYSQL_PASSWORD=apixapix \
--restart unless-stopped mysql:8.0

echo "Waiting for MySQL..."

for i in {1..20}; do
    if docker exec apix-mysql mysqladmin ping -h "127.0.0.1" -uroot -pyour_root_password >/dev/null 2>&1; then
        echo "MySQL is ready"
        break
    fi
    sleep 2
done

echo "[4/7] Initializing database..."

cat "$ROOT/README/script/init_mysql_backup.sql" | \
docker exec -i apix-mysql mysql -u root -pyour_root_password apix_database

# =========================
# Backend
# =========================
echo "[5/7] Init backend..."

pip install -U uv

modules=(
  "AGENT/agent_module"
  "MEMORY/memory_module"
  "FILE/file_service"
  "TASK/task_flow_module"
)

for m in "${modules[@]}"; do
    pushd "$ROOT/$m" >/dev/null
    echo "Installing deps: $m"
    uv sync
    popd >/dev/null
done

# =========================
# Frontend
# =========================
echo "[6/7] Init frontend..."

pushd "$ROOT/CLIENT/apix-app" >/dev/null

# Install Volta if not exists
if ! command -v volta >/dev/null 2>&1; then
    echo "[INFO] Installing Volta..."
    curl https://get.volta.sh | bash
    export VOLTA_HOME="$HOME/.volta"
    export PATH="$VOLTA_HOME/bin:$PATH"
fi

volta install node@22.19.0

npm install

popd >/dev/null

# =========================
# Done
# =========================
echo "[7/7] DONE"