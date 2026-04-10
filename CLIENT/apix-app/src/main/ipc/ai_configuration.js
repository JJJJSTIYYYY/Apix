import { ipcMain } from 'electron'

const AI_API_BASE = "http://localhost:5091"
const FILE_API_BASE = "http://localhost:5094"
const MEMORY_API_BASE = "http://127.0.0.1:5093"
const TOOLS_API_BASE = "http://127.0.0.1:5092"
// =====================================================
//                      Ai config
// =====================================================
export function registerAiConfigIpc() {
  console.log('registerAiConfigIpc...')
  ipcMain.handle('api:get_models_list', async (event, model_provider, api_key) => {
    try {
      const res = await fetch(`${AI_API_BASE}/api/v1/get_models_list`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          model_provider: model_provider,
          api_key: api_key,
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

}