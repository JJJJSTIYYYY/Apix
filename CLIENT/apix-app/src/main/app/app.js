import {
  shell,
  BrowserWindow
} from 'electron'
import { join } from 'path'
import { is } from '@electron-toolkit/utils'
import { registerWindowIpc } from '../ipc/windowIpc'
import { isMac, isWin } from '../app/constants'
import { registerFileIpc } from '../ipc/file'
import { registerAiIpc } from '../ipc/ai_chat'
import { registerClipboardIpc } from '../ipc/clipboard'
import icon from '../../../resources/APIX.png'
import { registerLogreIpc } from '../ipc/login_register'
import { registerWebsocketIpc } from '../ws/wsClient'
import { registerAiConfigIpc } from '../ipc/ai_configuration'
import { registerAiFilesIpc } from '../ipc/ai_files'
import { registerAiTaskIpc } from '../ipc/ai_task'
import { registerLocalTaskIpc } from '../ipc/local_task'

// ---------- Windows Mica Support ----------
let MicaBrowserWindow = null
if (isWin) {
  try {
    ;({ MicaBrowserWindow } = require('mica-electron'))
  } catch (e) {
    console.log('Failed to load mica-electron:', e)
  }
}

// ---------- Common window options ----------
const baseWindowOptions = {
  width: 1570,
  height: 970,
  minWidth: 1570,
  minHeight: 970,
  show: false,
  autoHideMenuBar: true,
  icon: icon,
  webPreferences: {
    preload: join(__dirname, '../preload/index.js'),
    // nodeIntegration: true,
    // contextIsolation: false,
    sandbox: false,
    contextIsolation: true,
    nodeIntegration: false,
    webSecurity: true
  }
}

// ---------- macOS window options ----------
const macWindowOptions = {
  ...baseWindowOptions,
  frame: false,
  transparent: true,
  vibrancy: 'popover',
  visualEffectState: 'active'
}

// ---------- Windows Mica window options ----------
const winMicaOptions = {
  ...baseWindowOptions,
  frame: false,
  resizable: true,
  transparent: false
}

// ---------- Linux fallback window options ----------
const linuxWindowOptions = {
  ...baseWindowOptions
}

export function createAppWindow() {
  let mainWindow

  if (isMac) {
    mainWindow = new BrowserWindow(macWindowOptions)
  } else if (isWin && MicaBrowserWindow) {
    mainWindow = new MicaBrowserWindow(winMicaOptions)
  } else {
    mainWindow = new BrowserWindow(linuxWindowOptions)
  }

  return mainWindow
}




// =====================================================
//                   Create Window
// =====================================================
export function createMainWindow() {
  let mainWindow = createAppWindow()

  // ---------- Window event bindings ----------
  registerWindowIpc(mainWindow)
  registerFileIpc(mainWindow)
  registerLocalTaskIpc()
  registerAiIpc()
  registerAiConfigIpc()
  registerAiFilesIpc()
  registerAiTaskIpc()
  registerClipboardIpc()
  registerLogreIpc()
  registerWebsocketIpc()


  // =====================================================
  //                   Window Ready
  // =====================================================
  mainWindow.on('ready-to-show', () => {
    if (isWin && typeof mainWindow.setMicaEffect === 'function') {
      mainWindow.setMicaEffect()
      mainWindow.setRoundedCorner?.()
      mainWindow.setMicaTabbedEffect?.()
      mainWindow.setMicaAcrylicEffect?.()
    }
    mainWindow.show()
  })

  // Intercept new window (target="_blank")
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url)
    return { action: 'deny' }
  })

  // Intercept in-app navigation 生产环境解除注释以下代码
  // mainWindow.webContents.on('will-navigate', (event, url) => {
  //   event.preventDefault()
  //   shell.openExternal(url)
  // })

  // ---------- Load renderer ----------
  if (is.dev && process.env['ELECTRON_RENDERER_URL']) {
    mainWindow.loadURL(process.env['ELECTRON_RENDERER_URL'])
  } else {
    mainWindow.loadFile(join(__dirname, '../renderer/index.html'))
  }

  return mainWindow
}