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
    version: APIX.alpha
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, onMounted } from "vue"
import { useAuthStore } from "./store/auth"
import { useRouter } from "vue-router"
import { registerDynamicRoutes } from '@router/index'

const router = useRouter()
const authStore = useAuthStore()

onMounted(() => {
  registerDynamicRoutes()
  authStore.restore()

  if (authStore.user) {
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
      showToast(res)

      // Redirect to homepage after successful login
      if(!res.includes("登录失败")) router.replace("/home")
    } else {
      const res = await authStore.register(form.username, form.password)
      showToast(res)
      if(!res.includes("注册失败")) switchMode("login")
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
  align-items: flex-start;
  padding-top: 12%;
}

.glass-bg {
  min-height: 100vh;
  position: relative;
  overflow: hidden;

  background:
    /* warm soft light */
    radial-gradient(
      900px 700px at 15% 25%,
      rgba(254, 219, 233, 0.35),
      transparent 60%
    ),

    /* cool soft light */
    radial-gradient(
      1000px 800px at 85% 75%,
      rgba(209, 229, 255, 0.4),
      transparent 62%
    ),

    /* neutral base */
    linear-gradient(
      135deg,
      rgb(221, 251, 255),
      rgb(246, 226, 250)
    );
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
  background: rgba(255, 255, 255, 0.272);
  backdrop-filter: blur(16px);
  border-radius: 22px;
  border: 1px solid rgba(255, 255, 255, 0.4);
  box-shadow:
    0 8px 24px rgba(62, 67, 66, 0.128),
    inset 1px 1px 0 rgba(255, 255, 255, 0.662),
    inset -1px -1px 1px rgba(117, 187, 248, 0.083);
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
  transition: all 0.4s ease;
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
  background: rgba(226, 226, 226, 0.32);
  border-radius: 999px;
  border: 2px white;
  box-shadow:
    inset 1px -1px 16px rgba(117, 187, 248, 0.083);
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
  color: #0000009A;
  transition: color 0.25s ease;
}

.login-select:not(.right) {
  color: #4040409A;
  transition: color 0.25s ease;
}

.register-select {
  color: #0000009A;
  transition: color 0.25s ease;
}

.register-select.right {
  color: #4040409A;
  transition: color 0.25s ease;
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
    0 8px 24px rgba(62, 67, 66, 0.12);

  overflow: hidden;
  border: 1px solid color-mix(in srgb, #fff 10%, transparent);
  -webkit-backdrop-filter: saturate(500%) blur(16px);
  backdrop-filter: saturate(500%) blur(16px);
  -webkit-transition: all 0.3s cubic-bezier(0.215, 0.61, 0.355, 1);
  transition: all 0.3s cubic-bezier(0.215, 0.61, 0.355, 1);
  border-color: transparent;
  background-color: color-mix(in srgb, #ffffff 30%, transparent);
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
  color: #555;
}

.field input {
  height: 38px;
  padding: 0 12px;
  border-radius: 10px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  background: rgba(255, 255, 255, 0.8);
  font-size: 14px;
}

.field input:focus {
  outline: none;
  border-color: #7a9cff;
}

/* ================= Animations ================= */

.fade-slide-enter-active,
.fade-slide-leave-active {
  transition: all 0.25s ease;
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
  transition: all 0.3s ease;
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
  transition: all 0.25s ease;
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
  background-color: #ffffff70 !important;
  border: 1px solid rgba(0, 0, 0, 0.109);
}

.confirm-input.error {
  border: 1px solid red;
}

/* ================= Button ================= */

.submit-btn {
  height: 40px;
  margin-top: 12px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.69);
  cursor: pointer;
  font-size: 14px;
  color: white;
  background: linear-gradient(135deg, #4fd8c8cf, #4fd8c8cf);
  box-shadow:
    0 8px 24px rgba(62, 67, 66, 0.088);
  transition: all 0.23s ease;
}

.submit-btn:hover {
  transform: scale(1.03);
  background: linear-gradient(135deg, #4fd8c8cf, #4fd8c8cf);
  box-shadow:
    0 8px 24px rgba(40, 44, 43, 0.088);
}

.submit-btn:active {
  transform: scale(1.01);
  background: linear-gradient(135deg, #4fd8c8cf, #4fd8c8cf);
  box-shadow:
    0 8px 24px rgba(40, 44, 43, 0.088);
}

.submit-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.submit-btn.breathing {
  animation: breathe 1.4s ease-in-out infinite;
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

@keyframes breathe {
  0% { filter: brightness(1); }
  50% { filter: brightness(1.15); }
  100% { filter: brightness(1); }
}

.version-div {
  position: absolute;
  right: 10px;
  bottom: 6px;
  z-index: 9999;
  color: #00000077;
  font-size: 12px;
}

/* ================= Toast ================= */

.toast {
  position: fixed;
  bottom: 40px;
  left: 50%;
  transform: translateX(-50%);
  padding: 10px 18px;
  background: rgba(40, 40, 40, 0.8);
  color: white;
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
