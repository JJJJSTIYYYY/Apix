import { defineStore } from "pinia"
import { toRaw, isRef, unref, ref } from 'vue'

const DEFAULT_CONFIG = {
  // ----- app ui -----
  theme: 'light',
  lightValue: 95,
  transparencyValue: 90,
  backgroundImage: '',
  showToolLabels: false,

  // ----- chat config in setting page -----
  httpProxyUrl: '',
  httpsProxyUrl: '',
  excludeUrl: '',
  tokenLimit: 0,
  linkProvider: '',
  linkApiKey: '',
  contentPovider: '',
  contentApiKey: '',
  webContentFilter: 'rule',
  excludeWebUrl: '',
  toolsInvokeAi: false,
  remainToolsCache: false,
  longtermMemory: false,
  shorttermMemory: false,
  messageSummary: 0,
  keepNotSummary: 0,
  pureChat: false,
  agentSwarm: false,
  
  // ai permission config
  fileOpration: false,
  webSearch: false,
  knowledgeRetrieval: false,
  commandOpration: false,
  skillLoad: false,
  agentAssign: false,
  
  // ----- chat config in ai page -----
  modelProvider: '',
  modelName: '',
  apiKey: '',
  deepThink: false,
  visionOn: false,
  
  // ----- extra config in data page -----
  embeddingModel: '',
  rolePrompt: {
    name: '',
    definition: '',
  },
  testExpertMode: false,
  higherRolePromptPermission: false,
  autoRefreshTask: false,
}


export const useAppCacheData = defineStore("app", {
  state: () => ({
    // ---------- UI config (single source of truth)
    config: { ...DEFAULT_CONFIG },

    // ---------- UI state (non-persistent)
    activedTabName: "",
    current_history_id: '-1',
    currentWorkDir: '',

    // ---------- data
    cards: [],
    tabs: [],
    messages: [],
    work_dir: {}, // {hid: work_dir}
    apiKeyCache: {}, // {provider: api_key}
    role_prompts: [], // {id, roleName, roleDefinition, enabled}
  }),

  actions: {
    // ----------------
    // App init
    // ----------------
    async init() {
      try {
        // Restore config first (do NOT reset defaults here)
        this.restoreAllConfig()
        this.restoreWorkDir()
        this.restoreRolePrompts()
        this.restoreApiKeyCache()

        const cards = await this.readCards()
        const tabs = await this.readTabs()

        if (Array.isArray(cards)) this.cards = cards
        if (Array.isArray(tabs)) this.tabs = tabs
      } catch (e) {
        console.error("store.init error", e)
      }
    },

    // ----------------
    // Config
    // ----------------
    restoreAllConfig() {
      Object.keys(DEFAULT_CONFIG).forEach((key) => {
        const value = localStorage.getItem(key)
        if (value === null) return

        const defaultValue = DEFAULT_CONFIG[key]

        if (typeof defaultValue === 'boolean') {
          this.config[key] = value === 'true'
        } 
        else if (typeof defaultValue === 'number') {
          this.config[key] = Number(value)
        }
        else if (typeof defaultValue === 'object') {
          try {
            this.config[key] = JSON.parse(value)
          } catch {
            this.config[key] = defaultValue
          }
        }
        else {
          this.config[key] = value
        }
      })
    },

    restoreWorkDir() {
      try {
        const raw = localStorage.getItem("work_dir_map")
        if (!raw) return

        const parsed = JSON.parse(raw)

        if (parsed && typeof parsed === "object") {
          this.work_dir = parsed
        }
      } catch (e) {
        console.error("restoreWorkDir failed:", e)
        this.work_dir = {}
      }
    },

    restoreApiKeyCache() {
      try {
        const raw = localStorage.getItem("api_key_cache")

        if (!raw) {
          this.apiKeyCache = {}
          return
        }

        const parsed = JSON.parse(raw)

        if (parsed && typeof parsed === "object") {
          this.apiKeyCache = parsed
        } else {
          this.apiKeyCache = {}
        }
      } catch (e) {
        console.error("restoreApiKeyCache failed:", e)
        this.apiKeyCache = {}
      }
    },

    restoreRolePrompts() {
      try {
        const raw = localStorage.getItem("role_prompts")

        if (!raw) {
          this.role_prompts = []
          return
        }

        const parsed = JSON.parse(raw)

        if (Array.isArray(parsed)) {
          this.role_prompts = parsed
        } else {
          this.role_prompts = []
        }
      } catch (e) {
        console.error("restoreRolePrompts failed:", e)
        this.role_prompts = []
      }
    },

    persistWorkDir() {
      try {
        localStorage.setItem(
          "work_dir_map",
          JSON.stringify(toRaw(this.work_dir))
        )
      } catch (e) {
        console.error("persistWorkDir failed:", e)
      }
    },

    persistApiKeyCache() {
      try {
        localStorage.setItem(
          "api_key_cache",
          JSON.stringify(toRaw(this.apiKeyCache))
        )
      } catch (e) {
        console.error("persistApiKeyCache failed:", e)
      }
    },

    persistRolePrompts() {
      try {
        localStorage.setItem(
          "role_prompts",
          JSON.stringify(toRaw(this.role_prompts))
        )
      } catch (e) {
        console.error("persistRolePrompts failed:", e)
      }
    },

    setWorkDir(history_id, dir) {
      if (!history_id) return

      this.work_dir[history_id] = dir
      this.persistWorkDir()
    },

    getWorkDir(history_id) {
      if (!history_id) return ""

      return this.work_dir[history_id] || ""
    },

    removeWorkDir(history_id) {
      if (!history_id) return

      delete this.work_dir[history_id]
      this.persistWorkDir()
    },

    addRolePrompt(role) {
      if (!role || !role.id) return

      this.role_prompts.push(role)
      this.persistRolePrompts()
    },

    setApiKeyCache(provider, apiKey) {
      if (!provider) return

      this.apiKeyCache[provider] = apiKey || ""
      this.persistApiKeyCache()
    },

    getApiKeyCache(provider) {
      if (!provider) return ""

      return this.apiKeyCache[provider] || ""
    },

    removeApiKeyCache(provider) {
      if (!provider) return

      delete this.apiKeyCache[provider]
      this.persistApiKeyCache()
    },

    updateRolePrompt(updatedRole) {
      if (!updatedRole || !updatedRole.id) return

      const index = this.role_prompts.findIndex(r => r.id === updatedRole.id)
      if (index === -1) return

      this.role_prompts[index] = updatedRole
      this.persistRolePrompts()
    },

    removeRolePrompt(roleId) {
      if (!roleId) return

      this.role_prompts = this.role_prompts.filter(r => r.id !== roleId)
      this.persistRolePrompts()
    },

    toggleRolePrompt(roleId) {
      const role = this.role_prompts.find(r => r.id === roleId)
      if (!role) return

      role.enabled = !role.enabled
      this.persistRolePrompts()
    },

    _saveAppConfig(key, value) {
      try {
        const rawValue = isRef(value) ? unref(value) : value
        this.config[key] = rawValue
        localStorage.setItem(key, String(rawValue))
        console.log('Save onfig: Key: ', key, " Value: ", value)
      } catch (e) {
        console.error("saveAppConfig failed:", e)
      }
    },

    saveAppConfig(key, value) {
      try {
        const rawValue = isRef(value) ? unref(value) : value
        this.config[key] = rawValue

        // 支持对象
        if (typeof rawValue === 'object') {
          localStorage.setItem(key, JSON.stringify(rawValue))
        } else {
          localStorage.setItem(key, String(rawValue))
        }

      } catch (e) {
        console.error("saveAppConfig failed:", e)
      }
    },

    toggleTheme() {
      const next = this.config.theme === 'light' ? 'dark' : 'light'
      this.saveAppConfig('theme', next)
    },

    // ----------------
    // Tabs helpers
    // ----------------
    findTab(tabKey) {
      return this.tabs.findIndex(t => t.tabKey === tabKey)
    },

    async readCards() {
      return (await window.api.readData("cards")) ?? []
    },

    async readTabs() {
      const tabKeys = await window.api.readData("tabs")

      if (Array.isArray(tabKeys) && tabKeys.length > 0) {
        const tabs = []
        for (const tabKey of tabKeys) {
          tabs.push(await this.readTab(tabKey))
        }
        return tabs
      }

      return [{
        tabKey: Date.now().toString(),
        title: "任务流 1",
        items: [],
      }]
    },

    async readTab(tabKey) {
      return (
        (await window.api.readData(`tab_${tabKey}`)) ?? {
          tabKey,
          title: "任务流 1",
          items: [],
        }
      )
    },

    saveCards() {
      window.api.writeData('cards', toRaw(this.cards))
    },

    saveTabs() {
      const tabKeys = this.tabs.map(t => t.tabKey)
      window.api.writeData('tabs', tabKeys)
    },

    saveTab(tabKey) {
      const tab = this.tabs.find(t => t.tabKey === tabKey)
      if (tab) {
        window.api.writeData(`tab_${tab.tabKey}`, toRaw(tab))
      }
    },

    saveAllTabs() {
      const tabKeys = this.tabs.map(t => t.tabKey)
      window.api.writeData('tabs', tabKeys)

      for (const tab of this.tabs) {
        window.api.writeData(`tab_${tab.tabKey}`, toRaw(tab))
      }
    },
  }
})