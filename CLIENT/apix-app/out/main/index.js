"use strict";
const electron = require("electron");
const utils = require("@electron-toolkit/utils");
const path = require("path");
const fs = require("fs");
const os = require("os");
const crypto = require("crypto");
const axios = require("axios");
const FormData = require("form-data");
const yaml = require("js-yaml");
const WebSocket$1 = require("ws");
let ws = null;
let reconnectTimer = null;
let reconnectDelay = 1e3;
const MAX_RECONNECT_DELAY = 5e3;
let manuallyClosed = false;
const wsSubscribers = /* @__PURE__ */ new Map();
electron.ipcMain.on("ws:subscribe", (event) => {
  const wc = event.sender;
  wsSubscribers.set(wc.id, wc);
});
electron.ipcMain.on("ws:unsubscribe", (event) => {
  wsSubscribers.delete(event.sender.id);
});
function initWS(clientId) {
  if (ws) return ws;
  manuallyClosed = false;
  console.log("[WS] trying to connect...");
  ws = new WebSocket$1(`ws://localhost:5091/ws/${clientId}`);
  ws.on("open", () => {
    console.log("[WS] connected");
    reconnectDelay = 2e3;
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
  });
  ws.on("message", (data) => {
    let payload;
    try {
      payload = JSON.parse(data.toString());
    } catch (err) {
      console.error("[WS] invalid json:", err);
      return;
    }
    for (const wc of wsSubscribers.values()) {
      if (!wc.isDestroyed()) {
        wc.send("ws:message", payload);
      }
    }
  });
  ws.on("close", () => {
    console.warn("[WS] closed");
    ws = null;
    if (manuallyClosed) return;
    scheduleReconnect(clientId);
  });
  ws.on("error", (err) => {
    console.error("[WS] error:", err);
    try {
      ws.close();
    } catch (_) {
    }
  });
  return ws;
}
function scheduleReconnect(clientId) {
  if (reconnectTimer) return;
  console.warn(`[WS] reconnecting in ${reconnectDelay}ms...`);
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    initWS(clientId);
    reconnectDelay = Math.min(
      reconnectDelay * 1.5,
      MAX_RECONNECT_DELAY
    );
  }, reconnectDelay);
}
function closeWS() {
  manuallyClosed = true;
  if (reconnectTimer) {
    clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }
  if (ws) {
    ws.close();
    ws = null;
  }
  wsSubscribers.clear();
}
function waitForOpen(ws2, timeout = 5e3) {
  return new Promise((resolve, reject) => {
    if (ws2.readyState === WebSocket$1.OPEN) return resolve();
    const timer = setTimeout(() => reject(new Error("WebSocket open timeout")), timeout);
    ws2.once("open", () => {
      clearTimeout(timer);
      resolve();
    });
    ws2.once("close", () => {
      clearTimeout(timer);
      reject(new Error("WebSocket closed before open"));
    });
    ws2.once("error", (err) => {
      clearTimeout(timer);
      reject(err);
    });
  });
}
function registerWebsocketIpc() {
  console.log("registerWebsocketIpc...");
  electron.ipcMain.handle("api:closeWebsocket", (event) => {
    try {
      closeWS();
      return true;
    } catch (err) {
      console.error("closeWebsocket error:", err);
      return false;
    }
  });
  electron.ipcMain.handle("api:initWebsocket", (event, clientId) => {
    try {
      closeWS();
      initWS(clientId);
      return true;
    } catch (err) {
      console.error("initWebsocket error:", err);
      return false;
    }
  });
}
const isMac = process.platform === "darwin";
const isWin = process.platform === "win32";
function registerWindowIpc(win) {
  console.log("registerWindowIpc...");
  electron.ipcMain.on("window-minimize", () => win.minimize());
  electron.ipcMain.on("window-maximize", () => {
    win.isMaximized() ? win.unmaximize() : win.maximize();
  });
  electron.ipcMain.on("window-close", () => {
    isWin ? win.close() : electron.app.quit();
  });
}
const MAX_FILE_SIZE = 5 * 1024 * 1024;
function registerFileIpc() {
  console.log("registerFileIpc...");
  const dataDir = path.join(electron.app.getPath("userData"), "ApiX");
  if (!fs.existsSync(dataDir)) fs.mkdirSync(dataDir, { recursive: true });
  console.log("Apix data dir:", dataDir);
  electron.ipcMain.handle("openFileDialog", async () => {
    const result = await electron.dialog.showOpenDialog({
      title: "选择文件",
      properties: ["openFile", "openDirectory"]
    });
    if (result.canceled || result.filePaths.length === 0) {
      return result;
    }
    const filePath = result.filePaths[0];
    const stat = fs.statSync(filePath);
    if (stat.size > MAX_FILE_SIZE) {
      throw new Error("File size exceeds 5MB limit.");
    }
    return result;
  });
  electron.ipcMain.handle("openCacheDir", async () => {
    try {
      const dataDir2 = path.join(electron.app.getPath("userData"), "ApiX");
      if (!fs.existsSync(dataDir2)) {
        fs.mkdirSync(dataDir2, { recursive: true });
      }
      console.log("Apix data dir:", dataDir2);
      const err = await electron.shell.openPath(dataDir2);
      if (err) {
        console.error("Failed to open directory:", err);
        return { success: false, error: err };
      }
      return { success: true, path: dataDir2 };
    } catch (e) {
      console.error("openCacheDir error:", e);
      return { success: false, error: String(e) };
    }
  });
  electron.ipcMain.handle("openImageTemp", async (_, base64, fileName) => {
    try {
      const tempDir = path.join(os.tmpdir(), "apix-images");
      if (!fs.existsSync(tempDir)) {
        fs.mkdirSync(tempDir, { recursive: true });
      }
      const filePath = path.join(tempDir, fileName);
      fs.writeFileSync(filePath, Buffer.from(base64, "base64"));
      await electron.shell.openPath(filePath);
      return { success: true, path: filePath };
    } catch (err) {
      console.error("openImageTemp error:", err);
      return { success: false, error: String(err) };
    }
  });
}
const WebSocket = require("ws");
const MEMORY_API_BASE = "http://127.0.0.1:5093";
const TOOLS_API_BASE = "http://127.0.0.1:5092";
function registerAiIpc() {
  console.log("registerAiIpc...");
  electron.ipcMain.handle("api:chat", async (event, cid, sid, hid, content, chat_config) => {
    let ws2 = initWS(cid);
    try {
      await waitForOpen(ws2);
    } catch (err) {
      throw new Error("WebSocket not connected, please try again!");
    }
    if (!ws2 || ws2.readyState !== WebSocket.OPEN) {
      throw new Error("WebSocket not connected, please try again!");
    }
    ws2.send(
      JSON.stringify({
        action: "chat_with_llm",
        data: {
          client_id: cid,
          session_id: sid,
          history_id: hid,
          messages: content,
          config: chat_config
        }
      })
    );
    return true;
  });
  electron.ipcMain.handle("api:stop", async (event, cid, sid, hid) => {
    let ws2 = initWS(cid);
    try {
      await waitForOpen(ws2);
    } catch (err) {
      throw new Error("WebSocket not connected, please try again!");
    }
    if (!ws2 || ws2.readyState !== WebSocket.OPEN) {
      throw new Error("WebSocket not connected, please try again!");
    }
    ws2.send(
      JSON.stringify({
        action: "abort_generation",
        data: {
          client_id: cid,
          session_id: sid,
          history_id: hid
        }
      })
    );
    return true;
  });
  electron.ipcMain.handle("api:new_chat", async (event, cid) => {
    try {
      const res = await fetch(`${MEMORY_API_BASE}/memory/memory/conversation/create`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          client_id: cid,
          session_id: "",
          title: "新的聊天..."
        })
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Create conversation failed.");
      }
      return data;
    } catch (err) {
      console.error("Create conversation error:", err);
      throw err;
    }
  });
  electron.ipcMain.handle("api:update_conversation", async (event, cid, sid, hid, new_info) => {
    try {
      const res = await fetch(`${MEMORY_API_BASE}/memory/user/conversations/update`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          client_id: cid,
          session_id: sid,
          history_id: hid,
          title: new_info.title ?? null,
          is_pinned: new_info.star ?? null,
          is_deleted: new_info.deleted ?? null
        })
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Update conversation failed.");
      }
      return data;
    } catch (err) {
      console.error("Update conversation error:", err);
      throw err;
    }
  });
  electron.ipcMain.handle("api:fetch_chat_list", async (event, cid) => {
    try {
      const res = await fetch(`${MEMORY_API_BASE}/memory/user/conversations/list`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          client_id: cid,
          session_id: ""
        })
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Get conversation list failed.");
      }
      return data;
    } catch (err) {
      console.error("Get conversation list error:", err);
      throw err;
    }
  });
  electron.ipcMain.handle("api:fetch_chat_messages", async (event, cid, sid, hid) => {
    try {
      const res = await fetch(`${MEMORY_API_BASE}/memory/user/messages`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          client_id: cid,
          history_id: hid
        })
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Fetch conversation msgs failed.");
      }
      return data;
    } catch (err) {
      console.error("Fetch conversation msgs error:", err);
      throw err;
    }
  });
  electron.ipcMain.handle("api:start_task", async (event, tid) => {
    try {
      const res = await fetch(`${TOOLS_API_BASE}/task/start`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          task_id: tid
        })
      });
      const data = await res.json();
      if (!res.ok) {
        return "fail";
      }
      return data;
    } catch (err) {
      console.error("Start task error:", err);
      throw err;
    }
  });
  electron.ipcMain.handle("api:kill_task", async (event, tname, tid, cid, hid) => {
    try {
      const res = await fetch(`${TOOLS_API_BASE}/task/kill`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          tool_name: tname,
          task_id: tid,
          client_id: cid,
          history_id: hid
        })
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Kill task failed.");
      }
      return data;
    } catch (err) {
      console.error("Kill task error:", err);
      throw err;
    }
  });
  electron.ipcMain.handle("api:fetch_task_info", async (event, tid) => {
    try {
      const res = await fetch(`${MEMORY_API_BASE}/memory/task/info`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          task_id: tid,
          task_hash: ""
        })
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Fetch task info failed.");
      }
      return data;
    } catch (err) {
      console.error("Fetch task info error:", err);
      throw err;
    }
  });
}
function registerClipboardIpc() {
  console.log("registerClipboardIpc...");
  electron.ipcMain.handle("api:copyToClipboard", (event, payload) => {
    try {
      if (payload.type === "text") {
        electron.clipboard.writeText(payload.data);
      } else if (payload.type === "image") {
        const img = electron.nativeImage.createFromDataURL(payload.data);
        electron.clipboard.writeImage(img);
      }
      return true;
    } catch (err) {
      console.error("copyToClipboard error:", err);
      return false;
    }
  });
}
const icon = "data:image/png;base64,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";
const API_BASE = "http://127.0.0.1:8000";
const AES_KEY = Buffer.from("0123456789abcdef");
const AES_IV = Buffer.from("abcdef9876543210");
function encryptPassword(password) {
  const cipher = crypto.createCipheriv("aes-128-cbc", AES_KEY, AES_IV);
  let encrypted = cipher.update(password, "utf8", "base64");
  encrypted += cipher.final("base64");
  return encrypted;
}
function registerLogreIpc() {
  console.log("registerLogreIpc...");
  electron.ipcMain.handle("auth:login", async (_, payload) => {
    try {
      const res = await fetch(`${API_BASE}/auth/login`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          username: payload.username,
          password: encryptPassword(payload.password)
        })
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.messages?.msg || "Login failed");
      }
      return data;
    } catch (err) {
      console.error("Login error:", err);
      throw err;
    }
  });
  electron.ipcMain.handle("auth:register", async (_, payload) => {
    try {
      const res = await fetch(`${API_BASE}/auth/register`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          username: payload.username,
          password: encryptPassword(payload.password)
        })
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Register failed");
      }
      return data;
    } catch (err) {
      console.error("Register error:", err);
      throw err;
    }
  });
}
const AI_API_BASE$1 = "http://localhost:5091";
function registerAiConfigIpc() {
  console.log("registerAiConfigIpc...");
  electron.ipcMain.handle("api:get_models_list", async (event, model_provider, api_key) => {
    try {
      const res = await fetch(`${AI_API_BASE$1}/api/v1/get_models_list`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          model_provider,
          api_key
        })
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Get models list failed.");
      }
      return data.messages;
    } catch (err) {
      console.error("[ipc:get_models_list] error:", err);
      throw err;
    }
  });
  electron.ipcMain.handle("api:set_proxy", async (event, http_proxy, https_proxy, no_proxy) => {
    try {
      const res = await fetch(`${AI_API_BASE$1}/api/v1/set_proxy`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          http_proxy,
          https_proxy,
          no_proxy
        })
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Set proxy failed.");
      }
      return data.messages;
    } catch (err) {
      console.error("[ipc:set_proxy] error:", err);
      throw err;
    }
  });
  electron.ipcMain.handle("api:clear_vision_cache", async (event) => {
    try {
      const res = await fetch(`${AI_API_BASE$1}/api/v1/clear_vision_cache`, {
        method: "GET",
        headers: {
          "Content-Type": "application/json"
        }
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Clear cache failed.");
      }
      if (!data.success) {
        throw new Error(data.messages || "Clear cache failed.");
      }
      return data.messages;
    } catch (err) {
      console.error("[ipc:clear_vision_cache] error:", err);
      throw err;
    }
  });
}
const FILE_API_BASE = "http://localhost:5094";
function registerAiFilesIpc() {
  console.log("registerAiFiles...");
  electron.ipcMain.handle("api:get_embed_list", async (event, model_provider, api_key) => {
    try {
      const resp = await axios.post(
        `${FILE_API_BASE}/file/info/get_models_list`,
        {
          model_provider,
          api_key
        },
        {
          headers: {
            "Content-Type": "application/json"
          }
        }
      );
      return resp.data.messages;
    } catch (err) {
      console.error("[ipc:get_models_list] error:", err);
      throw err;
    }
  });
  electron.ipcMain.handle("api:upload_files", async (event, cid, files) => {
    try {
      const form = new FormData();
      form.append("client_id", cid);
      for (const file of files) {
        form.append(
          "files",
          fs.createReadStream(file.path),
          file.name
        );
      }
      const resp = await axios.post(
        `${FILE_API_BASE}/file/file/insert_file`,
        form,
        {
          headers: {
            ...form.getHeaders()
          },
          // Important for large files
          maxBodyLength: Infinity,
          maxContentLength: Infinity
        }
      );
      if (resp.data.success !== true) {
        throw new Error(resp.data.messages);
      }
      return resp.data;
    } catch (err) {
      console.error("[ipc:upload_files] error:", err);
      throw err;
    }
  });
  electron.ipcMain.handle("api:upload_skills", async (event, cid, files) => {
    try {
      const form = new FormData();
      form.append("client_id", cid);
      for (const file of files) {
        form.append(
          "files",
          fs.createReadStream(file.path),
          file.name
        );
      }
      const resp = await axios.post(
        `${FILE_API_BASE}/file/skills/insert_skills`,
        form,
        {
          headers: {
            ...form.getHeaders()
          },
          // Important for large files
          maxBodyLength: Infinity,
          maxContentLength: Infinity
        }
      );
      if (resp.data.success !== true) {
        throw new Error(resp.data.messages);
      }
      return resp.data;
    } catch (err) {
      console.error("[ipc:upload_skills] error:", err);
      throw err;
    }
  });
  electron.ipcMain.handle("api:get_available_skills", async (event, cid, limit) => {
    try {
      const resp = await axios.post(
        `${FILE_API_BASE}/file/skills/get_available_skills`,
        {
          client_id: cid,
          limit
        },
        {
          headers: {
            "Content-Type": "application/json"
          }
        }
      );
      if (resp.data.success !== true) {
        throw new Error(resp.data.messages);
      }
      return resp.data.messages;
    } catch (err) {
      console.error("[ipc:get_available_skills] error:", err);
      throw err;
    }
  });
  electron.ipcMain.handle("api:update_skill_status", async (event, cid, skill_id, active) => {
    try {
      const resp = await axios.post(
        `${FILE_API_BASE}/file/skills/update_skill`,
        {
          client_id: cid,
          skill_id,
          is_active: active
        },
        {
          headers: {
            "Content-Type": "application/json"
          }
        }
      );
      if (resp.data.success !== true) {
        throw new Error(resp.data.messages);
      }
      return resp.data.messages;
    } catch (err) {
      console.error("[ipc:update_skill_status] error:", err);
      throw err;
    }
  });
  electron.ipcMain.handle("api:delete_skill", async (event, cid, skill_id) => {
    try {
      const resp = await axios.post(
        `${FILE_API_BASE}/file/skills/update_skill`,
        {
          client_id: cid,
          skill_id,
          deleted: true
        },
        {
          headers: {
            "Content-Type": "application/json"
          }
        }
      );
      if (resp.data.success !== true) {
        throw new Error(resp.data.messages);
      }
      return resp.data.messages;
    } catch (err) {
      console.error("[ipc:delete_skill] error:", err);
      throw err;
    }
  });
  electron.ipcMain.handle("api:upload_documents", async (event, cid, files) => {
    try {
      const form = new FormData();
      form.append("client_id", cid);
      for (const file of files) {
        form.append(
          "files",
          fs.createReadStream(file.path),
          file.name
        );
      }
      const resp = await axios.post(
        `${FILE_API_BASE}/file/rag/insert_document`,
        form,
        {
          headers: {
            ...form.getHeaders()
          },
          // Important for large files
          maxBodyLength: Infinity,
          maxContentLength: Infinity
        }
      );
      if (resp.data.success !== true) {
        throw new Error(resp.data.messages);
      }
      return resp.data;
    } catch (err) {
      console.error("[ipc:upload_documents] error:", err);
      throw err;
    }
  });
  electron.ipcMain.handle("api:update_document_status", async (event, cid, document_id, active) => {
    try {
      const resp = await axios.post(
        `${FILE_API_BASE}/file/rag/update_document`,
        {
          client_id: cid,
          document_id,
          is_active: active
        },
        {
          headers: {
            "Content-Type": "application/json"
          }
        }
      );
      if (resp.data.success !== true) {
        throw new Error(resp.data.messages);
      }
      return resp.data.messages;
    } catch (err) {
      console.error("[ipc:update_document_status] error:", err);
      throw err;
    }
  });
  electron.ipcMain.handle("api:update_document_description", async (event, cid, document_id, description) => {
    try {
      const resp = await axios.post(
        `${FILE_API_BASE}/file/rag/update_document`,
        {
          client_id: cid,
          document_id,
          description
        },
        {
          headers: {
            "Content-Type": "application/json"
          }
        }
      );
      if (resp.data.success !== true) {
        throw new Error(resp.data.messages);
      }
      return resp.data.messages;
    } catch (err) {
      console.error("[ipc:update_document_description] error:", err);
      throw err;
    }
  });
  electron.ipcMain.handle("api:delete_document", async (event, cid, document_id) => {
    try {
      const resp = await axios.post(
        `${FILE_API_BASE}/file/rag/update_document`,
        {
          client_id: cid,
          document_id,
          deleted: true
        },
        {
          headers: {
            "Content-Type": "application/json"
          }
        }
      );
      if (resp.data.success !== true) {
        throw new Error(resp.data.messages);
      }
      return resp.data.messages;
    } catch (err) {
      console.error("[ipc:delete_document] error:", err);
      throw err;
    }
  });
  electron.ipcMain.handle("api:get_available_documents", async (event, cid, limit) => {
    try {
      const resp = await axios.post(
        `${FILE_API_BASE}/file/rag/get_available_documents`,
        {
          client_id: cid,
          limit
        },
        {
          headers: {
            "Content-Type": "application/json"
          }
        }
      );
      if (resp.data.success !== true) {
        throw new Error(resp.data.messages);
      }
      return resp.data.messages;
    } catch (err) {
      console.error("[ipc:get_available_documents] error:", err);
      throw err;
    }
  });
  electron.ipcMain.handle("api:embed_document", async (event, cid, document_id, model) => {
    try {
      const resp = await axios.post(
        `${FILE_API_BASE}/file/rag/embed_document`,
        {
          client_id: cid,
          document_id,
          selected_embed_model: model
        },
        {
          headers: {
            "Content-Type": "application/json"
          }
        }
      );
      if (resp.data.success !== true) {
        throw new Error(resp.data.messages);
      }
      return resp.data.messages;
    } catch (err) {
      console.error("[ipc:embed_document] error:", err);
      throw err;
    }
  });
  electron.ipcMain.handle("api:load_resource", async (event, cid, fileId) => {
    try {
      const resp = await axios.get(
        `${FILE_API_BASE}/file/file/load_resource`,
        {
          params: {
            file_id: fileId,
            client_id: cid
          },
          responseType: "arraybuffer"
        }
      );
      return {
        ok: true,
        fileId,
        clientId: cid,
        contentType: resp.headers["content-type"] || "application/octet-stream",
        contentDisposition: resp.headers["content-disposition"] || "",
        etag: resp.headers["etag"] || "",
        sha256: resp.headers["x-file-sha256"] || "",
        buffer: Buffer.from(resp.data).toString("base64")
      };
    } catch (err) {
      console.error("[ipc:load_resource] error:", err?.message || err);
      const status = err?.response?.status || 500;
      const detail = err?.response?.data || err?.message || "load resource failed";
      return {
        ok: false,
        status,
        detail
      };
    }
  });
}
const AI_API_BASE = "http://localhost:5091";
function registerAiTaskIpc() {
  console.log("registerAiTaskIpc...");
  electron.ipcMain.handle("api:get_ai_task_list", async (event, clear) => {
    try {
      let api_port = "";
      if (clear) {
        api_port = "clear_finished_tasks";
      } else {
        api_port = "get_sub_agent_task_list";
      }
      const res = await fetch(`${AI_API_BASE}/api/v1/${api_port}`, {
        method: "GET",
        headers: {
          "Content-Type": "application/json"
        }
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Get task list failed.");
      }
      if (!data.success) {
        throw new Error(data.messages || "Get task list failed.");
      }
      return data.messages;
    } catch (err) {
      console.error("[ipc:get_ai_task_list] error:", err);
      throw err;
    }
  });
  electron.ipcMain.handle("api:stop_task", async (event, history_id, task_id) => {
    try {
      const res = await fetch(`${AI_API_BASE}/api/v1/stop_task`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          history_id,
          task_id
        })
      });
      const data = await res.json();
      if (!data.success) {
        throw new Error(data.messages || "Stop task failed.");
      }
      return data.messages;
    } catch (err) {
      console.error("[ipc:stop_task] error:", err);
      throw err;
    }
  });
}
const TEST_API_BASE = "http://127.0.0.1:5090";
function registerLocalTaskIpc() {
  console.log("registerLocalTaskIpc...");
  const dataDir = path.join(electron.app.getPath("userData"), "ApiX");
  if (!fs.existsSync(dataDir)) fs.mkdirSync(dataDir, { recursive: true });
  console.log("Apix data dir:", dataDir);
  electron.ipcMain.handle("readData", (event, key) => {
    const filePath = path.join(dataDir, `${key}.yaml`);
    if (!fs.existsSync(filePath)) return null;
    const content = fs.readFileSync(filePath, "utf-8").trim();
    return content ? yaml.load(content) : null;
  });
  electron.ipcMain.handle("writeData", (event, key, value) => {
    const filePath = path.join(dataDir, `${key}.yaml`);
    fs.writeFileSync(filePath, yaml.dump(value), "utf-8");
    return true;
  });
  electron.ipcMain.handle("api:submit_case", async (event, cid, content) => {
    try {
      const res = await fetch(`${TEST_API_BASE}/plugin/submit_task`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          client_id: cid,
          content
        })
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Submit case list failed.");
      }
      return data.messages;
    } catch (err) {
      console.error("[ipc:submit_case] error:", err);
      throw err;
    }
  });
}
let MicaBrowserWindow = null;
if (isWin) {
  try {
    ;
    ({ MicaBrowserWindow } = require("mica-electron"));
  } catch (e) {
    console.log("Failed to load mica-electron:", e);
  }
}
const baseWindowOptions = {
  width: 1400,
  height: 900,
  minWidth: 1400,
  minHeight: 900,
  show: false,
  autoHideMenuBar: true,
  icon,
  webPreferences: {
    preload: path.join(__dirname, "../preload/index.js"),
    sandbox: false
  }
};
const macWindowOptions = {
  ...baseWindowOptions,
  frame: false,
  transparent: true,
  vibrancy: "popover",
  visualEffectState: "active"
};
const winMicaOptions = {
  ...baseWindowOptions,
  frame: false,
  resizable: true,
  transparent: false
};
const linuxWindowOptions = {
  ...baseWindowOptions
};
function createAppWindow() {
  let mainWindow;
  if (isMac) {
    mainWindow = new electron.BrowserWindow(macWindowOptions);
  } else if (isWin && MicaBrowserWindow) {
    mainWindow = new MicaBrowserWindow(winMicaOptions);
  } else {
    mainWindow = new electron.BrowserWindow(linuxWindowOptions);
  }
  return mainWindow;
}
function createMainWindow() {
  let mainWindow = createAppWindow();
  registerWindowIpc(mainWindow);
  registerFileIpc();
  registerLocalTaskIpc();
  registerAiIpc();
  registerAiConfigIpc();
  registerAiFilesIpc();
  registerAiTaskIpc();
  registerClipboardIpc();
  registerLogreIpc();
  registerWebsocketIpc();
  mainWindow.on("ready-to-show", () => {
    if (isWin && typeof mainWindow.setMicaEffect === "function") {
      mainWindow.setMicaEffect();
      mainWindow.setRoundedCorner?.();
      mainWindow.setMicaTabbedEffect?.();
      mainWindow.setMicaAcrylicEffect?.();
    }
    mainWindow.show();
  });
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    electron.shell.openExternal(url);
    return { action: "deny" };
  });
  mainWindow.webContents.on("will-navigate", (event, url) => {
    event.preventDefault();
    electron.shell.openExternal(url);
  });
  if (utils.is.dev && process.env["ELECTRON_RENDERER_URL"]) {
    mainWindow.loadURL(process.env["ELECTRON_RENDERER_URL"]);
  } else {
    mainWindow.loadFile(path.join(__dirname, "../renderer/index.html"));
  }
  return mainWindow;
}
electron.app.whenReady().then(() => {
  const root = process.cwd();
  console.warn("root is ", root);
  utils.electronApp.setAppUserModelId("com.electron");
  if (isMac) {
    electron.app.dock.setIcon(
      "/Users/justiy/Documents/code/Project/TestPlat/CLIENT/apix-app/resources/APIX.png"
    );
  }
  electron.app.on("browser-window-created", (_, window) => {
    utils.optimizer.watchWindowShortcuts(window);
  });
  createMainWindow();
  electron.app.on("activate", () => {
    if (electron.BrowserWindow.getAllWindows().length === 0) createMainWindow();
  });
});
electron.app.on("window-all-closed", () => {
  if (!isMac) {
    closeWS();
    electron.app.quit();
  }
});
