"use strict";
const electron = require("electron");
const preload = require("@electron-toolkit/preload");
const api = {
  readData: (key) => electron.ipcRenderer.invoke("readData", key),
  writeData: (key, value) => electron.ipcRenderer.invoke("writeData", key, value),
  submitCase: (cid, content) => electron.ipcRenderer.invoke("api:submit_case", cid, content),
  openFileDialog: (type, extensions) => electron.ipcRenderer.invoke("openFileDialog", type, extensions),
  openDir: (path, fileName = "") => electron.ipcRenderer.invoke("openDir", path, fileName),
  openCacheDir: () => electron.ipcRenderer.invoke("openCacheDir"),
  watchWorkspace: (dirPath) => electron.ipcRenderer.invoke("fs:watch", dirPath),
  unwatchWorkspace: () => electron.ipcRenderer.invoke("fs:unwatch"),
  getDirectoryTree: (targetPath) => electron.ipcRenderer.invoke("fs:getDirectoryTree", targetPath),
  watchDirectoryNode: (targetPath) => electron.ipcRenderer.invoke("fs:watchDirectoryNode", targetPath),
  collapseDirectoryTree: (targetPath) => electron.ipcRenderer.invoke("fs:collapseDirectoryTree", targetPath),
  createFile: (filePath, encoding = "utf-8") => electron.ipcRenderer.invoke("fs:createFile", filePath, encoding),
  deleteFile: (filePath) => electron.ipcRenderer.invoke("fs:deleteFile", filePath),
  readFile: (filePath, encoding = "utf-8") => electron.ipcRenderer.invoke("fs:readFile", filePath, encoding),
  reReadFile: (filePath, version, baseContent = "", encoding = "utf-8") => electron.ipcRenderer.invoke("fs:reReadFile", filePath, version, baseContent, encoding),
  writeFile: (filePath, content, encoding = "utf-8") => electron.ipcRenderer.invoke("fs:writeFile", filePath, content, encoding),
  searchFiles: (cwd) => electron.ipcRenderer.invoke("fs:searchFiles", cwd),
  createDirectory: (dirPath) => electron.ipcRenderer.invoke("fs:createDirectory", dirPath),
  deleteDirectory: (dirPath) => electron.ipcRenderer.invoke("fs:deleteDirectory", dirPath),
  rename: (oldPath, newPath) => electron.ipcRenderer.invoke("fs:rename", oldPath, newPath),
  searchText: (keyword, cwd) => electron.ipcRenderer.invoke("fs:searchText", keyword, cwd),
  createSkillFolder: (atPath, skillName) => electron.ipcRenderer.invoke("fs:createSkillFolder", atPath, skillName),
  compressSkillFloder: (atPath) => electron.ipcRenderer.invoke("fs:compressSkillFloder", atPath),
  /**
   * Listen fs watcher events from main process
   * @param callback (events: any[]) => void
   * @returns unsubscribe function
   */
  onFsEvents: (callback) => {
    const listener = (_event, events) => {
      callback(events);
    };
    electron.ipcRenderer.on(
      "fs:events",
      listener
    );
    return () => {
      electron.ipcRenderer.removeListener(
        "fs:events",
        listener
      );
    };
  },
  // Send chat request (fire-and-forget, result comes from WS push)
  chatComplations: (cid, sid, hid, content, re_generate, chat_config) => electron.ipcRenderer.invoke("api:chat", cid, sid, hid, content, re_generate, chat_config),
  sendWsEvent: (cid, action, ws_event) => electron.ipcRenderer.invoke("api:send_event", cid, action, ws_event),
  stopGeneration: (cid, sid, hid) => electron.ipcRenderer.invoke("api:stop", cid, sid, hid),
  newChat: (cid, workspace = "") => electron.ipcRenderer.invoke("api:new_chat", cid, workspace),
  updateConversation: (cid, sid, hid, new_info) => electron.ipcRenderer.invoke("api:update_conversation", cid, sid, hid, new_info),
  getChatlist: (cid) => electron.ipcRenderer.invoke("api:fetch_chat_list", cid),
  getChatMsgs: (cid, sid, hid, branch_id = "-") => electron.ipcRenderer.invoke("api:fetch_chat_messages", cid, sid, hid, branch_id),
  deleteMsgs: (cid, hid, node_ids) => electron.ipcRenderer.invoke("api:delete_messages", cid, hid, node_ids),
  // AI Task
  getAiTaskList: (clear) => electron.ipcRenderer.invoke("api:get_ai_task_list", clear),
  terminateAiTask: (history_id, task_id) => electron.ipcRenderer.invoke("api:stop_task", history_id, task_id),
  // Config AI
  getModelsList: (model_provider, api_key, config = {}) => electron.ipcRenderer.invoke("api:get_models_list", model_provider, api_key, config),
  setProxy: (http_proxy, https_proxy, no_proxy) => electron.ipcRenderer.invoke("api:set_proxy", http_proxy, https_proxy, no_proxy),
  clearVisionCache: () => electron.ipcRenderer.invoke("api:clear_vision_cache"),
  createLlmProvider: (cid, provider_meta) => electron.ipcRenderer.invoke("api:create_llm_provider", cid, provider_meta),
  getLlmProviders: (cid) => electron.ipcRenderer.invoke("api:get_llm_providers", cid),
  updateLlmProvider: (provider_id, cid, new_meta) => electron.ipcRenderer.invoke("api:update_llm_provider", provider_id, cid, new_meta),
  autoFetchModelList: (endpoint, api_key) => electron.ipcRenderer.invoke("api:auto_fetch_model_list", endpoint, api_key),
  createMcpServer: (cid, mcp_meta) => electron.ipcRenderer.invoke("api:create_mcp_server", cid, mcp_meta),
  getMcpServers: (cid) => electron.ipcRenderer.invoke("api:get_mcp_servers", cid),
  updateMcpServer: (mcp_id, cid, new_meta) => electron.ipcRenderer.invoke("api:update_mcp_server", mcp_id, cid, new_meta),
  getMcpTools: (mcp_id, cid, mcp_meta) => electron.ipcRenderer.invoke("api:get_mcp_tools", mcp_id, cid, mcp_meta),
  // AI files
  loadResource: (cid, file_id) => electron.ipcRenderer.invoke("api:load_resource", cid, file_id),
  getEmbedList: (model_provider, api_key) => electron.ipcRenderer.invoke("api:get_embed_list", model_provider, api_key),
  uploadAiFiles: (cid, files) => electron.ipcRenderer.invoke("api:upload_files", cid, files),
  uploadSkillFiles: (cid, files) => electron.ipcRenderer.invoke("api:upload_skills", cid, files),
  getAvailableSkills: (cid, limit) => electron.ipcRenderer.invoke("api:get_available_skills", cid, limit),
  updateSkillStatus: (cid, skill_id, active) => electron.ipcRenderer.invoke("api:update_skill_status", cid, skill_id, active),
  deleteSkill: (cid, skill_id) => electron.ipcRenderer.invoke("api:delete_skill", cid, skill_id),
  uploadDocumentFiles: (cid, files) => electron.ipcRenderer.invoke("api:upload_documents", cid, files),
  embedDocumentFile: (cid, document_id, model) => electron.ipcRenderer.invoke("api:embed_document", cid, document_id, model),
  getAvailableDocuments: (cid, limit) => electron.ipcRenderer.invoke("api:get_available_documents", cid, limit),
  updateDocumentsStatus: (cid, document_id, active) => electron.ipcRenderer.invoke("api:update_document_status", cid, document_id, active),
  updateDocumentsDesc: (cid, document_id, desc) => electron.ipcRenderer.invoke("api:update_document_description", cid, document_id, desc),
  deleteDocument: (cid, document_id) => electron.ipcRenderer.invoke("api:delete_document", cid, document_id),
  openImageTemp: (base64, fileName) => electron.ipcRenderer.invoke("openImageTemp", base64, fileName),
  createTempFileFromBase64: (base64, fileName) => electron.ipcRenderer.invoke("createTempFileFromBase64", base64, fileName),
  // Clipboard helper
  copyToClipboard: (payload) => electron.ipcRenderer.invoke("api:copyToClipboard", payload),
  auth: {
    login: (username, password) => electron.ipcRenderer.invoke("auth:login", { username, password }),
    register: (username, password) => electron.ipcRenderer.invoke("auth:register", { username, password }),
    ensure: (client_id) => electron.ipcRenderer.invoke("auth:ensure_user", client_id)
  },
  closeWebsocket: () => electron.ipcRenderer.invoke("api:closeWebsocket"),
  initWebsocket: (clientId) => electron.ipcRenderer.invoke("api:initWebsocket", clientId),
  /**
   * Listen websocket pushed messages from main process
   * @param callback (payload: any) => void
   * @returns unsubscribe function
   */
  onWsMessage: (callback) => {
    electron.ipcRenderer.send("ws:subscribe");
    const listener = (_event, payload) => {
      callback(payload);
    };
    electron.ipcRenderer.on("ws:message", listener);
    return () => {
      electron.ipcRenderer.send("ws:unsubscribe");
      electron.ipcRenderer.removeListener("ws:message", listener);
    };
  }
};
if (process.contextIsolated) {
  console.log("preload: process.contextIsolated is true");
  try {
    electron.contextBridge.exposeInMainWorld("electron", preload.electronAPI);
    electron.contextBridge.exposeInMainWorld("api", api);
  } catch (error) {
    console.error("preload expose error:", error);
  }
} else {
  console.log("preload: process.contextIsolated is false");
  window.electron = preload.electronAPI;
  window.api = api;
}
