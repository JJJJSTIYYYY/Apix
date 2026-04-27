#!/usr/bin/env bash

set -e

# =========================
# Config
# =========================

ROOT="$(cd "$(dirname "$0")" && pwd)"

SERVICES=(
  "AGENT/agent_module"
  "MEMORY/memory_module"
  "FILE/file_service"
  "TOOLS/tools_module"
  "TASK/task_flow_module"
)

LOG_DIR="$ROOT/logs"
PID_FILE="$ROOT/.apix_pids"

mkdir -p "$LOG_DIR"

# =========================
# Utils
# =========================

start_service() {
    local path="$1"
    local name="${path//\//_}"
    local log_file="$LOG_DIR/$name.log"

    echo "[START] $path"

    (
        cd "$ROOT/$path"
        uv run main.py > "$log_file" 2>&1 &
        echo "$!,$name"
    )
}

stop_process() {
    local pid="$1"

    if kill -0 "$pid" 2>/dev/null; then
        kill "$pid"
    else
        echo "[WARN] Failed to stop $pid"
    fi
}

# =========================
# Commands
# =========================

up() {
    echo "==== Starting APIX Services ===="

    > "$PID_FILE"

    for svc in "${SERVICES[@]}"; do
        record=$(start_service "$svc")
        echo "$record" >> "$PID_FILE"
    done

    echo ""
    echo "All services started ✅"
}

down() {
    if [ ! -f "$PID_FILE" ]; then
        echo "No running services"
        exit 0
    fi

    echo "==== Stopping APIX Services ===="

    while IFS=',' read -r pid name; do
        echo "[STOP] $name ($pid)"
        stop_process "$pid"
    done < "$PID_FILE"

    rm -f "$PID_FILE"

    echo "All services stopped ✅"
}

logs() {
    echo "Logs directory: $LOG_DIR"
}

# =========================
# Entry
# =========================

case "$1" in
    up) up ;;
    down) down ;;
    logs) logs ;;
    *) echo "Usage: ./apix.sh [up|down|logs]" ;;
esac