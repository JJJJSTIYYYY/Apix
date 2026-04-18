Write-Host "==== APIX One-click Setup (Windows) ===="

Write-Host "[1/8] Init project..."

# ---------------------------
# Build sandbox
# ---------------------------
Write-Host "[2/8] Building agent sandbox..."
cd .\README\script\AgentSandbox\
docker build -t agent-sandbox .
cd ..\..\..\

# ---------------------------
# Redis
# ---------------------------
Write-Host "[3/8] Starting Redis..."

mkdir .\MEMORY\memory_module\data\redis\data-redis-memo -Force
mkdir .\MEMORY\memory_module\data\redis\data-redis-task -Force
mkdir .\AGENT\agent_module\data\redis\data-redis-longterm-memory -Force

docker pull redis:7

docker run -d --name redis-memo -p 6379:6379 `
  -v ${PWD}\MEMORY\memory_module\data\redis\data-redis-memo:/data redis:7

docker run -d --name redis-task -p 6380:6379 `
  -v ${PWD}\MEMORY\memory_module\data\redis\data-redis-task:/data redis:7

docker run -d --name redis-longterm-memory -p 6378:6379 `
  -v ${PWD}\AGENT\agent_module\data\redis\data-redis-longterm-memory:/data redis:7

# ---------------------------
# MySQL
# ---------------------------
Write-Host "[4/8] Starting MySQL..."

mkdir .\MEMORY\memory_module\data\mysql_data -Force

docker pull mysql:8.0

docker run -d --name apix-mysql -p 3307:3306 `
  -v ${PWD}\MEMORY\memory_module\data\mysql_data:/var/lib/mysql `
  -e MYSQL_ROOT_PASSWORD=your_root_password `
  -e MYSQL_DATABASE=apix_database `
  -e MYSQL_USER=apix `
  -e MYSQL_PASSWORD=apixapix mysql:8.0

Start-Sleep -Seconds 10

Write-Host "[5/8] Initializing database..."

docker exec -i apix-mysql `
  mysql -u root -pyour_root_password apix_database `
  < .\README\script\init_mysql_backup.sql

# ---------------------------
# Backend
# ---------------------------
Write-Host "[6/8] Init backend..."

pip install -U uv

$modules = @(
  "AGENT/agent_module",
  "MEMORY/memory_module",
  "FILE/file_service",
  "TOOLS/tools_module",
  "LOGIN_REGISTER/login_register_module",
  "TASK/task_flow_module"
)

foreach ($m in $modules) {
    cd $m
    uv sync
    cd ../../
}

# ---------------------------
# Frontend
# ---------------------------
Write-Host "[7/8] Init frontend..."

cd .\CLIENT\apix-app

winget install Volta.Volta -e --id Volta.Volta

volta install node@22.19.0

npm install

Write-Host "[8/8] DONE ✅"