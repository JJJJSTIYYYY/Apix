import { ipcMain } from 'electron'
import fs from 'fs'
import axios from 'axios'
import FormData from 'form-data'

import { AI_API_BASE, MEMORY_API_BASE, FILE_API_BASE } from '../config'

// =====================================================
//                      Ai config
// =====================================================
export function registerAiFilesIpc() {
  console.log('registerAiFiles...')

  /**
   * Get embedding model list
   * JSON request
   */
  ipcMain.handle('api:get_embed_list', async (event, model_provider, api_key) => {
    try {
      const resp = await axios.post(
        `${FILE_API_BASE}/file/info/get_models_list`,
        {
          model_provider,
          api_key,
        },
        {
          headers: {
            'Content-Type': 'application/json',
          },
        }
      )

      return resp.data.messages
    } catch (err) {
      console.error("[ipc:get_models_list] error:", err)
      throw err
    }
  })

  /**
   * Upload files (multipart/form-data)
   */
  ipcMain.handle('api:upload_files', async (event, cid, files) => {
    try {
      const form = new FormData()

      // Form field
      form.append('client_id', cid)

      // Files: same field name MUST be "files"
      for (const file of files) {
        const stat = fs.statSync(file.path)

        // Skip directories
        if (!stat.isFile()) {
          console.warn('[upload_files] skip non-file:', file.path)
          continue
        }

        form.append(
          'files',
          fs.createReadStream(file.path),
          file.name
        )
      }

      const resp = await axios.post(
        `${FILE_API_BASE}/file/file/insert_file`,
        form,
        {
          headers: {
            ...form.getHeaders(),
          },
          // Important for large files
          maxBodyLength: Infinity,
          maxContentLength: Infinity,
        }
      )
      
      if (resp.data.success !== true) {
        throw new Error(resp.data.messages)
      }
      return resp.data
    } catch (err) {
      console.error("[ipc:upload_files] error:", err)
      throw err
    }
  })

  /**
   * Upload skill zip (multipart/form-data)
   */
  ipcMain.handle('api:upload_skills', async (event, cid, files) => {
    try {
      const form = new FormData()

      // Form field
      form.append('client_id', cid)

      // Files: same field name MUST be "files"
      for (const file of files) {
        form.append(
          'files',
          fs.createReadStream(file.path),
          file.name
        )
      }

      const resp = await axios.post(
        `${FILE_API_BASE}/file/skills/insert_skills`,
        form,
        {
          headers: {
            ...form.getHeaders(),
          },
          // Important for large files
          maxBodyLength: Infinity,
          maxContentLength: Infinity,
        }
      )
      
      if (resp.data.success !== true) {
        throw new Error(resp.data.messages)
      }
      return resp.data
    } catch (err) {
      console.error("[ipc:upload_skills] error:", err)
      throw err
    }
  })

  ipcMain.handle('api:get_available_skills', async (event, cid, limit) => {
    try {
      const resp = await axios.post(
        `${FILE_API_BASE}/file/skills/get_available_skills`,
        {
          client_id: cid,
          limit,
        },
        {
          headers: {
            'Content-Type': 'application/json',
          },
        }
      )
      
      if (resp.data.success !== true) {
        throw new Error(resp.data.messages)
      }
      return resp.data.messages
    } catch (err) {
      console.error("[ipc:get_available_skills] error:", err)
      throw err
    }
  })

  ipcMain.handle('api:update_skill_status', async (event, cid, skill_id, active) => {
    try {
      const resp = await axios.post(
        `${FILE_API_BASE}/file/skills/update_skill`,
        {
          client_id: cid,
          skill_id,
          is_active: active
        },
        {
          headers: {
            'Content-Type': 'application/json',
          },
        }
      )
      
      if (resp.data.success !== true) {
        throw new Error(resp.data.messages)
      }
      return resp.data.messages
    } catch (err) {
      console.error("[ipc:update_skill_status] error:", err)
      throw err
    }
  })

  ipcMain.handle('api:delete_skill', async (event, cid, skill_id) => {
    try {
      const resp = await axios.post(
        `${FILE_API_BASE}/file/skills/update_skill`,
        {
          client_id: cid,
          skill_id,
          deleted: true
        },
        {
          headers: {
            'Content-Type': 'application/json',
          },
        }
      )
      
      if (resp.data.success !== true) {
        throw new Error(resp.data.messages)
      }
      return resp.data.messages
    } catch (err) {
      console.error("[ipc:delete_skill] error:", err)
      throw err
    }
  })

  /**
   * Upload rag documents (multipart/form-data)
   */
  ipcMain.handle('api:upload_documents', async (event, cid, files) => {
    try {
      const form = new FormData()

      // Form field
      form.append('client_id', cid)

      // Files: same field name MUST be "files"
      for (const file of files) {
        form.append(
          'files',
          fs.createReadStream(file.path),
          file.name
        )
      }

      const resp = await axios.post(
        `${FILE_API_BASE}/file/rag/insert_document`,
        form,
        {
          headers: {
            ...form.getHeaders(),
          },
          // Important for large files
          maxBodyLength: Infinity,
          maxContentLength: Infinity,
        }
      )
      
      if (resp.data.success !== true) {
        throw new Error(resp.data.messages)
      }
      return resp.data
    } catch (err) {
      console.error("[ipc:upload_documents] error:", err)
      throw err
    }
  })

  ipcMain.handle('api:update_document_status', async (event, cid, document_id, active) => {
    try {
      const resp = await axios.post(
        `${FILE_API_BASE}/file/rag/update_document`,
        {
          client_id: cid,
          document_id,
          is_active: active
        },
        {
          headers: {
            'Content-Type': 'application/json',
          },
        }
      )
      
      if (resp.data.success !== true) {
        throw new Error(resp.data.messages)
      }
      return resp.data.messages
    } catch (err) {
      console.error("[ipc:update_document_status] error:", err)
      throw err
    }
  })

  ipcMain.handle('api:update_document_description', async (event, cid, document_id, description) => {
    try {
      const resp = await axios.post(
        `${FILE_API_BASE}/file/rag/update_document`,
        {
          client_id: cid,
          document_id,
          description
        },
        {
          headers: {
            'Content-Type': 'application/json',
          },
        }
      )
      
      if (resp.data.success !== true) {
        throw new Error(resp.data.messages)
      }
      return resp.data.messages
    } catch (err) {
      console.error("[ipc:update_document_description] error:", err)
      throw err
    }
  })

  ipcMain.handle('api:delete_document', async (event, cid, document_id) => {
    try {
      const resp = await axios.post(
        `${FILE_API_BASE}/file/rag/update_document`,
        {
          client_id: cid,
          document_id,
          deleted: true
        },
        {
          headers: {
            'Content-Type': 'application/json',
          },
        }
      )
      
      if (resp.data.success !== true) {
        throw new Error(resp.data.messages)
      }
      return resp.data.messages
    } catch (err) {
      console.error("[ipc:delete_document] error:", err)
      throw err
    }
  })

  ipcMain.handle('api:get_available_documents', async (event, cid, limit) => {
    try {
      const resp = await axios.post(
        `${FILE_API_BASE}/file/rag/get_available_documents`,
        {
          client_id: cid,
          limit,
        },
        {
          headers: {
            'Content-Type': 'application/json',
          },
        }
      )
      
      if (resp.data.success !== true) {
        throw new Error(resp.data.messages)
      }
      return resp.data.messages
    } catch (err) {
      console.error("[ipc:get_available_documents] error:", err)
      throw err
    }
  })

  ipcMain.handle('api:embed_document', async (event, cid, document_id, model) => {
    try {
      const resp = await axios.post(
        `${FILE_API_BASE}/file/rag/embed_document`,
        {
          client_id: cid,
          document_id,
          selected_embed_model: model
        },
        {
          headers: {
            'Content-Type': 'application/json',
          },
        }
      )
      
      if (resp.data.success !== true) {
        throw new Error(resp.data.messages)
      }
      return resp.data.messages
    } catch (err) {
      console.error("[ipc:embed_document] error:", err)
      throw err
    }
  })

  ipcMain.handle('api:load_resource', async (event, cid, fileId) => {
    try {
      const resp = await axios.get(
        `${FILE_API_BASE}/file/file/load_resource`,
        {
          params: {
            file_id: fileId,
            client_id: cid,
          },
          responseType: 'arraybuffer',
        }
      )

      return {
        ok: true,
        fileId,
        clientId: cid,
        contentType: resp.headers['content-type'] || 'application/octet-stream',
        contentDisposition: resp.headers['content-disposition'] || '',
        etag: resp.headers['etag'] || '',
        sha256: resp.headers['x-file-sha256'] || '',
        buffer: Buffer.from(resp.data).toString('base64'),
      }
    } catch (err) {
      console.error("[ipc:load_resource] error:", err?.message || err)

      const status = err?.response?.status || 500
      const detail = err?.response?.data || err?.message || 'load resource failed'

      return {
        ok: false,
        status,
        detail,
      }
    }
  })
}
 