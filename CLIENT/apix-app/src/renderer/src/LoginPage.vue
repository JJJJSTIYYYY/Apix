<template>
  <div class="glass-bg flex-center app-enter">
    <Transition name="card-float" appear>
      <div class="glass-card auth-card">
        <!-- Mode switch -->
        <div class="mode-switch">
          <div class="slider" :class="{ right: !isLogin }" />
          <button @click="switchMode('login')" class="login-select" :class="{ right: !isLogin }">Login</button>
          <button @click="switchMode('register')" class="register-select" :class="{ right: !isLogin }">Register</button>
        </div>

        <!-- Title -->
        <Transition name="fade-slide" mode="out-in">
          <h2 class="title" :class="{ right: !isLogin }" :key="titleText">
            {{ titleText }}
          </h2>
        </Transition>

        <!-- Form -->
        <Transition name="form-switch" mode="out-in">
          <form :key="mode" class="auth-form" @submit.prevent="onSubmit">
            <div class="field">
              <label>- Username</label>
              <input
                class="info-input"
                v-model="form.username"
                type="text"
                autocomplete="username"
              />
            </div>

            <div class="field">
              <label>- Password</label> 
              <input
                class="info-input"
                v-model="form.password"
                type="password"
                autocomplete="current-password"
              />
            </div>

            <Transition name="expand-fade">
              <div v-if="!isLogin" class="field">
                <label>- Confirm Password</label>
                <input
                  class="info-input confirm-input"
                   :class="{ error: !validate_pass }" 
                  v-model="form.confirmPassword"
                  type="password"
                  autocomplete="new-password"
                />
              </div>
            </Transition>

            <button
              class="submit-btn"
              :class="{ breathing: loading }"
              :disabled="loading"
            >
              {{ submitText }}
            </button>

            <button
              class="forget-btn"
              :class="{ breathing: loading }"
              :disabled="loading"
              v-if="isLogin"
            >
              Forgot Password?
            </button>
          </form>
        </Transition>
      </div>
    </Transition>

    <!-- Toast -->
    <div v-if="toast.show" class="toast">
      {{ toast.message }}
    </div>
  </div>

  <div
    class="version-div"
  >
    APIX {{ apix_client_version }}
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, onMounted } from "vue"
import { useAuthStore } from "./store/auth"
import { useRouter } from "vue-router"
import { registerDynamicRoutes } from '@router/index'
import { apix_client_version } from './store/globalData'

const router = useRouter()
const authStore = useAuthStore()

onMounted(async () => {
  registerDynamicRoutes()
  authStore.restore()

  if (authStore.user && await authStore.ensure(authStore.user.user_uid)) {
    // Already logged in → skip login page
    router.replace("/home")
  }
})


/**
 * Page mode
 */
const mode = ref("login") // login | register
const loading = computed(() => authStore.loading)

/**
 * Form data
 */
const form = reactive({
  username: "",
  password: "",
  confirmPassword: "",
})

/**
 * Toast
 */
const toast = reactive({
  show: false,
  message: "",
})

const isLogin = computed(() => mode.value === "login")
const titleText = computed(() => (isLogin.value ? "Sign In" : "Create Account"))
const submitText = computed(() => (isLogin.value ? "Login" : "Register"))

/**
 * Toast helper
 */
const showToast = (msg) => {
  toast.message = msg
  toast.show = true
  console.log("start show")
  setTimeout(() => {
    toast.show = false
  }, 3000)
}

/**
 * Switch login / register
 */
const switchMode = (target) => {
  if (mode.value === target) return
  mode.value = target

  // Clear sensitive fields
  form.password = ""
  form.confirmPassword = ""
}

/**
 * Password validation (register only)
 */
const validate_pass = ref(true)

watch(
  () => form.confirmPassword,
  (val) => {
    if (isLogin.value || !val) {
      validate_pass.value = true
      return
    }
    validate_pass.value = val === form.password
  }
)

watch(
  () => form.password,
  (val) => {
    if (isLogin.value || !form.confirmPassword) {
      validate_pass.value = true
      return
    }
    validate_pass.value = val === form.confirmPassword
  }
)

/**
 * Form validation
 */
const validate = () => {
  if (!form.username || !form.password) {
    showToast("Username and password required")
    return false
  }

  if (!isLogin.value && form.password !== form.confirmPassword) {
    showToast("Passwords do not match")
    return false
  }

  return true
}

/**
 * Submit handler
 */
const onSubmit = async () => {
  if (loading.value) return
  if (!validate()) return

  try {
    if (isLogin.value) {
      const res = await authStore.login(form.username, form.password)

      // Redirect to homepage after successful login
      if(res) {
        showToast("登陆成功")
        router.replace("/home")
      }
    } else {
      const res = await authStore.register(form.username, form.password)
      showToast(res)
      if(res) {
        showToast("注册成功")
        switchMode("login")
      }
    }
  } catch (e) {
    showToast(e?.message || "Operation failed")
  }
}

</script>


<style scoped>
/* ================= Layout ================= */

.flex-center {
  display: flex;
  justify-content: center;
  align-items: center;
}

.glass-bg {
  height: calc(100vh - 30px);
  position: relative;
  overflow: hidden;
  /* overflow: visible; */

  background: transparent;
}


.app-enter {
  animation: appFadeIn 0.35s ease forwards;
}

@keyframes appFadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

/* ================= Card ================= */

.glass-card {
  background: var(--apix-panel-layer-1-background);
  backdrop-filter: blur(16px);
  border-radius: 22px;
  box-shadow: var(--apix-shadow-layer-2);
}

.auth-card {
  width: 330px;
  padding: 32px;
  height: 400px;
  overflow: hidden;
  will-change: transform;
}

/* Card float */
.card-float-enter-active {
  transition: opacity 0.4s var(--apix-cubic-bezier),
    transform 0.4s var(--apix-cubic-bezier);
}

.card-float-enter-from {
  opacity: 0;
  transform: translateY(16px) scale(0.98);
}

/* ================= Mode Switch ================= */

.mode-switch {
  position: relative;
  display: flex;
  margin-bottom: 22px;
  background: var(--apix-default-light-color);
  border-radius: 999px;
  box-shadow:
    inset 1px -1px 16px var(--apix-default-light-color);
}

.mode-switch button {
  flex: 1;
  height: 36px;
  border: none;
  background-color: transparent;
  cursor: pointer;
  z-index: 1;
  font-size: 14px;
}

.login-select {
  color: var(--apix-default-dark-color);
  transition: color 0.25s var(--apix-cubic-bezier);
}

.login-select:not(.right) {
  color: var(--apix-darkest-color);
  transition: color 0.25s var(--apix-cubic-bezier);
}

.register-select {
  color: var(--apix-default-dark-color);
  transition: color 0.25s var(--apix-cubic-bezier);
}

.register-select.right {
  color: var(--apix-darkest-color);
  transition: color 0.25s var(--apix-cubic-bezier);
}

.slider {
  position: absolute;
  margin-top: -6px;
  top: 2px;
  left: 2px;

  width: calc(50% + 8px);
  height: calc(100% + 7px);

  border-radius: 32px;

  /* Movement */
  transform: translateX(-3%);

  /* Stable physical shadow (never changes) */
  box-shadow:
    0 8px 24px var(--apix-default-light-color);

  overflow: hidden;
  border: none;
  backdrop-filter: saturate(500%) blur(16px);
  transition: all 0.3s var(--apix-cubic-bezier);
  border-color: transparent;
  background-color: color-mix(in srgb, var(--apix-lightest-color) 30%, transparent);
}

.mode-switch:active:deep(.slider) {
  transform: scale(1.2);
}

/* ===== Right state ===== */

.slider.right {
  transform: translateX(90%);
}

/* Flip highlight direction */
.slider.right::before {
  transform: scaleX(-1);
}

/* Drift refraction to simulate background bending */
.slider.right::after {
  transform: translateX(25%);
}


/* ================= Form ================= */
.title {
  color: var(--apix-darkest-color);
}

.title:not(.right) {
  margin-top: 40px;
}


.auth-form {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.field label {
  font-size: 13px;
  color: var(--apix-secondary-dark-color);
}

.field input {
  height: 38px;
  padding: 0 12px;
  border-radius: 10px;
  border: 1px solid var(--apix-secondary-light-color);
  background: var(--apix-default-light-color);
  font-size: 14px;
}

.field input:focus {
  outline: none;
  border-color: var(--apix-primary-hover);
}

/* ================= Animations ================= */

.fade-slide-enter-active,
.fade-slide-leave-active {
  transition: transform 0.25s ease,
    opacity 0.25s ease;
}

.fade-slide-enter-from {
  opacity: 0;
  transform: translateY(6px);
}

.fade-slide-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}

.form-switch-enter-active,
.form-switch-leave-active {
  transition: transform 0.3s ease,
    opacity 0.3s ease;
}

.form-switch-enter-from {
  opacity: 0;
  transform: translateY(10px);
}

.form-switch-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}

.expand-fade-enter-active,
.expand-fade-leave-active {
  transition: transform 0.3s ease,
    opacity 0.3s ease;
}

.expand-fade-enter-from,
.expand-fade-leave-to {
  opacity: 0;
  max-height: 0;
}

.expand-fade-enter-to,
.expand-fade-leave-from {
  opacity: 1;
  max-height: 80px;
}

/* ================= Input ================= */

.info-input {
  height: 40px;
  margin-top: 4px;
  background-color: var(--apix-default-light-color) !important;
  border: 1px solid var(--apix-secondary-light-color);
  color: var(--apix-default-dark-color);
}

.confirm-input.error {
  border: 1px solid var(--apix-danger-color);
}

/* ================= Button ================= */

.submit-btn {
  height: 40px;
  margin-top: 12px;
  border-radius: 999px;
  border: none;
  cursor: pointer;
  font-size: 14px;
  color: var(--apix-lightest-color);
  background: var(--apix-primary-color);
  box-shadow: var(--apix-shadow-layer-1);
  transition: transform 0.23s var(--apix-cubic-bezier),
    background 0.23s var(--apix-cubic-bezier),
    box-shadow 0.23s var(--apix-cubic-bezier);
}

.submit-btn:hover {
  transform: scale(1.03);
  background: var(--apix-primary-hover);
  box-shadow: var(--apix-shadow-layer-3);
}

.submit-btn:active {
  transform: scale(1.01);
  background: var(--apix-primary-active);
  box-shadow: var(--apix-shadow-layer-2);
}

.submit-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.forget-btn {
  height: 18px;
  width: fit-content;
  margin-top: 12px;
  border: none;
  cursor: pointer;
  font-size: 12px;
  align-self: center;
  color: rgba(138, 192, 194, 0.665);
  background: transparent;
}

.forget-btn:hover {
  border-bottom: 1px solid rgba(132, 205, 232, 0.665);
  color: rgba(67, 205, 210, 0.875);
}

.version-div {
  width: 100px;
  height: 32px;
  position: absolute;
  right: 10px;
  bottom: 6px;
  z-index: 9999;
  color: var(--apix-default-dark-color);
  font-size: 12px;
}

/* ================= Toast ================= */

.toast {
  position: fixed;
  bottom: 40px;
  left: 50%;
  transform: translateX(-50%);
  padding: 10px 18px;
  background: var(--apix-default-dark-color);
  color: var(--apix-lightest-color);
  border-radius: 20px;
  font-size: 13px;
  animation: toastIn 0.3s ease;
}

@keyframes toastIn {
  from {
    opacity: 0;
    transform: translateX(-50%) translateY(6px);
  }
  to {
    opacity: 1;
    transform: translateX(-50%) translateY(0);
  }
}
</style>
