<template>
  <div class="task-page-wrapper">

    <div class="main-wrapper">

      <div class="page-title-wrapper">
        <div class="title-wrapper">
          <h1 class="data-page-title">
            后台子代理任务视图
          </h1>
          <div class="btn-wrapper">
            <el-button
              type="primary"
              class="refresh-btn"
              @click="refreshTasks"
              :loading="isRefreshing"
            >
              刷新任务
              <el-icon style="padding-left: 4px;"><Refresh /></el-icon>
            </el-button>
            <el-button
              class="clear-btn"
              @click="clearCompleted"
            >
              清理已完成
              <el-icon style="padding-left: 4px;"><Delete /></el-icon>
            </el-button>
            <div class="auto-refresh-wrapper">
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
          </div>

          <!-- 搜索 -->
          <div class="search-wrapper">
            <el-input
              v-model="searchKeyword"
              placeholder="通过任务ID、任务目标、子代理名称搜索任务"
              clearable
              style="max-width: 420px;"
            >
              <template #prefix>
                <el-icon><Search /></el-icon>
              </template>
            </el-input>
          </div>
        </div>

        <div class="page-docs">
<span>1. 子代理是什么: 子代理是主 Agent 自主分配的后台任务执行者。它是主 Agent 的一个副本，但不具备再分配子代理的权限。子代理在工作时不会干扰用户与主 Agent 之间的对话。</span>

<span>2. 如何使用: 进入设置页面，开启 Agent 的子代理分配权限。当 Agent 分配子代理后，可以在当前页面查看任务分配情况及子代理的运行状态摘要。</span>

<span>3. 注意事项: 子代理任务被中断后，通常无法继续执行（蜂群模式除外）。开启蜂群模式后，除非用户明确要求，否则主 Agent 一般不会与已分配过的子代理继续对话。</span>
        </div>
      </div>

      <!-- 统计信息 -->
      <div class="stats-wrapper">
        <div class="stat-item">
          <div class="stat-value status-total-text">{{ taskStats.total }}</div>
          <div class="stat-label">总任务</div>
        </div>
        <div class="stat-item">
          <div class="stat-value status-pending-text">{{ taskStats.pending }}</div>
          <div class="stat-label">等待中</div>
        </div>
        <div class="stat-item">
          <div class="stat-value status-running-text">{{ taskStats.running }}</div>
          <div class="stat-label">运行中</div>
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
            <el-icon :size="60" color="var(--apix-tertiary-dark-color)"><DocumentDelete /></el-icon>
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
    console.error('[Task page onMounted error]:', err)
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
    console.error('[loadTasks error]:', err)
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
    console.error('[handleTerminate error]:', err)
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
      console.error('[clearCompleted error]:', err)
      if (showError) {
        ElMessage.error('加载任务列表失败')
      }
    }
    ElMessage.success('已完成任务已清理')
  } catch (err) {
    if (err !== 'cancel') {
      console.error('[clearCompleted error]:', err)
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
      console.error('[startAutoRefresh error]:', err)
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
  background-color: transparent;
  height: calc(100vh - 36px);
}

.page-title-wrapper {
  display: flex;
  justify-content: space-between;
}

.page-docs {
  min-width: 500px;
  max-width: 500px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  font-size: 12px;
  color: var(--apix-tertiary-dark-color);
  text-indent: 2em;
}

.title-wrapper {
  margin: 8px 0;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  padding: 0px 12px;
  min-width: 500px;
  max-width: 500px;
}

.data-page-title {
  padding-left: 6px;
  font-size: 24px;
  color: var(--apix-default-dark-color);
  margin-bottom: 0px;
}

.main-wrapper {
  position: relative;
  justify-content: center;
  width: 1050px;
  height: calc(100vh - 76px) !important;
  left: calc((100% - 1090px) / 2);
  padding: 10px 20px;
  overflow-y: scroll;
  align-items: center;
  scrollbar-width: none;
}

.refresh-btn,
.clear-btn {
  margin: 0 !important;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 105px;
  height: 32px;
  font-size: 14px;
  font-weight: bold;
  border-radius: var(--apix-button-border-radius);
  color: var(--apix-lightest-color);
  background: var(--apix-primary-color);
  transition: transform 0.2s var(--apix-cubic-bezier),
    background-color 0.2s var(--apix-cubic-bezier);
  border: none;
}

.refresh-btn:hover,
.clear-btn:hover {
  background-color: var(--apix-primary-hover);
}

.refresh-btn:active,
.clear-btn:active {
  transform: scale(0.98);
  background-color: var(--apix-primary-active);
}

.btn-wrapper {
  width: 100%; 
  display: flex; 
  margin: 8px 0;
  gap: 12px;
}

.search-wrapper {
  width: 100%;
  margin: 8px 0;
  display: flex;
  gap: 12px;
}

.search-wrapper :deep(.el-input) {
  flex: 1;
  min-width: 0;
  height: 38px !important;
  transform-origin: center;
  transform: scale(1);
  transition: transform 0.22s var(--apix-cubic-bezier);
}

.search-wrapper :deep(.el-input__wrapper) {
  height: 38px !important;
  padding: 0 12px 0 10px;
  background: transparent;
  background-color: var(--apix-panel-layer-4-background);
  border: none;
  border-radius: var(--apix-border-radius-base);
  box-shadow: var(--apix-shadow-layer-1);
  transition: all 0.13s var(--apix-cubic-bezier);
}

/* -------------- 统计信息 -------------- */
.stats-wrapper {
  display: flex;
  justify-content: center;
  gap: 32px;
  margin: 20px 12px;
  padding: 16px;
  background: color-mix(in srgb, var(--apix-primary-color) 20%, transparent);
  border-radius: 24px;
  box-shadow: var(--apix-shadow-layer-1);
  transition: transform 0.3s var(--apix-cubic-bezier),
    box-shadow 0.3s var(--apix-cubic-bezier);
}

.stats-wrapper:hover {
  transform: scale(1.01);
  box-shadow: var(--apix-shadow-layer-2);
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
  color: var(--apix-secondary-dark-color);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.status-total-text {
  color: var(--apix-primary-color);
}

.status-running-text {
  color: var(--apix-primary-active);
}

.status-pending-text {
  color: var(--apix-primary-color);
}

.status-completed-text {
  color: var(--apix-success-color);
}

/* -------------- 任务列表容器 -------------- */
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

.empty-state:deep(*) {
  color: var(--apix-tertiary-dark-color);
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

/* ---------------------------------- */
.auto-refresh-wrapper {
  padding-left: 62px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
}

.mode-switch-label {
  width: fit-content;
  display: flex;
  text-align: center;
  color: rgba(80, 120, 117, 0.712);
}

.mode-switch {
  position: relative;
  display: flex;
  background: color-mix(in srgb, var(--apix-default-light-color) 32%, transparent);
  border-radius: 999px;
  border: 1px solid color-mix(in srgb, var(--apix-border-light) 31.8%, transparent);
  box-shadow: inset 1px -1px 16px color-mix(in srgb, var(--apix-primary-color) 8.3%, transparent);
}

.mode-switch button {
  flex: 1;
  height: 24px;
  border: none;
  background-color: transparent;
  cursor: pointer;
  z-index: 1;
  font-size: 12px;
  color: var(--apix-secondary-dark-color);
  transition: color 0.25s ease;
}

.mode-switch button.active {
  color: var(--apix-darkest-color);
}

/* 共用 active 时的光晕与背景效果（original used color-mix） */
.mode-switch:active .slider,
.mode-switch:active:deep(.slider) {
  z-index: 999;
  box-shadow:
    var(--apix-shadow-lg),
    0 0 0 2px color-mix(in srgb, var(--apix-primary-color) 14%, transparent);
  backdrop-filter: saturate(180%) blur(3px);
  transition: all 0.3s var(--apix-cubic-bezier);
  background-color: color-mix(in srgb, var(--apix-default-light-color) 1%, transparent);
}

.highlight-select {
  color: var(--apix-secondary-dark-color);
  transition: color 0.25s ease;
}

.highlight-select.right {
  color: var(--apix-darkest-color);
  transition: color 0.25s ease;
}

/* Slider */
.slider {
  position: absolute;
  width: calc(50% + 4px);
  height: calc(100% + 2px);
  margin-top: -1px;
  margin-left: -1px;
  border-radius: 32px;
  transition: all 0.3s var(--apix-cubic-bezier);
  box-shadow:
    var(--apix-shadow-md),
    0 0 0 2px color-mix(in srgb, var(--apix-primary-color) 47.1%, transparent);
  background-color: var(--apix-lightest-color);
}

.slider.right {
  transform: translateX(87%);
}
/* ---------------------------------- */
</style>