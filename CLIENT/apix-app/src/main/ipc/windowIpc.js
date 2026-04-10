import { ipcMain, app } from 'electron'
import { isWin } from '../app/constants'

export function registerWindowIpc(win) {
  console.log('registerWindowIpc...')
  ipcMain.on('window-minimize', () => win.minimize())

  ipcMain.on('window-maximize', () => {
    win.isMaximized() ? win.unmaximize() : win.maximize()
  })

  ipcMain.on('window-close', () => {
    isWin ? win.close() : app.quit()
  })
}
