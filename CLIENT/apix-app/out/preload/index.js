"use strict";
const electron = require("electron");
const preload = require("@electron-toolkit/preload");
const api = {
  readData: (key) => electron.ipcRenderer.invoke("readData", key),
  writeData: (key, value) => electron.ipcRenderer.invoke("writeData", key, value),
  submitCase: (cid, content) => electron.ipcRenderer.invoke("api:submit_case", cid, content),
  openFileDialog: () => electron.ipcRenderer.invoke("openFileDialog"),
  openCacheDir: () => electron.ipcRenderer.invoke("openCacheDir"),
  // Send chat request (fire-and-forget, result comes from WS push)
  chatComplations: (cid, sid, hid, content, chat_config) => electron.ipcRenderer.invoke("api:chat", cid, sid, hid, content, chat_config),
  stopGeneration: (cid, sid, hid) => electron.ipcRenderer.invoke("api:stop", cid, sid, hid),
  newChat: (cid) => electron.ipcRenderer.invoke("api:new_chat", cid),
  updateConversation: (cid, sid, hid, new_info) => electron.ipcRenderer.invoke("api:update_conversation", cid, sid, hid, new_info),
  getChatlist: (cid) => electron.ipcRenderer.invoke("api:fetch_chat_list", cid),
  getChatMsgs: (cid, sid, hid) => electron.ipcRenderer.invoke("api:fetch_chat_messages", cid, sid, hid),
  startTask: (tid) => electron.ipcRenderer.invoke("api:start_task", tid),
  killTask: (tname, tid, cid, hid) => electron.ipcRenderer.invoke("api:kill_task", tname, tid, cid, hid),
  getTaskInfo: (tid) => electron.ipcRenderer.invoke("api:fetch_task_info", tid),
  // AI Task
  getAiTaskList: (clear) => electron.ipcRenderer.invoke("api:get_ai_task_list", clear),
  terminateAiTask: (history_id, task_id) => electron.ipcRenderer.invoke("api:stop_task", history_id, task_id),
  // Config AI
  getModelsList: (model_provider, api_key) => electron.ipcRenderer.invoke("api:get_models_list", model_provider, api_key),
  setProxy: (http_proxy, https_proxy, no_proxy) => electron.ipcRenderer.invoke("api:set_proxy", http_proxy, https_proxy, no_proxy),
  clearVisionCache: () => electron.ipcRenderer.invoke("api:clear_vision_cache"),
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
  // Clipboard helper
  copyToClipboard: (payload) => electron.ipcRenderer.invoke("api:copyToClipboard", payload),
  auth: {
    login: (username, password) => electron.ipcRenderer.invoke("auth:login", { username, password }),
    register: (username, password) => electron.ipcRenderer.invoke("auth:register", { username, password })
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
