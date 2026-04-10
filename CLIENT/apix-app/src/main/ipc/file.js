import { ipcMain, dialog, app } from 'electron'
import fs from 'fs'
import path from 'path'
import yaml from 'js-yaml'

const MAX_FILE_SIZE = 5 * 1024 * 1024 // 5 MB

// =====================================================
//              Data write / read handlers
// =====================================================
export function registerFileIpc() {
  console.log('registerFileIpc...')
  const dataDir = path.join(app.getPath('userData'), 'ApiX')
  if (!fs.existsSync(dataDir)) fs.mkdirSync(dataDir, { recursive: true })
  console.log('Apix data dir:', dataDir)

  ipcMain.handle('openFileDialog', async () => {
    const result = await dialog.showOpenDialog({
      title: '选择文件',
      properties: ['openFile', 'openDirectory'],
    })

    if (result.canceled || result.filePaths.length === 0) {
      return result
    }

    const filePath = result.filePaths[0]

    const stat = fs.statSync(filePath)

    if (stat.size > MAX_FILE_SIZE) {
      throw new Error('File size exceeds 5MB limit.')
    }

    return result
  })
}