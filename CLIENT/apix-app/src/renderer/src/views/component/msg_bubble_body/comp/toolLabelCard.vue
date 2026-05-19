<template>
  <div class="tool-chip" :class="`is-${status}`" @click="showTaskInfo">
    <!-- 状态指示器 -->
    <div class="status-indicator">
      <!-- 加载动画 -->
      <div v-if="status === 'in_progress'" class="loader">
        <div class="loader-ring"></div>
      </div>
      
      <!-- 状态图标 -->
      <svg v-else-if="status === 'completed'" class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
        <path d="M20 6L9 17l-5-5" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
      
      <svg v-else-if="status === 'pending'" class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="10"/>
        <path d="M12 6v6l4 2" stroke-linecap="round"/>
      </svg>
      
      <svg v-else-if="status === 'error'" class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
        <circle cx="12" cy="12" r="10"/>
        <path d="M15 9l-6 6M9 9l6 6" stroke-linecap="round"/>
      </svg>
      
      <svg v-else-if="status === 'outdated'" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="7533" width="200" height="200">
        <path d="M275.84 908.8c-32.64 0-65.28-12.16-90.24-37.12-24.32-24.32-37.12-56.32-37.12-90.24s13.44-65.92 37.12-90.24l96-96c10.88-10.88 14.72-26.88 10.24-40.96-39.04-119.04-8.32-248.32 80.64-337.28 72.32-72.32 172.8-106.88 274.56-94.08 33.28 3.84 60.16 26.24 71.04 57.6 10.88 31.36 3.2 65.92-20.48 89.6L548.48 418.56c-12.16 12.16-18.56 28.16-18.56 44.8s6.4 33.28 18.56 44.8c12.16 12.16 28.16 18.56 44.8 18.56s33.28-6.4 44.8-18.56L787.2 359.68c23.68-23.68 58.24-31.36 89.6-20.48 31.36 10.88 53.76 37.76 57.6 71.04 12.8 101.76-21.76 202.24-94.08 274.56-88.32 88.96-217.6 119.68-337.28 80.64-14.08-4.48-30.08-0.64-40.96 10.24l-96 96c-24.96 24.96-57.6 37.12-90.24 37.12zM605.44 183.68c-70.4 0-137.6 27.52-188.16 78.08-71.04 71.68-96 176-64.64 272 12.16 37.12 2.56 78.08-25.6 106.24l-96 96c-24.96 24.96-24.96 65.28 0 90.24 24.96 24.96 65.28 24.96 90.24 0l96-96c28.16-28.16 69.12-38.4 106.24-25.6 96 31.36 200.32 6.4 272-64.64 58.24-58.24 86.4-139.52 76.16-221.44-1.28-12.16-10.88-17.28-14.72-18.56-3.84-1.28-14.72-3.84-23.68 5.12l-149.12 149.12c-24.32 24.32-56.32 37.12-90.24 37.12s-65.92-13.44-90.24-37.12c-24.32-24.32-37.12-56.32-37.12-90.24s13.44-65.92 37.12-90.24L652.8 224.64c8.96-8.96 7.04-19.84 5.12-23.68-1.28-3.84-5.76-13.44-18.56-14.72-11.52-1.28-22.4-2.56-33.92-2.56z" fill="#818181" p-id="7534"></path>
      </svg>
    </div>

    <!-- 内容区 -->
    <span class="content">{{ tool_name }}</span>
  </div>

  <taskInfoView
    v-if="ifShowTaskInfo"
    :task-info="obj"
    @close="ifShowTaskInfo=false"
  />
</template>

<script setup lang="ts">
import { ref } from 'vue'
import TaskInfoView from './taskInfoView.vue'

const props = defineProps<{
  tool_name: string
  tool_call_id: string
  content: object
  status: 'pending' | 'in_progress' | 'completed' | 'error' | 'outdated'
  obj?: object
}>()



const ifShowTaskInfo = ref(false)
const showTaskInfo = () => {
  if (props.obj) {
    ifShowTaskInfo.value = true
    return
  }
}
</script>

<style scoped>
.tool-chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  
  border-radius: 4px;
  font-size: 13px;
  font-weight: 600;
  line-height: 1.4;
  padding: 0px 1px;
  
  /* 透明背景 + 细边框 */
  background: transparent;
  box-shadow: none;
  
  cursor: default;
}

.tool-chip:hover {
  background: var(--apix-default-light-color);
}

/* Pending */
.tool-chip.is-pending {
  color: #78716c;
  border-color: rgba(120, 113, 108, 0.2);
}

/* In Progress */
.tool-chip.is-in_progress {
  color: #2563eb;
  border-color: rgba(37, 99, 235, 0.25);
  background: rgba(167, 188, 233, 0.04);
}

/* Completed */
.tool-chip.is-completed {
  color: var(--apix-success-color);
  border-color: var(--apix-success-color);
}

/* Error */
.tool-chip.is-error {
  color: var(--apix-danger-color);
  border-color: var(--apix-danger-color);
  background: color-mix(in srgb, var(--apix-danger-color) 20%, transparent);
}

/* Outdated */
.tool-chip.is-outdated {
  color: #78716c;
  border-color: rgba(120, 113, 108, 0.2);
  font-style: italic;
  opacity: 0.7;
}

/* ===== 状态指示器 ===== */
.status-indicator {
  width: 16px;
  height: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  position: relative;
}

.icon {
  width: 14px;
  height: 14px;
  display: block;
}

/* 加载动画 */
.loader {
  width: 14px;
  height: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.loader-ring {
  width: 100%;
  height: 100%;
  border: 2px solid currentColor;
  border-radius: 50%;
  border-top-color: transparent;
  animation: spin 0.8s linear infinite;
  box-sizing: border-box;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* ===== 内容区 ===== */
.content {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}

/* In Progress 状态下的脉冲效果 */
.tool-chip.is-in_progress .status-indicator::before {
  content: '';
  position: absolute;
  top: 50%;
  left: 50%;
  width: 22px;
  height: 22px;
  transform: translate(-50%, -50%);
  border-radius: 50%;
  background: currentColor;
  opacity: 0.15;
  animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}

@keyframes pulse {
  0%, 100% { transform: translate(-50%, -50%) scale(1); opacity: 0.15; }
  50% { transform: translate(-50%, -50%) scale(1.3); opacity: 0; }
}

/* 完成状态的勾选动画 */
.tool-chip.is-completed .icon {
  animation: check-in 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

@keyframes check-in {
  0% { transform: scale(0) rotate(-45deg); }
  50% { transform: scale(1.2) rotate(0deg); }
  100% { transform: scale(1) rotate(0deg); }
}

/* 错误状态的抖动提示 */
.tool-chip.is-error {
  animation: shake 0.5s cubic-bezier(0.36, 0.07, 0.19, 0.97) both;
}

@keyframes shake {
  10%, 90% { transform: translateX(-1px); }
  20%, 80% { transform: translateX(2px); }
  30%, 50%, 70% { transform: translateX(-2px); }
  40%, 60% { transform: translateX(2px); }
}
</style>