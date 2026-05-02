import { ipcMain, dialog, app, shell } from 'electron'
import fs from 'fs'
import path from 'path'
import os from 'os'

import { AI_API_BASE, TOOLS_API_BASE, MEMORY_API_BASE, FILE_API_BASE } from '../config'

// =====================================================
//              Data write / read handlers
// =====================================================
export function registerFileIpc() {
  console.log('registerFileIpc...')
  const dataDir = path.join(app.getPath('userData'), 'ApiX')
  if (!fs.existsSync(dataDir)) fs.mkdirSync(dataDir, { recursive: true })
  console.log('Apix data dir:', dataDir)

  ipcMain.handle('openFileDialog', async (event, type, extensions = []) => {
    let properties = []

    if (type === 'file') {
      properties = ['openFile']
    } else if (type === 'folder') {
      properties = ['openDirectory']
    } else {
      throw new Error(`Unknown dialog type: ${type}`)
    }

    const normalizedExtensions = Array.isArray(extensions)
      ? extensions
          .filter((ext) => typeof ext === 'string' && ext.trim() !== '')
          .map((ext) => ext.replace(/^\./, '').toLowerCase())
      : []

    const result = await dialog.showOpenDialog({
      title: 'APIX',
      properties,
      filters:
        type === 'file' && normalizedExtensions.length > 0
          ? [
              {
                name: 'Allowed Files',
                extensions: normalizedExtensions,
              },
            ]
          : [],
    })

    if (result.canceled || result.filePaths.length === 0) {
      return result
    }

    const selectedPath = result.filePaths[0]
    const stat = fs.statSync(selectedPath)

    if (type === 'file') {
      if (!stat.isFile()) {
        throw new Error('Please select a file.')
      }

      const ext = path.extname(selectedPath).slice(1).toLowerCase()

      if (normalizedExtensions.length > 0 && !normalizedExtensions.includes(ext)) {
        throw new Error(`Unsupported file type: .${ext}`)
      }
    } else if (!stat.isDirectory()) {
      throw new Error('Please select a folder.')
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
      const tempDir = path.join(os.tmpdir(), 'apix-temp')
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

  ipcMain.handle('createTempFileFromBase64', async (_, base64, fileName) => {
    try {
      // Create temp file path
      const tempDir = path.join(os.tmpdir(), 'apix-temp')
      if (!fs.existsSync(tempDir)) {
        fs.mkdirSync(tempDir, { recursive: true })
      }

      const filePath = path.join(tempDir, fileName)

      // Write base64 to file
      fs.writeFileSync(filePath, Buffer.from(base64, 'base64'))

      return filePath

    } catch (err) {
      console.error('createTempFileFromBase64 error:', err)

      return null
    }
  })

  ipcMain.handle('cleanTempDir', async (_, maxAgeMs = 24 * 60 * 60 * 1000) => {
    try {
      const tempDir = path.join(os.tmpdir(), 'apix-temp')

      // Ensure dir exists
      if (!fs.existsSync(tempDir)) {
        fs.mkdirSync(tempDir, { recursive: true })
        return { success: true, removed: 0 }
      }

      const files = fs.readdirSync(tempDir)
      let removedCount = 0

      for (const file of files) {
        const filePath = path.join(tempDir, file)

        try {
          const stat = fs.statSync(filePath)

          // Skip directories
          if (!stat.isFile()) continue

          // Check age
          const age = Date.now() - stat.mtimeMs

          if (age > maxAgeMs) {
            fs.unlinkSync(filePath)
            removedCount++
          }
        } catch (err) {
          console.warn('[cleanTempDir] skip:', filePath, err)
        }
      }

      return {
        success: true,
        removed: removedCount,
      }

    } catch (err) {
      console.error('[cleanTempDir] error:', err)
      return {
        success: false,
        error: String(err),
      }
    }
  })
}