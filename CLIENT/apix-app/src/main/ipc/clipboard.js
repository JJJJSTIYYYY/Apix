import { ipcMain, clipboard, nativeImage } from 'electron'

import { AI_API_BASE, MEMORY_API_BASE, FILE_API_BASE } from '../config'

// =====================================================
//            Copy text / image to clipboard
// =====================================================
export function registerClipboardIpc() {
  console.log('registerClipboardIpc...')
  ipcMain.handle('api:copyToClipboard', (event, payload) => {
    try {
      if (payload.type === 'text') {
        clipboard.writeText(payload.data)
      } else if (payload.type === 'image') {
        const img = nativeImage.createFromDataURL(payload.data)
        clipboard.writeImage(img)
      }
      return true
    } catch (err) {
      console.error('copyToClipboard error:', err)
      return false
    }
  })
}