# 🚀 APIX - A full-stack AI agent platform

> A modern, modular AI agent system with extensible architecture and full-stack integration.

*Version 1.1*

---

## ✨ Overview

**APIX** is a full-stack AI agent platform designed for building intelligent, scalable, and extensible applications.

It integrates:

* 🧠 Multi-agent runtime system
* 💾 Memory management (short-term & long-term)
* 🔧 Tool calling framework
* 📁 File service support
* 🔐 Authentication system
* ⚙️ Task orchestration pipeline
* 🖥️ Desktop client (Electron + Vue)

The project is built with a modular architecture, making it easy to customize, extend, and deploy in different scenarios.

---

## 🧩 Architecture Highlights

* **Backend**: Python-based micro-modules (Agent, Memory, Tools, Task Flow, etc.)
* **Frontend**: Electron + Vue + Vite
* **Storage**: MySQL + Redis
* **Optional**: Milvus (vector database) + Ollama (local LLM / embedding)

---

## 📦 Project Structure

```
APIX/
├── AGENT/                 # AI agent runtime
├── MEMORY/                # Memory system (Redis + MySQL)
├── TOOLS/                 # Tool calling modules
├── TASK/                  # Task orchestration
├── FILE/                  # File service
├── LOGIN_REGISTER/        # Auth system
├── CLIENT/                # Electron frontend
└── README/                # Setup & documentation
```

---

## 🚀 Getting Started

Please refer to the detailed setup guides:

* 🇨🇳 [中文文档](./README/README_zh.md): `./README/README_zh.md`
* 🇺🇸 [English Docs](./README/README_en.md): `./README/README_en.md`

---

## 🌟 Features

* Modular multi-agent system
* Streaming response support
* Persistent memory (short-term & long-term)
* Tool invocation & extensibility
* Task-based workflow execution
* Cross-platform desktop client
* Docker-based deployment support

---

## 🛠️ Tech Stack

* **Backend**: Python 3.12, FastAPI
* **Frontend**: Electron, Vue 3, Vite
* **Database**: MySQL, Redis
* **Vector DB (Optional)**: Milvus
* **LLM Runtime (Optional)**: Ollama

---

## 📌 Notes

* This project is under active development
* Contributions, issues, and discussions are welcome

---

## 📄 License

MIT License

---

## 💡 Vision

APIX aims to provide a flexible foundation for building next-generation AI applications, combining agent-based intelligence with robust engineering practices.

---

| Broken Feature | Estimated Fix Version |
|----------------|------------------------|
| Async tools service | v1.3 |

---

⭐ If you find this project useful, feel free to give it a star!
