import { ipcMain } from 'electron'
import { initWS, waitForOpen } from '../ws/wsClient'
const WebSocket = require('ws')

import { AI_API_BASE, MEMORY_API_BASE, FILE_API_BASE } from '../config'

// =====================================================
//                      Ai chat
// =====================================================
export function registerAiIpc() {
  console.log('registerAiIpc...')
  ipcMain.handle('api:chat', async (event, cid, sid, hid, content, re_generate, chat_config) => {
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
          platform: 'default',
          messages: content,
          re_generate: re_generate,
          config: chat_config
        }
      })
    )

    // Renderer awaits this, real messages come via ws:message
    return true
  })

  ipcMain.handle('api:send_event', async (event, cid, action, ws_event) => {
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
        action: action,
        data: ws_event
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
          platform: 'default',
        }
      })
    )

    // Renderer awaits this, real messages come via ws:message
    return true
  })

  ipcMain.handle('api:new_chat', async (event, cid, workspace = "") => {
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
          workspace: workspace,
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
          workspace: new_info.workspace ?? null,
          is_pinned: new_info.star ?? null,
          is_deleted: new_info.deleted ?? null,
          has_new_message: new_info.has_new_message ?? null,
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

  ipcMain.handle('api:fetch_chat_messages', async (event, cid, sid, hid, branch_id) => {
    try {
      const res = await fetch(`${MEMORY_API_BASE}/memory/user/messages`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          client_id: cid,
          history_id: hid,
          current_node_id: branch_id
        }),
      })

      const data = await res.json()
      if (!res.ok) {
        throw new Error(data.detail || "Fetch conversation msgs failed.")
      }

      // console.log(data)

      let messages = data.messages
      const branches = data.branches
      messages = attachSiblingLinks(messages, branches)
      data.messages = messages

      return data
    } catch (err) {
      console.error("Fetch conversation msgs error:", err)
      throw err
    }
  })

  ipcMain.handle('api:delete_messages', async (event, cid, hid, node_ids) => {
    try {
      const res = await fetch(`${MEMORY_API_BASE}/memory/memory/delete_messages`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          client_id: cid,
          history_id: hid,
          messages: node_ids ?? []
        }),
      })

      const data = await res.json()
      if (!res.ok) {
        throw new Error(data.detail || "Delete messages failed.")
      }

      return data
    } catch (err) {
      console.error("Delete messages error:", err)
      throw err
    }
  })
}

function attachSiblingLinks(messages, branches) {
  if (!messages || !messages.length) return messages

  // 当前路径上的 node（更可靠）
  const activeNodeSet = new Set(messages.map(m => m.node_id))

  // node_id -> {pre_node, next_node}
  const nodeSiblingLinkMap = new Map()

  for (const parentId in branches) {
    const siblings = branches[parentId]

    if (!siblings || siblings.length <= 1) continue

    // 找当前路径命中的 child
    const activeNode = siblings.find(s => activeNodeSet.has(s.node_id))

    if (!activeNode) continue

    const idx = siblings.findIndex(s => s.node_id === activeNode.node_id)

    const pre = siblings.slice(0, idx).map(s => s.node_id)
    const next = siblings.slice(idx + 1).map(s => s.node_id)

    nodeSiblingLinkMap.set(activeNode.node_id, {
      pre_node: pre,
      next_node: next,
    })
  }

  // 挂到 message
  for (const msg of messages) {
    const link = nodeSiblingLinkMap.get(msg.node_id)

    if (link) {
      msg.pre_node = link.pre_node
      msg.next_node = link.next_node
    }
  }

  // console.log("Attac branch finish: ", messages)
  return messages
}