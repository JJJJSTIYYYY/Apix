import { contextBridge, ipcRenderer } from 'electron'
import { electronAPI } from '@electron-toolkit/preload'

// Custom APIs for renderer
const api = {
  readData: (key) => ipcRenderer.invoke('readData', key),
  writeData: (key, value) => ipcRenderer.invoke('writeData', key, value),
  submitCase: (cid, content) => ipcRenderer.invoke('api:submit_case', cid, content),

  openFileDialog: (type, extensions) => ipcRenderer.invoke('openFileDialog', type, extensions),
  openCacheDir: () => ipcRenderer.invoke('openCacheDir'),

  // Send chat request (fire-and-forget, result comes from WS push)
  chatComplations: (cid, sid, hid, content, re_generate, chat_config) =>
    ipcRenderer.invoke('api:chat', cid, sid, hid, content, re_generate, chat_config),
  stopGeneration: (cid, sid, hid) =>
    ipcRenderer.invoke('api:stop', cid, sid, hid),
  newChat: (cid) =>
    ipcRenderer.invoke('api:new_chat', cid),
  updateConversation: (cid, sid, hid, new_info) =>
    ipcRenderer.invoke('api:update_conversation', cid, sid, hid, new_info),
  getChatlist: (cid) =>
    ipcRenderer.invoke('api:fetch_chat_list', cid),
  getChatMsgs: (cid, sid, hid, branch_id = '-') =>
    ipcRenderer.invoke('api:fetch_chat_messages', cid, sid, hid, branch_id),
  deleteMsgs: (cid, hid, node_ids) =>
    ipcRenderer.invoke('api:delete_messages', cid, hid, node_ids),
  startTask: (tid) =>
    ipcRenderer.invoke('api:start_task', tid),
  killTask: (tname, tid, cid, hid) =>
    ipcRenderer.invoke('api:kill_task', tname, tid, cid, hid),
  getTaskInfo: (tid) =>
    ipcRenderer.invoke('api:fetch_task_info', tid),

  // AI Task
  getAiTaskList: (clear) =>
    ipcRenderer.invoke('api:get_ai_task_list', clear),
  terminateAiTask: (history_id, task_id) =>
    ipcRenderer.invoke('api:stop_task', history_id, task_id),

  // Config AI
  getModelsList: (model_provider, api_key) =>
    ipcRenderer.invoke('api:get_models_list', model_provider, api_key),
  setProxy: (http_proxy, https_proxy, no_proxy) =>
    ipcRenderer.invoke('api:set_proxy', http_proxy, https_proxy, no_proxy),
  clearVisionCache: () =>
    ipcRenderer.invoke('api:clear_vision_cache'),
  
  // AI files
  loadResource: (cid, file_id) =>
    ipcRenderer.invoke('api:load_resource', cid, file_id),
  getEmbedList: (model_provider, api_key) =>
    ipcRenderer.invoke('api:get_embed_list', model_provider, api_key),
  uploadAiFiles: (cid, files) =>
    ipcRenderer.invoke('api:upload_files', cid, files),
  uploadSkillFiles: (cid, files) =>
    ipcRenderer.invoke('api:upload_skills', cid, files),
  getAvailableSkills: (cid, limit) =>
    ipcRenderer.invoke('api:get_available_skills', cid, limit),
  updateSkillStatus: (cid, skill_id, active) =>
    ipcRenderer.invoke('api:update_skill_status', cid, skill_id, active),
  deleteSkill: (cid, skill_id) =>
    ipcRenderer.invoke('api:delete_skill', cid, skill_id),
  uploadDocumentFiles: (cid, files) =>
    ipcRenderer.invoke('api:upload_documents', cid, files),
  embedDocumentFile: (cid, document_id, model) =>
    ipcRenderer.invoke('api:embed_document', cid, document_id, model),
  getAvailableDocuments: (cid, limit) =>
    ipcRenderer.invoke('api:get_available_documents', cid, limit),
  updateDocumentsStatus: (cid, document_id, active) =>
    ipcRenderer.invoke('api:update_document_status', cid, document_id, active),
  updateDocumentsDesc: (cid, document_id, desc) =>
    ipcRenderer.invoke('api:update_document_description', cid, document_id, desc),
  deleteDocument: (cid, document_id) =>
    ipcRenderer.invoke('api:delete_document', cid, document_id),

  openImageTemp: (base64, fileName) =>
    ipcRenderer.invoke('openImageTemp', base64, fileName),
  
  // Clipboard helper
  copyToClipboard: (payload) =>
    ipcRenderer.invoke('api:copyToClipboard', payload),

  auth: {
    login: (username, password) =>
      ipcRenderer.invoke("auth:login", { username, password }),

    register: (username, password) =>
      ipcRenderer.invoke("auth:register", { username, password }),
  },

  closeWebsocket: () =>
    ipcRenderer.invoke('api:closeWebsocket'),
  initWebsocket: (clientId) =>
    ipcRenderer.invoke('api:initWebsocket', clientId),
  /**
   * Listen websocket pushed messages from main process
   * @param callback (payload: any) => void
   * @returns unsubscribe function
   */
  onWsMessage: (callback) => {
    // Explicitly subscribe when renderer starts listening
    ipcRenderer.send('ws:subscribe')

    const listener = (_event, payload) => {
      callback(payload)
    }

    ipcRenderer.on('ws:message', listener)

    // Return unsubscribe function to avoid memory leak
    return () => {
      ipcRenderer.send('ws:unsubscribe')
      ipcRenderer.removeListener('ws:message', listener)
    }
  }
}

// Expose APIs safely
if (process.contextIsolated) {
  console.log('preload: process.contextIsolated is true')
  try {
    contextBridge.exposeInMainWorld('electron', electronAPI)
    contextBridge.exposeInMainWorld('api', api)
  } catch (error) {
    console.error('preload expose error:', error)
  }
} else {
  console.log('preload: process.contextIsolated is false')
  window.electron = electronAPI
  window.api = api
}
