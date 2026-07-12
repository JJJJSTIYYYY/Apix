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

  ipcMain.handle('api:create_cron_task', async (event, cid, cron_meta) => {
    try {
      const res = await fetch(`${MEMORY_API_BASE}/cron/create_cron_task`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          client_id: cid,
          ...cron_meta,
        }),
      })

      const data = await res.json()

      if (!data.success) {
        throw new Error(data.messages || "Create cron task failed.")
      }

      const tid = data.messages.task_id
      const repeat = cron_meta.repeat
      const exec_time = cron_meta.exec_time
      const res_2 = await fetch(`${AI_API_BASE}/api/v1/sync_cron/${tid}/${repeat}/${exec_time.replace(' ', 'T')}`, {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
        },
      })

      const data_2 = await res_2.json()

      if (!data_2.success) {
        throw new Error(data_2.messages || "Failed to sync cron tasks.")
      }

      return data.messages // {"task_id": "xxx"}

    } catch (err) {
      console.error("[ipc:create_cron_task] error:", err)
      throw err
    }
  })

  ipcMain.handle('api:get_cron_task_list', async (event, cid) => {
    try {
      const res = await fetch(`${MEMORY_API_BASE}/cron/get_cron_tasks`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          client_id: cid,
        }),
      })

      const data = await res.json()

      if (!data.success) {
        throw new Error(data.messages || "Get cron tasks failed.")
      }

      return data.messages

    } catch (err) {
      console.error("[ipc:get_cron_tasks] error:", err)
      throw err
    }
  })

  ipcMain.handle('api:update_cron_task', async (event, tid, repeat, exec_time, new_info) => {
    try {
      const res = await fetch(`${MEMORY_API_BASE}/cron/update_cron_task`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          task_id: tid,
          ...new_info,
        }),
      })

      const data = await res.json()

      if (!data.success) {
        throw new Error(data.messages || "Update cron task failed.")
      }

      if (exec_time !== "") {
        const res_2 = await fetch(`${AI_API_BASE}/api/v1/sync_cron/${tid}/${repeat}/${exec_time.replace(' ', 'T')}`, {
          method: "GET",
          headers: {
            "Content-Type": "application/json",
          },
        })

        const data_2 = await res_2.json()

        if (!data_2.success) {
          throw new Error(data_2.messages || "Failed to sync cron tasks.")
        }
      }

      return data.messages

    } catch (err) {
      console.error("[ipc:update_cron_task] error:", err)
      throw err
    }
  })
}