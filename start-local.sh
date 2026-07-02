#!/usr/bin/env bash
# Start all APIX backend services locally (non-Docker mode).
# Run this after setup.sh has installed dependencies and started Redis/MySQL.

set -e

ROOT=$(pwd)

declare -a services=(
    "TASK:TASK/task_flow_module:5090"
    "AGENT:AGENT/agent_module:5091"
    "MEMORY:MEMORY/memory_module:5093"
    "FILE:FILE/file_service:5094"
)

echo "Starting APIX backend services locally..."

for svc in "${services[@]}"; do
    IFS=':' read -r name path port <<< "$svc"
    echo "[$name] Starting uvicorn on port $port..."
    (
        cd "$ROOT/$path"
        nohup uv run main.py > "$ROOT/$name.log" 2>&1 &
    )
done

echo "All backend services started."
echo "AGENT : http://127.0.0.1:5091"
echo "TASK  : http://127.0.0.1:5090"
echo "MEMORY: http://127.0.0.1:5093"
echo "FILE  : http://127.0.0.1:5094"
