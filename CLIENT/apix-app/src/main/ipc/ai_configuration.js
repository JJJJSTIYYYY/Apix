import { ipcMain } from 'electron'

import { AI_API_BASE, TOOLS_API_BASE, MEMORY_API_BASE, FILE_API_BASE } from '../config'

// =====================================================
//                      Ai config
// =====================================================
export function registerAiConfigIpc() {
  console.log('registerAiConfigIpc...')
  ipcMain.handle('api:get_models_list', async (event, model_provider, api_key, config) => {
    try {
      const res = await fetch(`${AI_API_BASE}/api/v1/get_models_list`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          model_provider: model_provider,
          api_key: api_key,
          config: config
        }),
      })

      const data = await res.json()

      if (!res.ok) {
        throw new Error(data.detail || "Get models list failed.")
      }

      return data.messages

    } catch (err) {
      console.error("[ipc:get_models_list] error:", err)
      throw err
    }
  })

  ipcMain.handle('api:set_proxy', async (event, http_proxy, https_proxy, no_proxy) => {
    try {
      const res = await fetch(`${AI_API_BASE}/api/v1/set_proxy`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          http_proxy: http_proxy,
          https_proxy: https_proxy,
          no_proxy: no_proxy,
        }),
      })

      const data = await res.json()

      if (!res.ok) {
        throw new Error(data.detail || "Set proxy failed.")
      }

      return data.messages

    } catch (err) {
      console.error("[ipc:set_proxy] error:", err)
      throw err
    }
  })

  ipcMain.handle('api:clear_vision_cache', async (event) => {
    try {
      const res = await fetch(`${AI_API_BASE}/api/v1/clear_vision_cache`, {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
        }
      })

      const data = await res.json()

      if (!res.ok) {
        throw new Error(data.detail || "Clear cache failed.")
      }
      if (!data.success) {
        throw new Error(data.messages || "Clear cache failed.")
      }

      return data.messages

    } catch (err) {
      console.error("[ipc:clear_vision_cache] error:", err)
      throw err
    }
  })

  ipcMain.handle('api:create_llm_provider', async (event, cid, provider_meta) => {
    try {
      const res = await fetch(`${MEMORY_API_BASE}/provider/create_llm_provider`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          client_id: cid,
          ...provider_meta
        }),
      })

      const data = await res.json()

      if (!res.ok || !data.success) {
        throw new Error(data.detail || data.messages || "Create providers failed.")
      }

      return data.messages

    } catch (err) {
      console.error("[ipc:create_llm_provider] error:", err)
      throw err
    }
  })

  ipcMain.handle('api:get_llm_providers', async (event, cid) => {
    try {
      const res = await fetch(`${MEMORY_API_BASE}/provider/get_llm_providers`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          client_id: cid
        }),
      })

      const data = await res.json()

      if (!res.ok || !data.success) {
        throw new Error(data.detail || data.messages || "Get providers failed.")
      }

      return data.messages

    } catch (err) {
      console.error("[ipc:get_llm_providers] error:", err)
      throw err
    }
  })

  ipcMain.handle('api:update_llm_provider', async (event, provider_id, cid, new_meta) => {
    try {
      const res = await fetch(`${MEMORY_API_BASE}/provider/update_llm_provider`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          provider_id: provider_id,
          client_id: cid,
          ...new_meta
        }),
      })

      const data = await res.json()

      if (!res.ok || !data.success) {
        throw new Error(data.detail || data.messages || "Update providers failed.")
      }

      return data.messages

    } catch (err) {
      console.error("[ipc:update_llm_provider] error:", err)
      throw err
    }
  })

ipcMain.handle('api:auto_fetch_model_list', async (event, endpoint, api_key) => {
  try {
    const base = endpoint.replace(/\/+$/, '')
    const url = `${base}/models`

    const res = await fetch(url, {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
        ...(api_key ? { Authorization: `Bearer ${api_key}` } : {})
      },
    })

    const data = await res.json()

    if (!res.ok) {
      throw new Error(
        data?.error?.message ||
        data?.detail ||
        "Fetch models failed."
      )
    }

    let models = []

    if (Array.isArray(data)) {
      models = data
    } else if (Array.isArray(data.data)) {
      models = data.data
    } else if (Array.isArray(data.models)) {
      models = data.models
    } else {
      throw new Error("Unexpected response format.")
    }

    const ids = models
      .map((m) => m?.id || m?.name)
      .filter((id) => typeof id === "string" && id.length > 0)

    return ids

  } catch (err) {
    console.error("[ipc:auto_fetch_model_list] error:", err)
    throw err
  }
})

}