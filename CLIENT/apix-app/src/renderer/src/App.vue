<template>
  <div class="app-wrapper" :style="{
    background: `
      linear-gradient(
        rgba(${255*(store.config.lightValue / 100)}, ${255*(store.config.lightValue / 100)}, ${255*(store.config.lightValue / 100)}, ${store.config.transparencyValue / 100}),
        rgba(${255*(store.config.lightValue / 100)}, ${255*(store.config.lightValue / 100)}, ${255*(store.config.lightValue / 100)}, ${store.config.transparencyValue / 100})
      ),
      url('${store.config.backgroundImage}')
    `,
    backgroundSize: 'cover',
    backgroundPosition: 'center',
    backgroundRepeat: 'no-repeat'
  }">
    <el-config-provider :locale="lacale" :message="config">
      <div class="common-layout">
        <el-container class="root-container">
          <!-- 自定义标题栏 -->
          <el-header class="title-bar" height="30px">
            <div class="left-icon no-drag">
              <svg
                ref="apixIcon"
                class="icon"
                @click="playSpin"
                t="1757926419635"
                viewBox="0 0 1024 1024"
                xmlns="http://www.w3.org/2000/svg"
                width="256" height="256"
              >
                <path d="M48.8448 44.4928m382.5152 0l169.7792 0q382.5152 0 382.5152 382.5152l0 169.7792q0 382.5152-382.5152 382.5152l-169.7792 0q-382.5152 0-382.5152-382.5152l0-169.7792q0-382.5152 382.5152-382.5152Z" fill="#EDEDED" p-id="1184"></path><path d="M509.7472 501.6064m-250.3168 0a250.3168 250.3168 0 1 0 500.6336 0 250.3168 250.3168 0 1 0-500.6336 0Z" fill="#B7B7AE" p-id="1185"></path><path d="M497.92 464.5888m-197.8368 0a197.8368 197.8368 0 1 0 395.6736 0 197.8368 197.8368 0 1 0-395.6736 0Z" fill="#CECECE" p-id="1186"></path><path d="M469.1456 425.7792m-116.5312 0a116.5312 116.5312 0 1 0 233.0624 0 116.5312 116.5312 0 1 0-233.0624 0Z" fill="#EAEAEA" p-id="1187"></path><path d="M510.72 768.512c-6.912 0-13.8752 0-20.8384-0.8192A266.5984 266.5984 0 0 1 431.872 247.0912a16.2816 16.2816 0 1 1 9.5744 31.0784 234.0864 234.0864 0 1 0 291.1744 297.3696 16.2816 16.2816 0 0 1 30.72 10.24 265.9328 265.9328 0 0 1-252.6208 182.7328z" fill="#434A54" p-id="1188"></path><path d="M558.848 256v207.36h198.2976A250.5216 250.5216 0 0 0 558.848 256z" fill="#5AB3FF" p-id="1189"></path><path d="M568.32 284.0576l-10.24 179.6608 134.8608 1.0752A191.7952 191.7952 0 0 0 568.32 284.0576z" fill="#7BD3FF" p-id="1190"></path><path d="M757.1456 479.6416h-198.2976A16.2816 16.2816 0 0 1 542.72 463.36V256a16.384 16.384 0 0 1 5.9392-12.5952 16.1792 16.1792 0 0 1 13.5168-3.3792A266.9568 266.9568 0 0 1 773.12 460.8a16.2816 16.2816 0 0 1-16.0768 18.7904z m-182.016-32.5632H737.28a234.752 234.752 0 0 0-162.2528-170.24z" fill="#434A54" p-id="1191"></path>
              </svg>
            </div>
            <div class="drag-area">
              <el-button class="title no-drag" @click="showAppInfo">APIX</el-button>
            </div>
            <div class="window-controls">
              <div class="window-show">
                <el-button class="no-drag win-btn minimize-btn" link size="small" @click="minimize">
                  <el-icon><Minus /></el-icon>
                </el-button>
                <el-button class="no-drag win-btn maxmize-btn" link size="small" @click="maximize">
                  <el-icon><FullScreen /></el-icon>
                </el-button>
              </div>
              <div style="width: 2px;"></div>
              <el-button class="no-drag win-btn close-btn" type="danger" size="small" @click="close" >
                <el-icon><Close /></el-icon>
              </el-button>
            </div>
          </el-header>

          <el-main class="main-window">
            <router-view></router-view>
          </el-main>
        </el-container>
      </div>
    </el-config-provider>
  </div>
</template>

<script setup lang="ts">
import { ref, getCurrentInstance } from 'vue'
// import { ElConfigProvider, ElContainer, ElHeader, ElMain, ElButton } from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import { ConfirmDialog } from './views/component/comp/confirmDialog.js'
import { useAppCacheData } from './store/app.js';

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
      `确认要退出程序吗？所有会话已经保存`,
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
const apixIcon = ref<SVGSVGElement | null>(null)
function playSpin() {
  const el = apixIcon.value
  if (!el) {
    console.warn("el 为空")
    return
  }
  el.classList.remove('spin')
  // 强制回流以重触发 CSS 动画
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
    '版本: beta',
    '版本信息',
    {
      confirmButtonText: '确定',
      type: 'info',
    }
  )
}

</script>

<style scoped>
.app-wrapper {
  background-color: rgba(0, 0, 0, 0);
}

.app-wrapper {
  position: relative;
  overflow: hidden;
}

/* 点阵背景层 */
.app-wrapper::before {
  content: "";
  position: absolute;
  inset: 0;
  z-index: 0;

  /* === 点阵参数 === */
  --dot-size: 1px;     /* 点大小 */
  --dot-gap: 24px;     /* 点间距 */
  --dot-color: rgba(119, 166, 157, 0.041);

  background-image:
    radial-gradient(
      circle,
      var(--dot-color) var(--dot-size),
      transparent calc(var(--dot-size) + 1px)
    );

  background-size: var(--dot-gap) var(--dot-gap);
  background-position: center;

  pointer-events: none; /* 不影响点击 / 拖拽 */
}

/* 确保内容在点阵之上 */
.app-wrapper > * {
  position: relative;
  z-index: 1;
}

.top_window {
  padding: 0%;
}

.common-layout {
  padding: 0%;
}

.root-container {
  padding: 0%;
}

.title-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  position: relative;
  height: 30px;
  padding: 0 8px;
  color: rgb(129, 129, 129);
  background-color: rgb(135, 223, 211);

  /* 左下角圆角取消 */
  border-radius: 5px 5px 0 0; /* 左上 右上 左下 右下 */ 

  /* 可拖拽 */
  -webkit-app-region: drag;
}

.left-icon {
  display: flex;
  align-items: center;
  margin-left: -3px;
  width: 20px;
  height: 20px;
}

.title {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
  font-weight: bold;
  font-size: 12px;
  padding-left: 5px;
  padding-right: 5px;
  color: rgba(255, 255, 255, 0.88);
  background-color: rgba(138, 186, 191, 0.539);
  border-radius: 5px;
  height: 24px;
  border: none;
}

.title:hover {
  background-color: rgba(113, 132, 133, 0.496);
}

.title:active {
  background-color: rgba(95, 158, 160, 0.496);
  border: none;
}

.drag-area {
  flex: 1;
  display: flex;
  align-items: center;
  border-radius: 5px;
}

.window-controls {
  margin-right: -4px;
}

.window-controls {
  display: flex;
}

.no-drag {
  -webkit-app-region: no-drag; /* 按钮区域不可拖拽 */
  /* color: white; */
}

.win-btn .el-icon {
  font-size: 14px;   /* 放大一点 */
  font-weight: bold; /* 粗化 */
  stroke-width: 2.5; /* Element Plus 图标支持 stroke-width 调整线条粗细 */
  margin-left: 0;
}

.window-show{
  display: grid;
  grid-template-columns: 50% 50%;
  height: 24px;
  width: 48px;
  border-radius: 6px;
  background-color: rgba(95, 158, 160, 0.539);
  margin: 0px;
}

.maxmize-btn{
  width: 24px;
  color: white;
}

.minimize-btn{
  width: 24px;
  color: white;
}

.el-button+.el-button{
  margin: 0;
}

.close-btn {
  height: 24px;
  width: 24px;
  border-radius: 6px;
}

.main-window {
  /* background-color: #ecf0f1; */
  padding: 0%;
  border-radius: 5px;
  position: relative;
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

<style>
html, body {
  overflow: hidden;
  margin: 0px;
  background: 
    linear-gradient(
      180deg,
      #ffffff8d,
      #f6f6f68d
    );
}

body, * {
  user-select: none;
  -webkit-user-select: none; /* Chromium 内核 */
  --n-tab-border-color: rgb(247, 247, 250);
  --el-input-focus-border: #02decc8d;
  --n-tab-text-color-active: #0061508d;
  --n-tab-text-color: #0918158d;
  --el-menu-border-color: none;
}

:root {
  --el-border-radius-base: 8px;
}

</style>

