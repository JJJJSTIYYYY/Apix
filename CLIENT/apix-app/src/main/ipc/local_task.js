import { ipcMain, dialog, app } from 'electron'
import fs from 'fs'
import path from 'path'
import yaml from 'js-yaml'

const TEST_API_BASE = "http://127.0.0.1:5090"
import { AI_API_BASE, MEMORY_API_BASE, FILE_API_BASE } from '../config'

// =====================================================
//              Data write / read handlers
// =====================================================
export function registerLocalTaskIpc() {
    console.log('registerLocalTaskIpc...')
    const dataDir = path.join(app.getPath('userData'), 'ApiX')
    if (!fs.existsSync(dataDir)) fs.mkdirSync(dataDir, { recursive: true })
    console.log('Apix data dir:', dataDir)

    ipcMain.handle('readData', (event, key) => {
        const filePath = path.join(dataDir, `${key}.yaml`)
        if (!fs.existsSync(filePath)) return null

        const content = fs.readFileSync(filePath, 'utf-8').trim()
        return content ? yaml.load(content) : null
    })

    ipcMain.handle('writeData', (event, key, value) => {
        const filePath = path.join(dataDir, `${key}.yaml`)
        fs.writeFileSync(filePath, yaml.dump(value), 'utf-8')
        return true
    })

    ipcMain.handle('api:submit_case', async (event, cid, content) => {
        try {
        const res = await fetch(`${TEST_API_BASE}/plugin/submit_task`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                client_id: cid,
                content: content,
            }),
        })

        const data = await res.json()

        if (!res.ok) {
            throw new Error(data.detail || "Submit case list failed.")
        }

        return data.messages

        } catch (err) {
        console.error("[ipc:submit_case] error:", err)
        throw err
        }
    })
}