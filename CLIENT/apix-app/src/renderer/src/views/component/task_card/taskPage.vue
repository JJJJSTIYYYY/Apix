<template>
  <div class="task-page-wrapper">
    <!-- 底部操作栏 -->
    <div class="ab-bar">
      <div class="ab-bar-btns">
        <el-button
          type="primary"
          class="refresh-btn"
          @click="refreshTasks"
          :loading="isRefreshing"
        >
          <el-icon class="el-icon--right"><Refresh /></el-icon>
          刷新任务
        </el-button>
        <el-button
          class="clear-btn"
          @click="clearCompleted"
        >
          <el-icon class="el-icon--right"><Delete /></el-icon>
          清理已完成
        </el-button>
      </div>
    </div>

    <div class="main-wrapper">
      <h1 class="data-page-title">
        后台子代理任务视图
      </h1>

      <!-- 搜索 -->
      <div class="search-wrapper">
        <el-input
          v-model="searchKeyword"
          placeholder="Search tasks by ID / goal / agent"
          clearable
          style="max-width: 420px;"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
        <div class="mode-switch-label">自动刷新</div>
        <div class="mode-switch">
          <div class="slider" :class="{ right: store.config.autoRefreshTask }" />

          <button
            class="off-select"
            :class="{ active: !store.config.autoRefreshTask }"
            @click="switchMode('autoRefreshTask', 'off')"
          >
            Off
          </button>

          <button
            class="on-select"
            :class="{ active: store.config.autoRefreshTask }"
            @click="switchMode('autoRefreshTask', 'on')"
          >
            On
          </button>
        </div>
      </div>

      <!-- 统计信息 -->
      <div class="stats-wrapper">
        <div class="stat-item">
          <div class="stat-value" :style="{ color: 'rgb(136, 202, 197)' }">{{ taskStats.total }}</div>
          <div class="stat-label">总任务</div>
        </div>
        <div class="stat-item">
          <div class="stat-value status-running-text">{{ taskStats.running }}</div>
          <div class="stat-label">运行中</div>
        </div>
        <div class="stat-item">
          <div class="stat-value status-pending-text">{{ taskStats.pending }}</div>
          <div class="stat-label">等待中</div>
        </div>
        <div class="stat-item">
          <div class="stat-value status-completed-text">{{ taskStats.completed }}</div>
          <div class="stat-label">已完成</div>
        </div>
      </div>

      <!-- 任务列表（普通列表 + 过渡动画） -->
      <div v-if="filteredTaskList.length" class="task-list-container">
        <transition-group
          name="task-fade"
          tag="div"
          class="task-list"
        >
          <div
            v-for="(item, index) in filteredTaskList"
            :key="item.task_id"
            class="task-item-wrapper"
            :style="{ '--stagger-index': index }"
          >
            <TaskCard
              :history_id="item.history_id"
              :task_id="item.task_id"
              :agent_identity="item.agent_identity"
              :final_goal="item.final_goal"
              :current_todo="item.current_todo"
              :duration="item.duration"
              :status="item.status"
              @terminate="handleTerminate"
            />
          </div>
        </transition-group>
      </div>

      <!-- 空状态 -->
      <div
        v-else
        class="empty-state"
      >
        <el-empty description="No tasks found">
          <template #image>
            <el-icon :size="60" color="#dcdfe6"><DocumentDelete /></el-icon>
          </template>
        </el-empty>
      </div>

      <div style="width: 100%; height: 100px;"></div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import TaskCard from './taskCard.vue'
import { useAuthStore } from '../../../store/auth'
import { useAppCacheData } from '../../../store/app'
import { ConfirmDialog } from '../comp/confirmDialog.js'

// ----------------------------------------------------------------------
// Types
// ----------------------------------------------------------------------
interface TaskItem {
  history_id: string
  task_id: string
  agent_identity: string
  final_goal: string
  current_todo: string
  duration: number
  status: 'in_progress' | 'completed' | 'pending' | 'failed' | 'cancelled'
  created_at: number
}

// ----------------------------------------------------------------------
// Store & Auth
// ----------------------------------------------------------------------
const authStore = useAuthStore()
const store = useAppCacheData()
const cid = ref('')

// ----------------------------------------------------------------------
// State
// ----------------------------------------------------------------------
const taskList = ref<TaskItem[]>([])
const searchKeyword = ref('')
const isRefreshing = ref(false)
const isAutoRefreshing = ref(false)
let refreshTimer: ReturnType<typeof setInterval> | null = null

const statusOrder: Record<TaskItem['status'], number> = {
  in_progress: 0,
  pending: 1,
  failed: 2,
  cancelled: 3,
  completed: 4
}

const cloneTaskList = (list: TaskItem[]) => list.map(item => ({ ...item }))

const sortTaskList = (list: TaskItem[]) => {
  return cloneTaskList(list).sort((a, b) => {
    const orderDiff = statusOrder[a.status] - statusOrder[b.status]
    if (orderDiff !== 0) return orderDiff
    return b.created_at - a.created_at
  })
}

// ----------------------------------------------------------------------
// Lifecycle
// ----------------------------------------------------------------------
onMounted(async () => {
  try {
    await authStore.restore()
    cid.value = authStore.user?.user_uid || ''
  } catch (err) {
    console.error('初始化失败', err)
  }

  await loadTasks(false)

  if (store.config.autoRefreshTask) {
    startAutoRefresh()
  }
})

onUnmounted(() => {
  stopAutoRefresh()
})

// 监听自动刷新开关
watch(
  () => store.config.autoRefreshTask,
  (enabled) => {
    if (enabled) {
      startAutoRefresh()
    } else {
      stopAutoRefresh()
    }
  }
)

// ----------------------------------------------------------------------
// API Functions
// ----------------------------------------------------------------------
const getTaskList = async (clear: boolean): Promise<TaskItem[]> => {
  const res = await window.api.getAiTaskList(clear)

  if (!Array.isArray(res?.task_list)) {
    console.log('getAiTaskList return invalid data:', res)
    return []
  }

  return sortTaskList(
    res.task_list.map((item: any) => ({
      history_id: item.history_id ?? '',
      task_id: item.task_id ?? '',
      agent_identity: item.agent_identity ?? '',
      final_goal: item.final_goal ?? '',
      current_todo: item.current_todo ?? '',
      duration: Number(item.duration ?? 0),
      status: item.status ?? 'pending',
      created_at: Number(item.created_at ?? Date.now())
    }))
  )
}

const terminateTask = async (history_id:string, taskId: string): Promise<boolean> => {
  const res = await window.api.terminateAiTask(history_id, taskId)
  ElMessage.info(res)
  taskList.value = await getTaskList(false)

  const task = taskList.value.find(item => item.task_id === taskId)
  if (task && (task.status === 'in_progress' || task.status === 'pending')) {
    task.status = 'cancelled'
    task.current_todo = '任务被用户终止'
  }

  return true
}

// ----------------------------------------------------------------------
// Computed
// ----------------------------------------------------------------------
const filteredTaskList = computed(() => {
  const keyword = searchKeyword.value.trim().toLowerCase()
  if (!keyword) return taskList.value

  return taskList.value.filter(task =>
    task.task_id.toLowerCase().includes(keyword) ||
    task.final_goal.toLowerCase().includes(keyword) ||
    task.agent_identity.toLowerCase().includes(keyword) ||
    task.current_todo.toLowerCase().includes(keyword)
  )
})

const taskStats = computed(() => {
  return {
    total: taskList.value.length,
    running: taskList.value.filter(t => t.status === 'in_progress').length,
    pending: taskList.value.filter(t => t.status === 'pending').length,
    completed: taskList.value.filter(t => t.status === 'completed').length,
    failed: taskList.value.filter(t => t.status === 'failed').length
  }
})

// ----------------------------------------------------------------------
// Methods
// ----------------------------------------------------------------------
const loadTasks = async (showError = true) => {
  try {
    taskList.value = await getTaskList(false)
  } catch (err) {
    console.error('加载任务失败:', err)
    if (showError) {
      ElMessage.error('加载任务列表失败')
    }
  }
}

const refreshTasks = async () => {
  if (isRefreshing.value) return
  isRefreshing.value = true

  try {
    await loadTasks(true)
    ElMessage.success('任务列表已刷新')
  } finally {
    isRefreshing.value = false
  }
}

const handleTerminate = async (history_id:string, taskId: string) => {
  try {
    await terminateTask(history_id, taskId)
    ElMessage.success('任务已终止')
    await loadTasks(false)
  } catch (err) {
    console.error('终止任务失败:', err)
    ElMessage.error('终止任务失败')
  }
}

const clearCompleted = async () => {
  try {
    await ConfirmDialog.confirm(
      '确定要清理已完成任务吗？清理后Agent将无法查询到任务信息',
      '清理确认',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
    )
    try {
      taskList.value = await getTaskList(true)
    } catch (err) {
      console.error('加载任务失败:', err)
      if (showError) {
        ElMessage.error('加载任务列表失败')
      }
    }
    ElMessage.success('已完成任务已清理')
  } catch (err) {
    if (err !== 'cancel') {
      console.error('清理任务失败:', err)
    }
  }
}

// ----------------------------------------------------------------------
// Auto Refresh
// ----------------------------------------------------------------------
const startAutoRefresh = () => {
  if (refreshTimer) return

  refreshTimer = setInterval(async () => {
    if (!store.config.autoRefreshTask) return
    if (isRefreshing.value || isAutoRefreshing.value) return

    isAutoRefreshing.value = true
    try {
      await loadTasks(false)
    } catch (err) {
      console.error('自动刷新任务失败:', err)
    } finally {
      isAutoRefreshing.value = false
    }
  }, 3000)
}

const stopAutoRefresh = () => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
  isAutoRefreshing.value = false
}

// ----------------------------------------------------------------------
// Settings
// ----------------------------------------------------------------------
const switchMode = (key: keyof typeof store.config, target: 'on' | 'off') => {
  const value = target === 'on'

  store.config[key] = value as any
  store.saveAppConfig(key as string, value)

  if (key === 'autoRefreshTask') {
    if (value) {
      startAutoRefresh()
    } else {
      stopAutoRefresh()
    }
  }
}
</script>

<style scoped>
.task-page-wrapper {
  position: relative;
  background-color: rgba(255, 255, 255, 0.5);
  box-shadow: 
    inset 0 0 0 2px rgba(255, 255, 255, 0.8),
    0 0px 26px rgba(218, 218, 218, 0.206),
    0 0px 6px rgba(218, 218, 218, 0.09);
  border-radius: 24px;
  margin: 12px 12px 12px 0;
}

.main-wrapper {
  position: relative;
  justify-content: center;
  width: 1050px;
  height: calc(100vh - 76px) !important;
  left: calc((100% - 1090px) / 2);
  padding: 10px 20px;
  overflow-y: scroll;
  border-radius: 16px;
  align-items: center;
}

.data-page-title {
  padding-left: 6px;
  font-size: 24px;
  color: rgb(82, 108, 106);
  margin-bottom: 0px;
}

/* 底部操作栏 */
.ab-bar {
  width: 100%;
  position: absolute;
  bottom: 24px;
  display: flex;
  flex-direction: column;
  align-items: center;
  z-index: 999;
}

.ab-bar-btns {
  display: flex;
  flex-direction: row;
  gap: 16px;
  z-index: 999;
}

.refresh-btn {
  height: 36px;
  font-size: 14px;
  font-weight: 500;
  border-radius: 32px;
  color: #606266;
  background: rgba(255, 255, 255, 0.6);
  border: 1px solid rgba(136, 202, 197, 0.3);
  transition: all 0.3s ease;
}

.refresh-btn:hover {
  background: rgba(255, 255, 255, 0.9);
  border-color: rgba(136, 202, 197, 0.5);
  transform: scale(1.05);
}

.clear-btn {
  height: 36px;
  font-size: 14px;
  font-weight: 500;
  border-radius: 32px;
  color: #606266;
  background: rgba(255, 255, 255, 0.6);
  border: 1px solid rgba(136, 202, 197, 0.3);
  transition: all 0.3s ease;
}

.clear-btn:hover {
  background: rgba(255, 255, 255, 0.9);
  border-color: rgba(136, 202, 197, 0.5);
  transform: scale(1.05);
}

/* 统计信息 */
.stats-wrapper {
  display: flex;
  justify-content: center;
  gap: 32px;
  margin: 20px 12px;
  padding: 16px;
  background: rgba(136, 202, 196, 0.189);
  border-radius: 24px;
  box-shadow: 
    0 0px 26px rgba(218, 218, 218, 0.206),
    0 0px 6px rgba(218, 218, 218, 0.09);
  transition: all 0.3s ease;
}

.stats-wrapper:hover {
  transform: scale(1.01);
  box-shadow: 
    0 0px 36px rgba(218, 218, 218, 0.3),
    0 0px 12px rgba(218, 218, 218, 0.15);
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.stat-value {
  font-size: 24px;
  font-weight: 700;
}

.stat-label {
  font-size: 12px;
  color: #909399;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.status-running-text {
  color: rgb(136, 202, 197);
}

.status-pending-text {
  color: #e6a23c;
}

.status-completed-text {
  color: #67c23a;
}


.search-wrapper {
  width: 100%; 
  display: flex; 
  margin: 16px 0;
  gap: 12px;
  align-items: center;
}

.search-wrapper :deep(.el-input) {
  height: 32px !important;
  flex: 1;
  min-width: 0;
  transform-origin: left center;
  transform: scale(1);
  transform-origin: center;
  transition: transform 0.22s cubic-bezier(0.34, 1, 0.64, 1);
}

.search-wrapper :deep(.el-input__wrapper) {
  height: 32px !important;
  background: transparent;
  border: none;
  border-radius: 0px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.1);
  box-shadow: none;
  padding: 0 12px 0 10px;
  transition: all 0.13s ease, border-color 0.18s ease, box-shadow 0.18s ease;
}

/* 任务列表容器 */
.task-list-container {
  width: 100%;
  min-height: 400px;
  position: relative;
}

.task-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.task-item-wrapper {
  transition: transform 0.3s ease;
}

/* 空状态 */
.empty-state {
  width: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 400px;
}

/* 滚动条样式 */
.main-wrapper::-webkit-scrollbar {
  width: 0px;
  height: 0px;
}

/* 列表动画 - 淡入淡出效果 */
.task-fade-enter-active {
  transition: 
    opacity 0.5s cubic-bezier(0.215, 0.61, 0.355, 1),
    transform 0.5s cubic-bezier(0.215, 0.61, 0.355, 1);
  transition-delay: calc(var(--stagger-index, 0) * 40ms);
}

.task-fade-enter-from {
  opacity: 0;
  transform: translateY(20px) scale(0.95);
}

.task-fade-enter-to {
  opacity: 1;
  transform: translateY(0) scale(1);
}

/* 离开动画 */
.task-fade-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
  position: absolute;
}

.task-fade-leave-to {
  opacity: 0;
  transform: scale(0.9);
}

/* 移动动画 */
.task-fade-move {
  transition: transform 0.4s cubic-bezier(0.215, 0.61, 0.355, 1);
}

.mode-switch-label {
  position: absolute;
  right: 90px;
  display: flex;
  text-align: center;
  color: rgba(80, 120, 117, 0.712);
}

.mode-switch {
  position: absolute;
  right: 24px;
  display: flex;
  background: rgba(226, 226, 226, 0.32);
  border-radius: 999px;
  border: 1px solid rgba(213, 213, 213, 0.318);
  box-shadow: inset 1px -1px 16px rgba(117, 187, 248, 0.083);
}

.mode-switch button {
  flex: 1;
  height: 24px;
  border: none;
  background-color: transparent;
  cursor: pointer;
  z-index: 1;
  font-size: 12px;
  color: #4040409A;
  transition: color 0.25s ease;
}

.mode-switch button.active {
  color: #0000009A;
}

/* Slider */
.slider {
  position: absolute;
  width: calc(50% + 4px);
  height: calc(100% + 2px);
  margin-top: -1px;
  margin-left: -1px;
  border-radius: 32px;
  transition: all 0.3s cubic-bezier(0.215, 0.61, 0.355, 1);
  box-shadow:
    0 8px 24px rgba(62, 67, 66, 0.12),
    0 0 0 2px rgba(136, 202, 196, 0.471);
  background-color: #ffffff2c;
}

.slider.right {
  transform: translateX(82%);
}

.mode-switch:active:deep(.slider) {
  z-index: 999;
  box-shadow:
    0 8px 24px rgba(62, 67, 66, 0.12),
    0 0 0 2px color-mix(in srgb, rgba(136, 202, 196, 0.567) 25%, transparent);
  -webkit-backdrop-filter: saturate(180%) blur(16px);
  backdrop-filter: saturate(180%) blur(3px);
  -webkit-transition: all 0.3s cubic-bezier(0.215, 0.61, 0.355, 1);
  transition: all 0.3s cubic-bezier(0.215, 0.61, 0.355, 1);
  background-color: color-mix(in srgb, #ebebeb83 1%, transparent);
}
</style>