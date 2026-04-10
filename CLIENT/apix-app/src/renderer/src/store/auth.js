// store/auth.js
import { defineStore } from "pinia"
import { ref } from "vue"

const STORAGE_KEY = "apix-auth-user"

export const useAuthStore = defineStore("auth", () => {
  const loading = ref(false)
  const user = ref(null) // { username, user_uid }

  /**
   * Restore login state from localStorage
   */
  const restore = () => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY)
      if (raw) {
        user.value = JSON.parse(raw)
      }
    } catch (e) {
      console.warn("restore auth failed:", e)
      localStorage.removeItem(STORAGE_KEY)
    }
  }

  /**
   * Persist login state
   */
  const persist = (userData) => {
    user.value = userData
    localStorage.setItem(STORAGE_KEY, JSON.stringify(userData))
  }

  /**
   * Clear login state
   */
  const logout = () => {
    user.value = null
    localStorage.removeItem(STORAGE_KEY)
  }

  /**
   * Login
   */
  const login = async (username, password) => {
    loading.value = true
    try {
      const res = await window.api.auth.login(username, password)

      if (res.success) {
        // Use the UID returned from backend
        persist({
          username,
          user_uid: res.messages.uid
        })
        window.api.initWebsocket(res.messages.uid)
      }

      return res.messages.msg
    } finally {
      loading.value = false
    }
  }

  /**
   * Register
   * Automatically log in after registration
   */
  const register = async (username, password) => {
    loading.value = true
    try {
      const res = await window.api.auth.register(username, password)

      if (res.success) {
        // Persist user immediately after registration
        persist({
          username,
          user_uid: res.messages.uid
        })
      }

      return res.messages.msg
    } finally {
      loading.value = false
    }
  }

  return {
    loading,
    user,
    login,
    register,
    restore,
    logout,
  }
})
