import { defineStore } from "pinia"
import { toRaw, isRef, unref } from 'vue'
import { setHighlightTheme } from './globalData'


// ----------------
// Default config
// ----------------
const DEFAULT_CONFIG = {
  // ----- app ui -----
  dark_theme: false,
  lightValue: 95,
  transparencyValue: 90,
  backgroundImage: '',
  showToolLabels: false,

  // ----- chat config -----
  httpProxyUrl: '',
  httpsProxyUrl: '',
  excludeUrl: '',
  tokenLimit: 0,
  linkProvider: '',
  linkApiKey: '',
  contentProvider: '',
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

  // ----- ai permissions -----
  fileOpration: false,
  webSearch: false,
  knowledgeRetrieval: false,
  commandOpration: false,
  skillLoad: false,
  agentAssign: false,

  // ----- ai page -----
  modelProvider: '',
  modelName: '',
  apiKey: '',
  deepThink: false,
  visionOn: false,

  // ----- extra -----
  embeddingModel: '',
  alwaysQuoteFile: false,

  rolePrompt: {
    name: '',
    definition: '',
  },

  testExpertMode: false,
  higherRolePromptPermission: false,
  autoRefreshTask: false,

  activeProvider: {
    provider_id: '',
    name: '',
    api_key: '',
  }
}


// ----------------
// Persist states
// ----------------
const PERSIST_STATES = {
  work_dir: {
    storageKey: 'work_dir_map',
    defaultValue: {},
  },

  workspace: {
    storageKey: 'workspace',
    defaultValue: '',
  },

  apiKeyCache: {
    storageKey: 'api_key_cache',
    defaultValue: {},
  },

  role_prompts: {
    storageKey: 'role_prompts',
    defaultValue: [],
  },

  providers: {
    storageKey: 'providers',
    defaultValue: [],
  },
}


// ----------------
// Helpers
// ----------------
function cloneDefault(value) {
  return structuredClone(value)
}

function parseStorageValue(raw, defaultValue) {
  try {
    const parsed = JSON.parse(raw)

    // Array
    if (Array.isArray(defaultValue)) {
      return Array.isArray(parsed)
        ? parsed
        : cloneDefault(defaultValue)
    }

    // Object
    if (
      typeof defaultValue === 'object'
      &&
      defaultValue !== null
    ) {
      return (
        parsed
        &&
        typeof parsed === 'object'
      )
        ? parsed
        : cloneDefault(defaultValue)
    }

    return parsed

  } catch {
    return cloneDefault(defaultValue)
  }
}


export const useAppCacheData = defineStore("app", {
  state: () => ({
    // ---------- persistent config
    config: { ...DEFAULT_CONFIG },

    // ---------- ui state
    activedTabKey: "",
    current_history_id: '-1', // Current actived history id at agent page
    currentWorkDir: '', // Current agent work dir at agent page
    mini_chat_current_history_id: {}, // page_id : current_history_id
    mini_chat_currentWorkDir: {}, // page_id : currentWorkDir

    // ---------- runtime data
    cards: [],
    tabs: [],
    messages: [],

    // ---------- persisted states
    work_dir: {}, // Local agent work dir store
    workspace: '', // Opened workspace at editor page
    apiKeyCache: {},
    role_prompts: [],
    providers: [],
  }),

  actions: {

    // ----------------
    // App init
    // ----------------
    async init() {
      try {
        this.restoreAllConfig()

        Object.keys(PERSIST_STATES).forEach((key) => {
          this.restorePersistedState(key)
          // console.log("restorePersistedState: ", key, this[key])
        })

        await this.restoreTabsAndCards()

      } catch (e) {
        console.error('store.init error:', e)
      }
    },


    // ----------------
    // Theme
    // ----------------
    applyTheme() {
      const isDark = this.config.dark_theme

      document.documentElement.setAttribute(
        'data-theme',
        isDark ? 'dark' : 'light'
      )

      setHighlightTheme(isDark)
    },


    // ----------------
    // Config
    // ----------------
    restoreAllConfig() {
      Object.keys(DEFAULT_CONFIG).forEach((key) => {
        const raw = localStorage.getItem(key)

        if (raw === null) {
          return
        }

        const defaultValue = DEFAULT_CONFIG[key]

        // Boolean
        if (typeof defaultValue === 'boolean') {
          this.config[key] = raw === 'true'
        }

        // Number
        else if (typeof defaultValue === 'number') {
          this.config[key] = Number(raw)
        }

        // Object
        else if (typeof defaultValue === 'object') {
          this.config[key] = parseStorageValue(
            raw,
            defaultValue
          )
        }

        // String
        else {
          this.config[key] = raw
        }
      })

      this.applyTheme()
    },

    saveAppConfig(key, value) {
      try {
        const rawValue = isRef(value)
          ? unref(value)
          : value

        this.config[key] = rawValue

        localStorage.setItem(
          key,
          typeof rawValue === 'object'
            ? JSON.stringify(rawValue)
            : String(rawValue)
        )

        // Auto apply theme
        if (key === 'dark_theme') {
          this.applyTheme()
        }

      } catch (e) {
        console.error('saveAppConfig failed:', e)
      }
    },


    // ----------------
    // Generic persist
    // ----------------
    restorePersistedState(stateKey) {
      const config = PERSIST_STATES[stateKey]

      if (!config) {
        console.warn(`Unknown persist state: ${stateKey}`)
        return
      }

      try {
        const raw = localStorage.getItem(
          config.storageKey
        )

        this[stateKey] = raw
          ? parseStorageValue(
              raw,
              config.defaultValue
            )
          : cloneDefault(config.defaultValue)

      } catch (e) {
        console.error(
          `restore ${stateKey} failed:`,
          e
        )

        this[stateKey] = cloneDefault(
          config.defaultValue
        )
      }
    },

    persistState(stateKey) {
      const config = PERSIST_STATES[stateKey]

      if (!config) {
        console.warn(`Unknown persist state: ${stateKey}`)
        return
      }

      try {
        localStorage.setItem(
          config.storageKey,
          JSON.stringify(
            toRaw(this[stateKey])
          )
        )

      } catch (e) {
        console.error(
          `persist ${stateKey} failed:`,
          e
        )
      }
    },


    // ----------------
    // Agent work dir
    // ----------------
    setWorkDir(history_id, dir) {
      if (!history_id) return

      this.work_dir[history_id] = dir
      this.persistState('work_dir')
    },

    getWorkDir(history_id) {
      return history_id
        ? (this.work_dir[history_id] || '')
        : ''
    },

    removeWorkDir(history_id) {
      if (!history_id) return

      delete this.work_dir[history_id]
      this.persistState('work_dir')
    },


    // ----------------
    // Api key cache
    // ----------------
    setApiKeyCache(provider, apiKey) {
      if (!provider) return

      this.apiKeyCache[provider] = apiKey || ''
      this.persistState('apiKeyCache')
    },

    getApiKeyCache(provider) {
      return provider
        ? (this.apiKeyCache[provider] || '')
        : ''
    },

    removeApiKeyCache(provider) {
      if (!provider) return

      delete this.apiKeyCache[provider]
      this.persistState('apiKeyCache')
    },


    // ----------------
    // Role prompts
    // ----------------
    addRolePrompt(role) {
      if (!role?.id) return

      this.role_prompts.push(role)
      this.persistState('role_prompts')
    },

    updateRolePrompt(updatedRole) {
      if (!updatedRole?.id) return

      const index = this.role_prompts.findIndex(
        r => r.id === updatedRole.id
      )

      if (index === -1) return

      this.role_prompts[index] = updatedRole

      this.persistState('role_prompts')
    },

    removeRolePrompt(roleId) {
      if (!roleId) return

      this.role_prompts = this.role_prompts.filter(
        r => r.id !== roleId
      )

      this.persistState('role_prompts')
    },

    toggleRolePrompt(roleId) {
      const role = this.role_prompts.find(
        r => r.id === roleId
      )

      if (!role) return

      role.enabled = !role.enabled

      this.persistState('role_prompts')
    },


    // ----------------
    // Workspace
    // ----------------
    setWorkspace(dir) {
      this.workspace = dir
      this.persistState('workspace')
    },

    getWorkspace() {
      return this.workspace || ''
    },

    removeWorkspace() {
      this.workspace = ''
      this.persistState('workspace')
    },


    // ----------------
    // Tabs helpers
    // ----------------
    findTab(tabKey) {
      return this.tabs.find(
        t => t.tabKey === tabKey
      )
    },

    async restoreTabsAndCards() {
      const cards = await this.readCards()
      const tabs = await this.readTabs()

      if (Array.isArray(cards)) {
        this.cards = cards
      }

      if (Array.isArray(tabs)) {
        this.tabs = tabs
      }
    },

    async readCards() {
      return (
        await window.api.readData('cards')
      ) ?? []
    },

    async saveCards() {
      await window.api.writeData(
        'cards',
        toRaw(this.cards)
      )
    },

    async readTabs() {
      // Read opened tabs
      const storedTabs = await window.api.readData('tabs')

      if (
        Array.isArray(storedTabs)
        &&
        storedTabs.length > 0
      ) {
        const tabs = []

        // Avoid duplicate restore
        const restoredDirs = new Set()

        for (const item of storedTabs) {
          const tabKey =
            typeof item === 'string'
              ? item
              : item?.tabKey

          if (!tabKey) {
            continue
          }

          // Restore parent directory watcher
          const lastSlashIndex =
            tabKey.lastIndexOf('/')

          if (lastSlashIndex !== -1) {
            const dirPath =
              tabKey.slice(0, lastSlashIndex)

            if (!restoredDirs.has(dirPath)) {
              restoredDirs.add(dirPath)

              try {
                console.log('[readTabs restore dir] rewatch:', dirPath)
                await window.api.watchDirectoryNode(
                  dirPath
                )
              }
              catch (err) {
                console.error(
                  '[readTabs restore dir] error:',
                  dirPath,
                  err
                )
              }
            }
          }

          try{
            const tab =
              await this.readTabContent(tabKey)

            tabs.push({
              tabKey: tabKey,

              // Prefer stored title, fallback to file name
              title:
                typeof item === 'object'
                &&
                item?.title
                  ? item.title
                  : tabKey,

              content: tab['content'],
              content_mime: tab['mime'],
              saved: true,
              status: 'default',
              version: 0,
              pinned:
                typeof item === 'object'
                  ? !!item?.pinned
                  : false
            })
          }
          catch (e) {

          }
        }

        // Pinned tabs first
        tabs.sort((a, b) => {
          // Both same pinned state
          if (!!a.pinned === !!b.pinned) {
            return 0
          }

          return a.pinned ? -1 : 1
        })

        return tabs
      }

      return []
    },

    async saveTabs() {
      // Store opened tabs
      await window.api.writeData(
        'tabs',
        this.tabs.map(t => ({
          tabKey: t.tabKey,
          title: t.title,
          pinned: t.pinned
        }))
      )
    },

    async readTabContent(tabKey) {
      return (
        await window.api.readFile(tabKey)
      ) ?? {}
    },

    async saveTabContent(tabKey) {
      const idx = this.tabs.findIndex(t => t.tabKey === tabKey)
      if (this.tabs[idx].saved && this.tabs[idx].status === 'default') return
      let content = this.tabs[idx].content
      if (typeof content === 'object') {
        content = JSON.stringify(
          toRaw(content)
        )
      }
      // console.log("Save content:", content)
      await window.api.writeFile(tabKey, content)
      this.tabs[idx].saved = true
      this.tabs[idx].status = 'default'
    },

    async saveAllTabContent() {
      for (const tab of this.tabs) {
        if (tab.saved && tab.status === 'default') continue
        
        let content = tab.content
        if (typeof content === 'object') {
          content = JSON.stringify(
            toRaw(content)
          )
        }
        // console.log("Save content:", content)
        await window.api.writeFile(tab.tabKey, content)
        tab.saved = true
        tab.status = 'default'
      }
    }
  }
})