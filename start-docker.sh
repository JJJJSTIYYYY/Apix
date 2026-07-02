#!/usr/bin/env bash
# Start all APIX backend services in Docker Compose.
# The Electron frontend should still run on the host.

set -e

ROOT=$(pwd)

# Stop legacy infrastructure containers started by setup.sh so Compose can own them.
for name in apix-mysql redis-memo; do
    if docker ps -a --format "{{.Names}}" | grep -q "^${name}$"; then
        echo "[INFO] Stopping legacy container: $name"
        docker stop "$name" >/dev/null 2>&1 || true
        docker rm "$name" >/dev/null 2>&1 || true
    fi
done

# Resolve host-side paths so AGENT can spawn sandbox containers correctly.
HOST_BASE_DIR="$ROOT/AGENT/apix_running_time"
mkdir -p "$HOST_BASE_DIR"
HOST_BASE_DIR=$(cd "$HOST_BASE_DIR" && pwd)
export HOST_BASE_DIR

echo "HOST_BASE_DIR set to: $HOST_BASE_DIR"
echo "Starting APIX services with Docker Compose..."

docker compose -f "$ROOT/docker-compose.yml" up -d --build

echo "Docker Compose started."
echo "Use 'docker compose logs -f' to view logs."
