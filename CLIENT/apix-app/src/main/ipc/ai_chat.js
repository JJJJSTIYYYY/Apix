import { ipcMain } from 'electron'
import { initWS, waitForOpen } from '../ws/wsClient'
const WebSocket = require('ws')

const MEMORY_API_BASE = "http://127.0.0.1:5093"
const TOOLS_API_BASE = "http://127.0.0.1:5092"
// =====================================================
//                      Ai chat
// =====================================================
export function registerAiIpc() {
  console.log('registerAiIpc...')
  ipcMain.handle('api:chat', async (event, cid, sid, hid, content, chat_config) => {
    // Ensure WS is connecting / connected
    let ws = initWS(cid)
    try {
      await waitForOpen(ws)
    } catch (err) {
      throw new Error('WebSocket not connected, please try again!')
    }

    if (!ws || ws.readyState !== WebSocket.OPEN) {
      throw new Error('WebSocket not connected, please try again!')
    }

    ws.send(
      JSON.stringify({
        action: 'chat_with_llm',
        data: {
          client_id: cid,
          session_id: sid,
          history_id: hid,
          messages: content,
          config: chat_config
        }
      })
    )

    // Renderer awaits this, real messages come via ws:message
    return true
  })

  ipcMain.handle('api:stop', async (event, cid, sid, hid) => {
    // Ensure WS is connecting / connected
    let ws = initWS(cid)
    try {
      await waitForOpen(ws)
    } catch (err) {
      throw new Error('WebSocket not connected, please try again!')
    }

    if (!ws || ws.readyState !== WebSocket.OPEN) {
      throw new Error('WebSocket not connected, please try again!')
    }

    ws.send(
      JSON.stringify({
        action: 'abort_generation',
        data: {
          client_id: cid,
          session_id: sid,
          history_id: hid,
        }
      })
    )

    // Renderer awaits this, real messages come via ws:message
    return true
  })

  ipcMain.handle('api:new_chat', async (event, cid) => {
    try {
      const res = await fetch(`${MEMORY_API_BASE}/memory/memory/conversation/create`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          client_id: cid,
          session_id: "",
          title: "新的聊天...",
        }),
      })

      const data = await res.json()
      if (!res.ok) {
        throw new Error(data.detail || "Create conversation failed.")
      }

      return data
    } catch (err) {
      console.error("Create conversation error:", err)
      throw err
    }
  })

  ipcMain.handle('api:update_conversation', async (event, cid, sid, hid, new_info) => {
    try {
      const res = await fetch(`${MEMORY_API_BASE}/memory/user/conversations/update`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          client_id: cid,
          session_id: sid,
          history_id: hid,
          title: new_info.title ?? null,
          is_pinned: new_info.star ?? null,
          is_deleted: new_info.deleted ?? null,
        }),
      })

      const data = await res.json()
      if (!res.ok) {
        throw new Error(data.detail || "Update conversation failed.")
      }

      return data
    } catch (err) {
      console.error("Update conversation error:", err)
      throw err
    }
  })

  ipcMain.handle('api:fetch_chat_list', async (event, cid) => {
    try {
      const res = await fetch(`${MEMORY_API_BASE}/memory/user/conversations/list`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          client_id: cid,
          session_id: "",
        }),
      })

      const data = await res.json()
      if (!res.ok) {
        throw new Error(data.detail || "Get conversation list failed.")
      }

      return data
    } catch (err) {
      console.error("Get conversation list error:", err)
      throw err
    }
  })

  ipcMain.handle('api:fetch_chat_messages', async (event, cid, sid, hid) => {
    try {
      const res = await fetch(`${MEMORY_API_BASE}/memory/user/messages`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          client_id: cid,
          history_id: hid,
        }),
      })

      const data = await res.json()
      if (!res.ok) {
        throw new Error(data.detail || "Fetch conversation msgs failed.")
      }

      return data
    } catch (err) {
      console.error("Fetch conversation msgs error:", err)
      throw err
    }
  })

  ipcMain.handle('api:start_task', async (event, tid) => {
    try {
      const res = await fetch(`${TOOLS_API_BASE}/task/start`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          task_id: tid,
        }),
      })

      const data = await res.json()
      if (!res.ok) {
        return "fail"
      }

      return data
    } catch (err) {
      console.error("Start task error:", err)
      throw err
    }
  })

  ipcMain.handle('api:kill_task', async (event, tname, tid, cid, hid) => {
    try {
      const res = await fetch(`${TOOLS_API_BASE}/task/kill`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          tool_name: tname,
          task_id: tid,
          client_id: cid,
          history_id: hid,
        }),
      })

      const data = await res.json()
      if (!res.ok) {
        throw new Error(data.detail || "Kill task failed.")
      }

      return data
    } catch (err) {
      console.error("Kill task error:", err)
      throw err
    }
  })

  ipcMain.handle('api:fetch_task_info', async (event, tid) => {
    try {
      const res = await fetch(`${MEMORY_API_BASE}/memory/task/info`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          task_id: tid,
          task_hash: "",
        }),
      })

      const data = await res.json()
      if (!res.ok) {
        throw new Error(data.detail || "Fetch task info failed.")
      }

      return data
    } catch (err) {
      console.error("Fetch task info error:", err)
      throw err
    }
  })
}