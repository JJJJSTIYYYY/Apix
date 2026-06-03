<template>
  <div class="app-wrapper">
    <el-config-provider :locale="lacale" :message="config">
      <div class="common-layout">
        <el-container class="root-container">
          <!-- 自定义标题栏 -->
          <el-header class="title-bar">
            <div class="window-controls">
              <button class="no-drag win-btn close-btn" type="danger" size="small" @click="close" >
              </button>
              <button class="no-drag win-btn minimize-btn" link size="small" @click="minimize">
              </button>
              <button class="no-drag win-btn maxmize-btn" link size="small" @click="maximize">
              </button>
            </div>
            <div class="drag-area">
              <button class="title no-drag" @click="showAppInfo">APIX</button>
            </div>
            <div class="left-icon no-drag">
              <img
                ref="apixIcon"
                class="icon"
                :src="appIcon"
                @click="playSpin"
              />
            </div>
          </el-header>

          <el-main class="main-window">
            <div v-show="!isResizing">
              <router-view v-slot="{ Component }">
                <keep-alive>
                  <component :is="Component" />
                </keep-alive>
              </router-view>
            </div>
          </el-main>
        </el-container>
      </div>
    </el-config-provider>
  </div>
</template>

<script setup lang="ts">
import { ref, getCurrentInstance, onMounted, onBeforeUnmount } from 'vue'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import { ConfirmDialog } from './views/component/comp/confirmDialog.js'
import { useAppCacheData } from './store/app.js';
import { apix_client_version } from './store/globalData.js';
import appIcon from './assets/background/APIX.png'

const lacale = zhCn
const config = ({
  max: 1
})
const { proxy } = getCurrentInstance()
const minimize = () => window.electron.ipcRenderer.send('window-minimize')
const maximize = () => window.electron.ipcRenderer.send('window-maximize')
async function close() {
  try {
    await ConfirmDialog.confirm(
      `确认要退出程序吗？未保存的数据将会丢失`,
      '关闭确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )
    window.electron.ipcRenderer.send('window-close')
  } catch {}
}
const store = useAppCacheData()
const apixIcon = ref<HTMLImageElement | null>(null)
function playSpin() {
  const el = apixIcon.value
  if (!el) {
    console.warn("el 为空")
    return
  }
  el.classList.remove('spin')
  void (el as HTMLElement).offsetWidth
  el.classList.add('spin')
  const handler = () => {
    el.classList.remove('spin')
    el.removeEventListener('animationend', handler)
  }
  el.addEventListener('animationend', handler)
}

async function showAppInfo() {
  await ConfirmDialog.confirm(
    '版本: ' + apix_client_version,
    '版本信息',
    {
      confirmButtonText: '确定',
      type: 'info',
    }
  )
}

const isResizing = ref(false)

let resizeTimer: ReturnType<typeof setTimeout> | null = null

function handleWindowResize() {
  isResizing.value = true

  if (resizeTimer) {
    clearTimeout(resizeTimer)
  }

  resizeTimer = setTimeout(() => {
    isResizing.value = false
    resizeTimer = null
  }, 150)
}

onMounted(() => {
  window.addEventListener('resize', handleWindowResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleWindowResize)

  if (resizeTimer) {
    clearTimeout(resizeTimer)
    resizeTimer = null
  }
})
</script>

<style scoped>
.app-wrapper {
  background-color: transparent;
}

.app-wrapper {
  position: relative;
  overflow: hidden;
}

.app-wrapper > * {
  position: relative;
  z-index: 1;
}

.top_window {
  padding: 0;
}

.common-layout {
  padding: 0;
}

.root-container {
  padding: 0;
}

.title-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  position: relative;
  height: 30px;
  padding: 0 8px;
  color: var(--apix-darkest-color);
  background-color: transparent;
  border-radius: var(--apix-border-radius-base) var(--apix-border-radius-base) 0 0;
  -webkit-app-region: drag;
}

.left-icon {
  display: flex;
  align-items: center;
  width: 20px;
  height: 20px;
}

.icon {
  cursor: pointer;
  display: inline-block;
  transform-origin: 50% 50%;
  width: 20px;
  height: 20px;
  border-radius: var(--apix-border-radius-base);
  object-fit: contain;
  overflow: hidden;
  opacity: 0.7;
  transition: opacity .25s var(--apix-cubic-bezier);
}

.icon:hover {
  opacity: 1;
}

.title {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
  font-weight: bold;
  font-size: 14px;
  padding-left: 5px;
  padding-right: 5px;
  color: var(--apix-darkest-color);
  background-color: transparent;
  height: 24px;
  border: none;
}

.drag-area {
  flex: 1;
  display: flex;
  align-items: center;
  border-radius: var(--apix-border-radius-base);
}

.window-controls {
  margin-left: 5px;
  display: flex;
  gap: 6px;
}

.no-drag {
  -webkit-app-region: no-drag; /* 按钮区域不可拖拽 */
  /* color: white; */
}

.win-btn {
  border-radius: 100%;
  padding: 0;
  width: 14px;
  height: 14px;
  border: none;
}

.maxmize-btn {
  background-color: var(--apix-success-color);
}

.minimize-btn {
  background-color: var(--apix-warning-color);
}

.close-btn {
  background-color: var(--apix-danger-color);
}

.maxmize-btn:hover {
  background-color: var(--apix-success-hover);
}

.minimize-btn:hover {
  background-color: var(--apix-warning-hover);
}

.close-btn:hover {
  background-color: var(--apix-danger-hover);
}

.main-window {
  background-color: transparent;
  padding: 0%;
  border-radius: var(--apix-border-radius-base);
  position: relative;
  min-height: calc(100vh - 30px);
  max-height: calc(100vh - 30px);
}

.icon {
  cursor: pointer;
  display: inline-block;
  transform-origin: 50% 50%;
}

/* 动画类 */
.spin {
  animation: spin-one 800ms cubic-bezier(0.4, 0, 0.2, 1);
}

@keyframes spin-one {
  from { transform: rotate(0deg); }
  to   { transform: rotate(360deg); }
}
</style>

