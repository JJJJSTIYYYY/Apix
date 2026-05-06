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
      else {
        console.log("before throw")
        throw new Error('登录失败: ' + res.messages)
      }
      loading.value = false
      return true
    } finally {
      loading.value = false
    }
    return false
  }

  /**
   * Register
   * Automatically log in after registration
   */
  const register = async (username, password) => {
    loading.value = true
    try {
      const res = await window.api.auth.register(username, password)
      console.log(res)
      if (res.success) {
        // Persist user immediately after registration
        persist({
          username,
          user_uid: res.messages.uid
        })
      }
      else {
        console.log("before throw")
        throw new Error('注册失败: ' + res.messages)
      }

      loading.value = false
      return true
    } finally {
      loading.value = false
    }
    return false
  }

  const ensure = async (user_uid) => {
    loading.value = true
    try {
      const res = await window.api.auth.ensure(user_uid)
      console.log(res)
      if (!res.success) {
        user.value = null
        localStorage.removeItem(STORAGE_KEY)
        console.warn("User ensure failed:", res.messages)
        loading.value = false
        return false
      }
      console.log("User ensure success:", res.messages)
      loading.value = false
      return true
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
    ensure,
  }
})
