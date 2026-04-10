<template>
  <transition name="bubble-scale">
    <div
      class="tool-card selectable"
      :class="{ running: msg.status === 'running', done: msg.status === 'done', fail: (msg.status === 'failed' || msg.status === 'manual stopped'), pending: msg.status === 'pending' }"
      @contextmenu.prevent="onContextMenu"
      @mouseup="showTaskInfo($event)"
    >
      <div v-if="msg.status === 'running'" class="shine"></div>

      <div class="card-body">
        <!-- Left icon -->
        <div class="card-icon">
          🛠️
        </div>

        <!-- Right content -->
        <div class="card-content">
          <!-- Title -->
          <div class="task-title">
            {{ msg.content }}
          </div>

          <!-- Status -->
          <div
            class="task-status"
            :class="{ running: msg.status === 'running', done: msg.status === 'done', fail: msg.status === 'failed' || msg.status === 'manual stopped', pending: msg.status === 'pending' }"
          >
            {{ taskStatus }}
          </div>

          <!-- Description -->
          <div v-if="msg.desc" class="task-desc">
            {{ msg.desc }}
          </div>
        </div>
      </div>

      <!-- Footer -->
      <div class="task-footer">
        Task ID: {{ msg.id }}
      </div>
      <div
        class="run-btn"
        :class="{ isRunning: msg.status === 'running', fail: msg.status === 'failed' || msg.status === 'manual stopped', pending: msg.status === 'pending' }"
        role="button"
        tabindex="0"
        @click="runTask"
        @keydown.enter.prevent="runTask"
        @keydown.space.prevent="runTask"
        @mousedown.prevent
        @mouseup.prevent
      >
        <!-- Loading -->
        <div
          v-if="msg.status === 'running'"
          class="arc-spinner smooth"
        ></div>
        <!-- Idle -->
        <el-icon
          v-else
          class="play-icon"
        >
          <CaretRight />
        </el-icon>
      </div>
    </div>
  </transition>

  <taskInfoView
    class="task-info-view"
    v-if="ifShowTaskInfo"
    :task-info="taskInfo"
    @close="ifShowTaskInfo=false"
  />
</template>


<script setup lang="ts">
import { ref, watchEffect } from 'vue'
import taskInfoView from './comp/taskInfoView.vue'
import { ConfirmDialog } from '../comp/confirmDialog.js'
import { ElMessage } from 'element-plus'

// ------------------------
// 参数类型
// ------------------------
type msgBubData = {
  id: string
  cid: string
  hid: string
  role: 'tools' | 'system'
  content: string      // task title
  desc?: string        // task description
  status?: 'pending' | 'running' | 'done' | 'failed' | 'manual stopped'     // task status
}

const props = defineProps<{
  msg: msgBubData
}>()

// ------------------------
// Task status
// ------------------------
// Local mutable state
const TASK_STATUS = {
  'pending': 'Pending',
  'running': 'Running',
  'done': 'Done',
  'failed': 'Failed',
  'manual stopped': 'Manual stopped',
}
const taskStatus = ref('Unsigned status')

// Sync from props (props change -> local state update)
watchEffect(() => {
  console.log("status: ", props.msg.status)
  taskStatus.value = TASK_STATUS[props.msg.status] || 'Unsigned status';
})

// ------------------------
// 查看任务详情
// ------------------------
const ifShowTaskInfo = ref(false)
const taskInfo = ref(null)
const showTaskInfo = async (event: MouseEvent) => {
  // If click target is inside run button, ignore
  const target = event.target as HTMLElement
  if (target?.closest('.run-btn')) {
    return
  }

  console.log("Query task: ", props.msg.id)
  
  if (taskInfo.value) {
    ifShowTaskInfo.value = true
    return
  }
  try {
    const res = await window.api.getTaskInfo(
      props.msg.id
    )
    if (!res.messages || Object.keys(res.messages).length === 0)
      ElMessage({ type: 'error', message: '未查询到任务结果', plain: true, })
    else {
      console.log("Get task info: ", res)
      taskInfo.value = res
      ifShowTaskInfo.value = true
    }
  } catch (err) {
    ElMessage({ type: 'error', message: '任务数据拉取失败', plain: true, })
    ifShowTaskInfo.value = false
  }
}

// ------------------------
// 运行按钮
// ------------------------
const runTask = async () => {
  console.log('Submit run task: ', props.msg.id)

  if (taskStatus.value === 'Running') {
    // Manually update local state
    try {
      await ConfirmDialog.confirm(
        `确定要终止任务 "${props.msg.id}" 吗？\n终止后需从头开始运行.`,
        '终止确认',
        {
          confirmButtonText: '确定',
          cancelButtonText: '取消',
          type: 'warning',
        }
      )
      try {
        await window.api.killTask(
          props.msg.content,
          props.msg.id,
          props.msg.cid,
          props.msg.hid,
        )
        props.msg.status = 'manual stopped'
        ElMessage({ type: 'success', message: '已终止', plain: true, })
      } catch (err) {
        ElMessage({ type: 'error', message: '任务数据拉取失败', plain: true, })
        ifShowTaskInfo.value = false
      }
    } catch (err) {
      console.error("tool msg bubble: runTask error:", err)
    }
  }
  else {
    try {
      const res = await window.api.startTask(
        props.msg.id
      )
      if (res !== "fail") {
        props.msg.status = 'running'
        ElMessage({ type: 'success', message: '开始运行', plain: true, })
      }
      else {
        ElMessage({ type: 'error', message: '任务已过期', plain: true, })
      }
    } catch (err) {
      ElMessage({ type: 'error', message: '任务数据拉取失败', plain: true, })
      ifShowTaskInfo.value = false
    }
  }

}
</script>


<style scoped>
/* ------------------------
   气泡进入动画
------------------------- */
.bubble-scale-enter-from {
  transform: scale(0.8);
  opacity: 0;
}
.bubble-scale-enter-active {
  transition: all 0.3s cubic-bezier(0.25, 0.1, 0.25, 1.0);
}

/* ------------------------
   气泡本体（修复 shine & 文本过渡）
------------------------- */
.tool-card {

  position: relative;
  overflow: hidden;

  min-width: 290px;
  max-width: 290px;
  padding: 12px 16px;
  border-radius: 12px;
  line-height: 1.6;
  box-shadow: 0 2px 6px rgba(0,0,0,0.1);
  background: rgba(255, 255, 255, 0.652);
  color: rgba(0, 0, 0, 0.657);

  transition: all 0.25s ease;
}

.tool-card:hover {
  transform: scale(1.04);
  box-shadow:
    0 10px 26px rgba(0, 59, 48, 0.066),
    0 2px 6px rgba(0, 142, 135, 0.03);
}

.tool-card:active:not(:has(.run-btn:active)) {
  transform: scale(1);
  box-shadow:
    0 10px 26px rgba(23, 47, 43, 0.163),
    0 2px 6px rgba(0, 142, 135, 0.061);
}

.tool-card.running {
  border: solid #ee9f01e0;
  border-width: 1.5px 1.5px 1.5px 3px;
}

.tool-card.done {
  border: solid #0a9211bb;
  border-width: 1.5px 1.5px 1.5px 3px;
}

.tool-card.fail {
  border: solid #ff2600bb;
  border-width: 1.5px 1.5px 1.5px 3px;
}

.tool-card.pending {
  border: solid #3d3d3dbb;
  border-width: 1.5px 1.5px 1.5px 3px;
}

/* pending 状态下（占位骨架） */
.tool-card:has(.shine) {
  padding: 10px 14px;
  opacity: 0.8;
}

/* ------------------------
   Card layout
------------------------- */
.card-body {
  display: flex;
  gap: 12px;
}

.card-icon {
  font-size: 20px;
  line-height: 1;
  margin-top: 2px;
  opacity: 0.85;
}

.card-content {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

/* ------------------------
   Task content hierarchy
------------------------- */
.task-title {
  font-size: 15px;
  font-weight: 600;
  color: rgba(0, 0, 0, 0.85);
}

.task-status {
  font-size: 13px;
  font-weight: 500;
}

.task-status.running {
  color: #d18b00;
}

.task-status.done {
  color: #2e7d32;
}

.task-status.fail {
  color: #ff3714;
}

.task-status.pending {
  color: #606060;
}

.task-desc {
  font-size: 12px;
  opacity: 0.7;
  max-height: 1.4em;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
}

/* ------------------------
   Footer
------------------------- */
.task-footer {
  margin-top: 8px;
  font-size: 11px;
  opacity: 0.45;
}


/* ------------------------
   Shine 动画（修复位置和大小）
------------------------- */
.shine {
  position: absolute;
  top: 0;
  left: -100%;
  width: 80%;
  height: 100%;
  background: linear-gradient(
    120deg,
    transparent,
    rgb(255, 255, 255),
    transparent
  );
  animation: shining 1.3s infinite;
}
@keyframes shining {
  0% { left: -100%; }
  100% { left: 120%; }
}

/* ------------------------
   菜单动画
------------------------- */
.scale-fade-enter-active {
  animation: scaleFadeIn .25s cubic-bezier(0.22, 1, 0.36, 1);
}
.scale-fade-leave-active {
  animation: scaleFadeOut .2s cubic-bezier(0.4, 0, 0.2, 1);
}
@keyframes scaleFadeIn {
  0% { opacity: 0; transform: scale(0.9) translateY(6px); }
  60% { opacity: 1; transform: scale(1.03) translateY(0); }
  100% { opacity: 1; transform: scale(1); }
}
@keyframes scaleFadeOut {
  0% { opacity: 1; transform: scale(1); }
  100% { opacity: 0; transform: scale(0.95) translateY(6px); }
}

.run-btn {
  position: absolute;
  top: 8px;
  right: 8px;

  width: 24px;
  height: 24px;
  border-radius: 24px;

  padding: 0;
  box-sizing: border-box;

  display: flex;
  align-items: center;
  justify-content: center;

  background-color: rgba(240, 255, 255, 0.212);
  border: 1.5px solid #2e7d32;
  font-size: 24px;
  color: #2e7d32;

  cursor: pointer;
  transition: all 0.25s ease;
}

.run-btn:active {
  border-color: transparent;
}

.run-btn.isRunning {
  font-size: 20px;
  border: 1.5px solid #d18b00;
  color: #1d1300;
}

.run-btn.fail {
  font-size: 20px;
  border: 1.5px solid #ff2600bb;
  color: #ff2600bb;
}

.run-btn.pending {
  font-size: 20px;
  border: 1.5px solid #999999bb;
  color: #424242bb;
}

.play-icon {
  transform: scaleY(0.8);
  transform-origin: center;
  color: inherit;
}

.arc-spinner {
  width: 14px;
  height: 14px;
  border-radius: 50%;

  /* Arc effect */
  border: 2px solid transparent;
  border-top-color: #d18b00;
  border-right-color: #d18b00;

  animation: arc-rotate 0.8s linear infinite;
}

@keyframes arc-rotate {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.arc-spinner.smooth {
  width: 14px;
  height: 14px;
  border-radius: 50%;

  border: 2px solid transparent;

  /* Single arc */
  border-top-color: #d18b00;

  animation: spinner-rotate 0.9s linear infinite;
}

.arc-spinner.smooth::after {
  content: '';
  position: absolute;
  inset: 0;

  border-radius: 50%;
  border: 2px solid transparent;
  border-top-color: rgba(209, 139, 0, 0.4);
}

@keyframes spinner-rotate {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.task-info-view {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -57%);
  height: 70vh;
  z-index: 999999;
  
}

</style>
