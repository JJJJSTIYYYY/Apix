import { contextBridge, ipcRenderer } from 'electron'
import { electronAPI } from '@electron-toolkit/preload'

// Custom APIs for renderer
const api = {
  readData: (key) => ipcRenderer.invoke('readData', key),
  writeData: (key, value) => ipcRenderer.invoke('writeData', key, value),
  submitCase: (cid, content) => ipcRenderer.invoke('api:submit_case', cid, content),

  openFileDialog: (type, extensions) => ipcRenderer.invoke('openFileDialog', type, extensions),
  openCacheDir: () => ipcRenderer.invoke('openCacheDir'),
  watchWorkspace: (dirPath) => ipcRenderer.invoke('fs:watch', dirPath),
  unwatchWorkspace: () => ipcRenderer.invoke('fs:unwatch'),
  getDirectoryTree: (targetPath) => ipcRenderer.invoke('fs:getDirectoryTree', targetPath),
  collapseDirectoryTree: (targetPath) => ipcRenderer.invoke('fs:collapseDirectoryTree', targetPath),
  createFile: (filePath, encoding = 'utf-8') => ipcRenderer.invoke('fs:createFile', filePath, encoding),
  deleteFile: (filePath) => ipcRenderer.invoke('fs:deleteFile', filePath),
  readFile: (filePath, encoding = 'utf-8') => ipcRenderer.invoke('fs:readFile', filePath, encoding),
  writeFile: (filePath, content, encoding = 'utf-8') => ipcRenderer.invoke('fs:writeFile', filePath, content, encoding),
  searchFiles: (cwd) => ipcRenderer.invoke('fs:searchFiles', cwd),
  createDirectory: (dirPath) => ipcRenderer.invoke('fs:createDirectory', dirPath),
  deleteDirectory: (dirPath) => ipcRenderer.invoke('fs:deleteDirectory', dirPath),
  rename: (oldPath, newPath) => ipcRenderer.invoke('fs:rename', oldPath, newPath),
  searchText: (keyword, cwd) => ipcRenderer.invoke('fs:searchText', keyword, cwd),

  /**
   * Listen fs watcher events from main process
   * @param callback (events: any[]) => void
   * @returns unsubscribe function
   */
  onFsEvents: (callback) => {

    const listener = (
      _event,
      events
    ) => {
      callback(events)
    }

    ipcRenderer.on(
      'fs:events',
      listener
    )

    // Return unsubscribe function
    return () => {

      ipcRenderer.removeListener(
        'fs:events',
        listener
      )
    }
  },

  // Send chat request (fire-and-forget, result comes from WS push)
  chatComplations: (cid, sid, hid, content, re_generate, chat_config) =>
    ipcRenderer.invoke('api:chat', cid, sid, hid, content, re_generate, chat_config),
  stopGeneration: (cid, sid, hid) =>
    ipcRenderer.invoke('api:stop', cid, sid, hid),
  newChat: (cid, workspace = "") =>
    ipcRenderer.invoke('api:new_chat', cid, workspace),
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
  getModelsList: (model_provider, api_key, config = {}) =>
    ipcRenderer.invoke('api:get_models_list', model_provider, api_key, config),
  setProxy: (http_proxy, https_proxy, no_proxy) =>
    ipcRenderer.invoke('api:set_proxy', http_proxy, https_proxy, no_proxy),
  clearVisionCache: () =>
    ipcRenderer.invoke('api:clear_vision_cache'),
  createLlmProvider: (cid, provider_meta) =>
    ipcRenderer.invoke('api:create_llm_provider', cid, provider_meta),
  getLlmProviders: (cid) =>
    ipcRenderer.invoke('api:get_llm_providers', cid),
  updateLlmProvider: (provider_id, cid, new_meta) =>
    ipcRenderer.invoke('api:update_llm_provider', provider_id, cid, new_meta),
  autoFetchModelList: (endpoint, api_key) =>
    ipcRenderer.invoke('api:auto_fetch_model_list', endpoint, api_key),
  
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
  createTempFileFromBase64: (base64, fileName) =>
    ipcRenderer.invoke('createTempFileFromBase64', base64, fileName),
  
  // Clipboard helper
  copyToClipboard: (payload) =>
    ipcRenderer.invoke('api:copyToClipboard', payload),

  auth: {
    login: (username, password) =>
      ipcRenderer.invoke("auth:login", { username, password }),
    register: (username, password) =>
      ipcRenderer.invoke("auth:register", { username, password }),
    ensure: (client_id) =>
      ipcRenderer.invoke("auth:ensure_user", client_id)
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
