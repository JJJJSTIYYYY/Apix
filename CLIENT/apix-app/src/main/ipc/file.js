import { ipcMain, dialog, app, shell } from 'electron'
import fs from 'fs'
import path from 'path'
import os from 'os'

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

  ipcMain.handle('openCacheDir', async () => {
    try {
      // Get user data directory and append custom folder
      const dataDir = path.join(app.getPath('userData'), 'ApiX')

      // Ensure directory exists
      if (!fs.existsSync(dataDir)) {
        fs.mkdirSync(dataDir, { recursive: true })
      }

      console.log('Apix data dir:', dataDir)

      // Open directory in system file explorer (cross-platform)
      const err = await shell.openPath(dataDir)

      // shell.openPath returns empty string on success
      if (err) {
        console.error('Failed to open directory:', err)
        return { success: false, error: err }
      }

      return { success: true, path: dataDir }
    } catch (e) {
      console.error('openCacheDir error:', e)
      return { success: false, error: String(e) }
    }
  })

  ipcMain.handle('openImageTemp', async (_, base64, fileName) => {
    try {
      // Create temp file path
      const tempDir = path.join(os.tmpdir(), 'apix-images')
      if (!fs.existsSync(tempDir)) {
        fs.mkdirSync(tempDir, { recursive: true })
      }

      const filePath = path.join(tempDir, fileName)

      // Write base64 to file
      fs.writeFileSync(filePath, Buffer.from(base64, 'base64'))

      // Open with system default image viewer
      await shell.openPath(filePath)

      return { success: true, path: filePath }
    } catch (err) {
      console.error('openImageTemp error:', err)
      return { success: false, error: String(err) }
    }
  })
}