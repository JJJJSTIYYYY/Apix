#!/usr/bin/env bash

set -e  # Exit on error

echo "==== APIX One-click Setup (Mac/Linux) ===="

# ---------------------------
# Clone project
# ---------------------------
echo "[1/8] Init..."

# ---------------------------
# Build Agent Sandbox
# ---------------------------
echo "[2/8] Building agent sandbox image..."
cd ./README/script/AgentSandbox/
docker build -t agent-sandbox .
cd ../../../

# ---------------------------
# Redis
# ---------------------------
echo "[3/8] Starting Redis containers..."

mkdir -p ./MEMORY/memory_module/data/redis/data-redis-memo
mkdir -p ./MEMORY/memory_module/data/redis/data-redis-task
mkdir -p ./AGENT/agent_module/data/redis/data-redis-longterm-memory

docker pull redis:7

docker run -d --name redis-memo \
  -p 6379:6379 \
  -v $(pwd)/MEMORY/memory_module/data/redis/data-redis-memo:/data \
  --restart unless-stopped redis:7 || true

docker run -d --name redis-task \
  -p 6380:6379 \
  -v $(pwd)/MEMORY/memory_module/data/redis/data-redis-task:/data \
  --restart unless-stopped redis:7 || true

docker run -d --name redis-longterm-memory \
  -p 6378:6379 \
  -v $(pwd)/AGENT/agent_module/data/redis/data-redis-longterm-memory:/data \
  --restart unless-stopped redis:7 || true

# ---------------------------
# MySQL
# ---------------------------
echo "[4/8] Starting MySQL..."

mkdir -p ./MEMORY/memory_module/data/mysql_data

docker pull mysql:8.0

docker run -d --name apix-mysql \
  -p 3307:3306 \
  -v $(pwd)/MEMORY/memory_module/data/mysql_data:/var/lib/mysql \
  -e MYSQL_ROOT_PASSWORD=your_root_password \
  -e MYSQL_DATABASE=apix_database \
  -e MYSQL_USER=apix \
  -e MYSQL_PASSWORD=apixapix \
  --restart unless-stopped mysql:8.0 || true

echo "Waiting MySQL to be ready..."
sleep 10

echo "[5/8] Initializing database..."
docker exec -i apix-mysql \
  mysql -u root -pyour_root_password apix_database \
  < ./README/script/init_mysql.sql

# ---------------------------
# Python backend
# ---------------------------
echo "[6/8] Init backend..."

pip3 install -U uv

modules=(
  "AGENT/agent_module"
  "MEMORY/memory_module"
  "FILE/file_service"
  "TOOLS/tools_module"
  "LOGIN_REGISTER/login_register_module"
  "TASK/task_flow_module"
)

for module in "${modules[@]}"; do
  echo "Starting $module ..."
  cd $module
  uv sync
  cd - > /dev/null
done

# ---------------------------
# Frontend
# ---------------------------
echo "[7/8] Init frontend..."

cd ./CLIENT/apix-app

if ! command -v volta &> /dev/null; then
  echo "Installing Volta..."
  curl https://get.volta.sh | bash
  export VOLTA_HOME="$HOME/.volta"
  export PATH="$VOLTA_HOME/bin:$PATH"
fi

volta install node@22.19.0

npm install

cd ../../

echo "[8/8] DONE ✅"
