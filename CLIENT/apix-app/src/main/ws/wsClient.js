import { BrowserWindow, ipcMain } from 'electron'
const WebSocket = require('ws')

import { WS_AI_API_BASE, AI_API_BASE, MEMORY_API_BASE, FILE_API_BASE } from '../config'

let ws = null

/* ------------------------
   WS reconnect state
------------------------- */
let reconnectTimer = null
let reconnectDelay = 1000 // initial delay (ms)
const MAX_RECONNECT_DELAY = 5000
let manuallyClosed = false

/* ------------------------
   WS subscribers
   key: webContents.id
   value: webContents
------------------------- */
const wsSubscribers = new Map()

/* =====================================================
   IPC: subscribe / unsubscribe WS messages
===================================================== */
ipcMain.on('ws:subscribe', (event) => {
  const wc = event.sender
  wsSubscribers.set(wc.id, wc)
})

ipcMain.on('ws:unsubscribe', (event) => {
  wsSubscribers.delete(event.sender.id)
})

/* =====================================================
   WebSocket
===================================================== */
export function initWS(clientId) {
  // Avoid duplicate connections
  if (ws) return ws

  manuallyClosed = false
  console.log('[WS] trying to connect...')

  ws = new WebSocket(`${WS_AI_API_BASE}/ws/default/${clientId}`)

  ws.on('open', () => {
    console.log('[WS] connected')

    // Reset reconnect state after successful connection
    reconnectDelay = 2000
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
  })

  ws.on('message', (data) => {
    let payload
    try {
      payload = JSON.parse(data.toString())
    } catch (err) {
      console.error('[WS] invalid json:', err)
      return
    }

    // Push message only to subscribed renderer processes
    for (const wc of wsSubscribers.values()) {
      if (!wc.isDestroyed()) {
        wc.send('ws:message', payload)
      }
    }
  })

  ws.on('close', () => {
    console.warn('[WS] closed')
    ws = null

    // Do not reconnect if closed manually
    if (manuallyClosed) return

    scheduleReconnect(clientId)
  })

  ws.on('error', (err) => {
    console.error('[WS] error:', err)

    // Some ws implementations won't emit close after error
    try {
      ws.close()
    } catch (_) {}
  })

  return ws
}

/* ------------------------
   Reconnect logic
------------------------- */
function scheduleReconnect(clientId) {
  if (reconnectTimer) return

  console.warn(`[WS] reconnecting in ${reconnectDelay}ms...`)

  reconnectTimer = setTimeout(() => {
    reconnectTimer = null
    initWS(clientId)

    // Exponential backoff with upper limit
    reconnectDelay = Math.min(
      reconnectDelay * 1.5,
      MAX_RECONNECT_DELAY
    )
  }, reconnectDelay)
}

/* ------------------------
   Manual WS close
------------------------- */
export function closeWS() {
  manuallyClosed = true

  if (reconnectTimer) {
    clearTimeout(reconnectTimer)
    reconnectTimer = null
  }

  if (ws) {
    ws.close()
    ws = null
  }

  // Clear all subscribers to avoid leaking stale webContents
  wsSubscribers.clear()
}

export function waitForOpen(ws, timeout = 5000) {
  return new Promise((resolve, reject) => {
    if (ws.readyState === WebSocket.OPEN) return resolve()
    const timer = setTimeout(() => reject(new Error('WebSocket open timeout')), timeout)
    ws.once('open', () => {
      clearTimeout(timer)
      resolve()
    })
    ws.once('close', () => {
      clearTimeout(timer)
      reject(new Error('WebSocket closed before open'))
    })
    ws.once('error', (err) => {
      clearTimeout(timer)
      reject(err)
    })
  })
}

export function registerWebsocketIpc() {
  console.log('registerWebsocketIpc...')
  ipcMain.handle('api:closeWebsocket', (event) => {
    try {
      closeWS()
      return true
    } catch (err) {
      console.error('closeWebsocket error:', err)
      return false
    }
  })
  ipcMain.handle('api:initWebsocket', (event, clientId) => {
    try {
      closeWS()
      initWS(clientId)
      return true
    } catch (err) {
      console.error('initWebsocket error:', err)
      return false
    }
  })
}
