# Clone the Project Locally

```bash
mkdir APIX
cd APIX
git clone https://github.com/JJJJSTIYYYY/Apix.git
cd Apix
```

> Except for bash command blocks containing `cd`, all the following Bash commands should be executed in the project *root directory* (`./Apix`)

---

# Docker Configuration

[Download Docker Desktop](https://www.docker.com/)

Make sure Docker Desktop is installed and running.

## 1. Agent Runtime Sandbox

* Build the container image using the [Dockerfile](./script/AgentSandbox/Dockerfile)

```bash
cd ./README/script/AgentSandbox/
docker build -t agent-sandbox .
```

> Tips: This image includes common dependencies such as Python, Node.js, and LibreOffice. You can comment out unnecessary dependencies. This step usually takes a long time.

---

## 2. Redis Image and Container Configuration

* Pull the official Redis image

```bash
docker pull redis:7
```

* Start data cache and async task containers

```bash
mkdir -p ./MEMORY/memory_module/data/redis/data-redis-memo
cd ./MEMORY/memory_module/data

# Redis for memo service
docker run -d \
  --name redis-memo \
  -p 6379:6379 \
  -v ./redis/data-redis-memo:/data \
  --restart unless-stopped \
  redis:7
```

---

## 3. MySQL Image and Container Configuration

* Pull the official MySQL image

```bash
docker pull mysql:8.0
```

* Start the MySQL container

```bash
cd ./MEMORY/memory_module/data

docker run -d \
  --name apix-mysql \
  -p 3307:3306 \
  -v ./mysql_data:/var/lib/mysql \
  -e MYSQL_ROOT_PASSWORD=your_root_password \
  -e MYSQL_DATABASE=apix_database \
  -e MYSQL_USER=apix \
  -e MYSQL_PASSWORD=apixapix \
  --restart unless-stopped \
  mysql:8.0
```

Wait for the MySQL container to fully start (about 5–10 seconds) before running the initialization script.

* Run the database initialization script

See [init_mysql.sql](./script/init_mysql.sql)

```bash
docker exec -i apix-mysql \
  mysql -u root -pyour_root_password apix_database < ./README/script/init_mysql.sql
```

---

## 4. [Optional] Milvus Knowledge Base Configuration

> Tips: If you do not need RAG, you can skip this step.

[Milvus Documentation (Chinese)](https://milvus.io/docs/zh/install_standalone-docker.md)
[Milvus Documentation (English)](https://milvus.io/docs/install_standalone-docker.md)

```bash
curl -sfL https://raw.githubusercontent.com/milvus-io/milvus/master/scripts/standalone_embed.sh -o standalone_embed.sh

bash standalone_embed.sh start
```

---

## 5. [Optional] Ollama Installation

[Download Ollama](https://ollama.com/)
[Ollama Model Library](https://ollama.com/search)

> Tips: If you need RAG, this step is required. Milvus depends on embedding models provided by Ollama.

* Download language/embedding models

```bash
ollama pull model_name
```

---

# Project Configuration

## Server

> Please install Python 3.12 in advance.

### 1. Install uv package manager

```bash
# Windows
pip install -U uv

# Mac/Linux
pip3 install -U uv
```

### 2. Sync dependencies and run services

```bash
cd ./AGENT/agent_module
uv sync
uv run main.py
```

```bash
cd ./MEMORY/memory_module
uv sync
uv run main.py
```

```bash
cd ./FILE/file_service
uv sync
uv run main.py
```

```bash
cd ./TASK/task_flow_module
uv sync
uv run main.py
```

---

## Client

The frontend is built with Electron + Vue.js + electron-vite, and uses Volta to manage Node.js versions.

---

### Install Volta (Node.js Version Manager)

```bash
# Windows
winget install Volta.Volta

# macOS/Linux
curl https://get.volta.sh | bash
```

After installation, restart your terminal.

---

### Install Node.js

This project uses Node.js 22.19.0

```bash
cd ./CLIENT/apix-app
volta install node@22.19.0
```

---

### Install Dependencies

```bash
cd ./CLIENT/apix-app
npm install
```

---

### Start Development Environment

```bash
cd ./CLIENT/apix-app
npm run dev
```

---

### Build Application (Optional)

```bash
cd ./CLIENT/apix-app

# macOS
npm run build:mac

# Windows
npm run build:win

# Linux
npm run build:linux
```

---

### Notes

* The first startup may take a few seconds for compilation.
* If dependency installation fails, try:

```bash
cd ./CLIENT/apix-app
rm -rf node_modules package-lock.json
npm install
```