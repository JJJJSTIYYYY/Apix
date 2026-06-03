# 克隆项目到本地

```bash
mkdir APIX
cd APIX
git clone https://github.com/JJJJSTIYYYY/Apix.git
cd Apix
```

> 除去含有cd命令的bash命令块，以下所有 Bash 命令均在项目*根目录*（`./Apix`）下执行

---

# Docker配置

[Docker Desktop下载地址](https://www.docker.com/)

请确保 Docker Desktop 已安装并正在运行

1. Agent运行时沙箱

- 使用[Dockerfile](./script/AgentSandbox/Dockerfile)新建容器镜像

```bash
cd ./README/script/AgentSandbox/
docker build -t agent-sandbox .
```

> Tips: 此镜像中包含了常用依赖 Python、node、libreoffice，可以自行注释不需要的依赖，这个步骤通常等待较长时间

2. Redis镜像与容器配置

- 使用Docker官方Redis镜像

```bash
docker pull redis:7
```

- 启动数据缓存

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

3. MySQL镜像与容器配置

- 使用Docker官方MySQL镜像

```bash
docker pull mysql:8.0
```

- 启动MySQL容器

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

请等待 MySQL 容器启动完成（约 5~10 秒）后再执行初始化脚本

- 执行数据库初始化脚本

查看[init_mysql.sql](./script/init_mysql.sql)

```bash
docker exec -i apix-mysql \
  mysql -u root -pyour_root_password apix_database < ./README/script/init_mysql.sql
```

4. [可选] Milvus知识库配置

> Tips: 若无RAG需求，此步骤可跳过

[Milvus文档地址(中文)](https://milvus.io/docs/zh/install_standalone-docker.md)

[Milvus文档地址(英文)](https://milvus.io/docs/install_standalone-docker.md)

```bash
curl -sfL https://raw.githubusercontent.com/milvus-io/milvus/master/scripts/standalone_embed.sh -o standalone_embed.sh

bash standalone_embed.sh start
```

5. [可选] Ollama安装

[Ollama下载地址](https://ollama.com/)

[Ollama模型下载](https://ollama.com/search)

> Tips: 若有RAG需求，此步骤不可跳过，Milvus依赖于Ollama提供的嵌入模型

- 下载语言/嵌入模型

```bash
ollama pull model_name
```

---

# 项目配置

## 服务器

> 请先自行下载Python3.12环境

1. 下载uv包管理工具

```bash
# Windows
pip install -U uv

# Mac/Linux
pip3 install -U uv
```

2. 同步项目依赖并运行服务

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

## 客户端

本项目前端基于 Electron + Vue.js + electron-vite 构建，使用 Volta 管理 Node.js 版本

---

### 安装 Volta（用于管理 Node.js）

```bash
# Windows
winget install Volta.Volta

# MacOS/Linux
curl https://get.volta.sh | bash
```

安装完成后，重启终端。

---

### 安装 Node.js

本项目使用 Node.js 22.19.0

```bash
cd ./CLIENT/apix-app
volta install node@22.19.0
```

---

### 安装依赖

```bash
cd ./CLIENT/apix-app
npm install
```

---

### 启动开发环境

```bash
cd ./CLIENT/apix-app
npm run dev
```

---

### 打包应用（可选）

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

### 注意事项

* 首次启动可能需要几秒钟编译时间
* 如安装依赖失败，可尝试：

```bash
cd ./CLIENT/apix-app
rm -rf node_modules package-lock.json
npm install
```