import {
  app,
  BrowserWindow
} from 'electron'
import { electronApp, optimizer } from '@electron-toolkit/utils'
import { initWS, closeWS } from './ws/wsClient'
import { isMac } from './app/constants'
import { createMainWindow } from './app/app'


// =====================================================
//                      App Events
// =====================================================
app.whenReady().then(() => {
  const root = process.cwd()
  console.warn("root is ", root)
  electronApp.setAppUserModelId('com.electron')

  app.on('browser-window-created', (_, window) => {
    optimizer.watchWindowShortcuts(window)
  })

  createMainWindow()

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createMainWindow()
  })
})

// Quit on all windows closed (except macOS)
app.on('window-all-closed', () => {
  if (!isMac) {
    closeWS()
    app.quit()
  }
})
