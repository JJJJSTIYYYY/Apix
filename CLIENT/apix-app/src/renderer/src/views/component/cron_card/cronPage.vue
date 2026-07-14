<template>
  <div class="task-page-wrapper">

    <div class="main-wrapper">

      <div class="page-title-wrapper">
        <div class="title-wrapper">
          <h1 class="data-page-title">
            定时任务
          </h1>
          <div class="btn-wrapper">
            <el-button
              type="primary"
              class="create-btn"
              @click="createCron"
            >
              新建任务
              <el-icon style="padding-left: 4px;"><Plus /></el-icon>
            </el-button>
            <el-button
              class="clear-btn"
              @click="clearCompleted"
            >
              清理任务
              <el-icon style="padding-left: 4px;"><Delete /></el-icon>
            </el-button>
            <el-button
              class="refresh-btn"
              @click="refreshTask"
            >
              刷新
              <el-icon style="padding-left: 4px;"><RefreshRight /></el-icon>
            </el-button>
          </div>

          <!-- 搜索 -->
          <div class="search-wrapper">
            <el-input
              v-model="searchKeyword"
              placeholder="通过任务ID、任务名称、任务提示词、执行时间搜索任务"
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
<span>1. 定时任务是什么: 定时任务可以指定一个未来执行的时间点，运行一段 Python 代码或使用指定的提示词唤醒 Agent。</span>

<span>2. 如何使用: 点击新建任务，输入计划执行的 Python 代码或需要输入给 Agent 的提示词，若代码中有额外依赖，需要自行安装。</span>

<span>3. 注意事项: 系统不会自动安装 Python 代码中的依赖，建议使用http的方式调用外部服务以维持系统整洁；代码中必须包含入口函数 apix_cron_main() -> str。</span>
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
            <CronCard
              :task_id="item.task_id"
              :history_id="item.history_id"
              :platform="item.platform"
              :name="item.name"
              :prompt="item.prompt"
              :execute="item.execute"
              :exec_time="item.exec_time"
              :repeat="item.repeat"
              :enabled="item.enabled"
              :created_at="item.created_at"
              :description="item.description"
              :extra_config="item.extra_config"
              @update:enabled="handleToggle"
              @delete="handleDelete"
              @edit="openCronDialog"
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

  <CronEditDialog
    v-if="dialogVisible"
    v-model="dialogVisible"
    :cron="editingCron"
    @save="handleSaveCron"
  />
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import CronCard from './cronCard.vue'
import { useAuthStore } from '../../../store/auth.js'
import { useAppCacheData } from '../../../store/app.js'
import { ConfirmDialog } from '../comp/confirmDialog.js'
import CronEditDialog from './CronEditDialog.vue'

// ----------------------------------------------------------------------
// Types
// ----------------------------------------------------------------------
interface TaskItem {
  task_id: string
  history_id: string
  platform: string
  name: string
  prompt: string
  execute: string
  exec_time: string
  repeat: 'once' | 'day' | 'week' | 'month' | 'year'
  extra_config?: Record<string, any>
  enabled: boolean
  created_at: string
  description: string
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

const cloneTaskList = (list: TaskItem[]) => list.map(item => ({ ...item }))

const sortTaskList = (list: TaskItem[]) => {
  const now = formatTime(new Date().toISOString())

  return cloneTaskList(list).sort((a, b) => {
    const ta = formatTime(a.exec_time)
    const tb = formatTime(b.exec_time)

    const aFuture = ta >= now
    const bFuture = tb >= now

    // Future tasks first
    if (aFuture !== bFuture) {
      return aFuture ? -1 : 1
    }

    // Within each group, sort by ascending time
    return ta.localeCompare(tb)
  })
}

// ----------------------------------------------------------------------
// Lifecycle
// ----------------------------------------------------------------------
onMounted(async () => {
  try {
    await authStore.restore()
    cid.value = authStore.user?.user_uid || ''
    taskList.value = await getTaskList()
  } catch (err) {
    console.error('[Task page onMounted error]:', err)
  }
})

// ----------------------------------------------------------------------
// API Functions
// ----------------------------------------------------------------------
const getTaskList = async (): Promise<TaskItem[]> => {
  const res = await window.api.getCronTaskList(cid.value)

  if (!Array.isArray(res)) {
    console.log('getCronTaskList return invalid data:', res)
    return []
  }

  return sortTaskList(
    res.map((item: any) => ({
      task_id: item.task_id ?? '',
      history_id: item.conversation_uid ?? '',
      platform: item.platform ?? '',
      name: item.name ?? '',
      prompt: item.prompt ?? '',
      execute: item.execute ?? '',
      exec_time: formatTime(item.exec_time) ?? '',
      repeat: item.repeat ?? 'once',
      extra_config: item.extra_config ?? {},
      enabled: Boolean(item.enabled) ?? true,
      created_at: item.created_at ?? '',
      description: item.description ?? ''
    }))
  )
}

// ----------------------------------------------------------------------
// Computed
// ----------------------------------------------------------------------
const filteredTaskList = computed(() => {
  const keyword = searchKeyword.value.trim().toLowerCase()
  if (!keyword) return taskList.value

  return taskList.value.filter(task =>
    task.task_id.toLowerCase().includes(keyword) ||
    task.name.toLowerCase().includes(keyword) ||
    task.prompt.toLowerCase().includes(keyword) ||
    task.exec_time.toLowerCase().includes(keyword)
  )
})

// ----------------------------------------------------------------------
// Methods
// ----------------------------------------------------------------------
const dialogVisible = ref(false)
const editingCron = ref<TaskItem | null>(null)

function openCronDialog(cronId: string) {
  editingCron.value = taskList.value.find(t => t.task_id === cronId) || null
  dialogVisible.value = true
}

const createCron = async () => {
  editingCron.value = null
  dialogVisible.value = true
}

async function handleSaveCron(payload: {
  is_editing: boolean
  task_id?: string
  history_id: string
  platform: string
  task_name: string
  prompt: string
  execute: string
  exec_time: string
  repeat: 'once' | 'day' | 'week' | 'month' | 'year'
  extra_config?: Record<string, any>
  description: string
}) {
  try {

    const cronMeta = JSON.parse(JSON.stringify({
      history_id: payload.history_id,
      platform: payload.platform,
      task_name: payload.task_name,
      prompt: payload.prompt,
      execute: payload.execute,
      exec_time: payload.exec_time,
      repeat: payload.repeat,
      extra_config: payload.extra_config || {},
      description: payload.description,
    }))

    let task_id = payload.task_id

    if (!payload.is_editing) {

      const res = await window.api.createCronTask(
        cid.value,
        cronMeta
      )

      task_id = res.task_id

    } else {

      if (!task_id) throw new Error('task_id missing')

      await window.api.updateCronTask(
        task_id,
        payload.repeat,
        payload.repeat === 'cron' ? payload.extra_config.cron_expression : payload.exec_time,
        cronMeta
      )
    }

    taskList.value = await getTaskList()

    ElMessage({
      type: 'success',
      message: '保存成功',
      plain: true,
    })

  } catch (err) {

    console.error('saveCron failed:', err)

    ElMessage({
      type: 'error',
      message: '保存失败: ' + String(err),
      plain: true,
    })

  }

}

async function handleToggle({ id, enabled }: { id: string; enabled: boolean }) {
  const current = taskList.value.find(m => m.task_id === id)
  if (!current) return

  try {
    current.enabled = enabled

    await window.api.updateCronTask(
      id,
      current.repeat,
      current.repeat === 'cron' ? current.extra_config.cron_expression : current.exec_time,
      { enabled }
    )

  } catch (err) {

    console.warn(
      '[handleToggle] window.api.updateCronTask failed:',
      err
    )

    current.enabled = !enabled

    ElMessage({
      type: 'error',
      message: '任务状态更新失败',
      plain: true,
    })
  }
}

const clearCompleted = async () => {
  try {
    await ConfirmDialog.confirm(
      '确定要清理所有已完成的定时任务吗？',
      '清理确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )

    const now = formatTime(new Date().toISOString())

    const completedTasks = taskList.value.filter(task => {
      return (
        task.repeat === 'once' &&
        formatTime(task.exec_time) < now
      )
    })

    for (const task of completedTasks) {
      await window.api.updateCronTask(
        task.task_id, 
        "",
        "",
        { is_deleted: true, }
      )
    }

    taskList.value = await getTaskList()

    ElMessage({
      type: 'success',
      message: '清理成功',
      plain: true,
    })
  } catch (err) {
    console.error(err)
    ElMessage({
      type: 'error',
      message: '清理失败',
      plain: true,
    })
  }
}

const refreshTask = async () => {
  try {
    taskList.value = await getTaskList()
    ElMessage({
      type: 'success',
      message: '已刷新',
      plain: true,
    })
  } catch (error) {
    ElMessage({
      type: 'error',
      message: '刷新失败',
      plain: true,
    })
    console.error(error)
  }
}

const handleDelete = async (taskId: string) => {
  try {
    const index = taskList.value.findIndex(t => t.task_id === taskId)
    const execTime = index >= 0 ? (taskList.value[index].repeat === 'cron' ? taskList.value[index].extra_config.cron_expression : taskList.value[index].exec_time) : ""
    const repeat = index >= 0 ? taskList.value[index].repeat : ""

    await window.api.updateCronTask(taskId, repeat, execTime, { is_deleted: true })

    if (index >= 0) {
      taskList.value.splice(index, 1)
    }

    ElMessage({
      type: 'success',
      message: '删除成功',
      plain: true,
    })
  } catch (err) {
    console.error(err)
    ElMessage({
      type: 'error',
      message: '删除失败',
      plain: true,
    })
  }
}

function formatTime(time: string) {
  return time?.replace?.('T', ' ').replace('Z', '') || ''
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

.create-btn,
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

.refresh-btn {
  width: 84px;
}

.create-btn:hover,
.refresh-btn:hover,
.clear-btn:hover {
  background-color: var(--apix-primary-hover);
}

.create-btn:active,
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
  border-top: 4px solid var(--apix-secondary-light-color);
  margin-top: 20px;
  padding-top: 32px;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
  margin-bottom: 20px;
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
</style>