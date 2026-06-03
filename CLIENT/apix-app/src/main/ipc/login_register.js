// main/ipc/login_register.js
import { ipcMain } from "electron"
import crypto from "crypto"

import { AI_API_BASE, MEMORY_API_BASE, FILE_API_BASE } from '../config'

// AES-128-CBC config must match server
const AES_KEY = Buffer.from("0123456789abcdef")
const AES_IV = Buffer.from("abcdef9876543210")

/**
 * Encrypt plain password using AES-CBC
 * Output is base64 encoded string
 */
function encryptPassword(password) {
  const cipher = crypto.createCipheriv("aes-128-cbc", AES_KEY, AES_IV)
  let encrypted = cipher.update(password, "utf8", "base64")
  encrypted += cipher.final("base64")
  return encrypted
}

/**
 * Register auth IPC handlers
 */
export function registerLogreIpc() {
  console.log("registerLogreIpc...")

  /**
   * Login handler
   */
  ipcMain.handle("auth:login", async (_, payload) => {
    try {
      const res = await fetch(`${MEMORY_API_BASE}/auth/login`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          username: payload.username,
          password: encryptPassword(payload.password),
        }),
      })

      const data = await res.json()
      if (!res.ok) {
        throw new Error(data.messages?.msg || "Login failed")
      }

      return data
    } catch (err) {
      console.error("Login error:", err)
      throw err
    }
  })

  /**
   * Register handler
   */
  ipcMain.handle("auth:register", async (_, payload) => {
    try {
      const res = await fetch(`${MEMORY_API_BASE}/auth/register`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          username: payload.username,
          password: encryptPassword(payload.password),
        }),
      })

      const data = await res.json()
      if (!res.ok) {
        throw new Error(data.detail || "Register failed")
      }

      return data
    } catch (err) {
      console.error("Register error:", err)
      throw err
    }
  })

  /**
   * Ensuer user handler
   */
  ipcMain.handle("auth:ensure_user", async (_, client_id) => {
    try {
      const res = await fetch(`${MEMORY_API_BASE}/auth/ensure_user`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          client_id: client_id
        }),
      })

      const data = await res.json()
      if (!res.ok) {
        throw new Error(data.detail || "Ensure failed")
      }

      return data
    } catch (err) {
      console.error("Ensure error:", err)
      throw err
    }
  })
}
