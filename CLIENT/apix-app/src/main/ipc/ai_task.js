import { ipcMain } from 'electron'

import { AI_API_BASE, MEMORY_API_BASE, FILE_API_BASE } from '../config'

// =====================================================
//                      Ai task
// =====================================================
export function registerAiTaskIpc() {
  console.log('registerAiTaskIpc...')
  ipcMain.handle('api:get_ai_task_list', async (event, clear) => {
    try {
      let api_port = ''
      if (clear) {
        api_port = 'clear_finished_tasks'
      }
      else {
        api_port = 'get_sub_agent_task_list'
      }
      const res = await fetch(`${AI_API_BASE}/api/v1/${api_port}`, {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
        },
      })

      const data = await res.json()

      if (!res.ok) {
        throw new Error(data.detail || "Get task list failed.")
      }

      if (!data.success) {
        throw new Error(data.messages || "Get task list failed.")
      }

      return data.messages

    } catch (err) {
      console.error("[ipc:get_ai_task_list] error:", err)
      throw err
    }
  })

  ipcMain.handle('api:stop_task', async (event, history_id, task_id) => {
    try {
      const res = await fetch(`${AI_API_BASE}/api/v1/stop_task`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          history_id: history_id,
          task_id: task_id,
        }),
      })

      const data = await res.json()

      if (!data.success) {
        throw new Error(data.messages || "Stop task failed.")
      }

      return data.messages

    } catch (err) {
      console.error("[ipc:stop_task] error:", err)
      throw err
    }
  })
}