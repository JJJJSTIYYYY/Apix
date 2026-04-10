// main/ipc/login_register.js
import { ipcMain } from "electron"
import crypto from "crypto"

const API_BASE = "http://127.0.0.1:8000"

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
      const res = await fetch(`${API_BASE}/auth/login`, {
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
      const res = await fetch(`${API_BASE}/auth/register`, {
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
}
