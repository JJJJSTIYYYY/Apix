<template>
  <div class="task-card selectable" :class="{ 'is-completed': status === 'completed', 'is-failed': status === 'failed' }">
    <!-- 左侧状态指示条 -->
    <div class="status-indicator-wrapper">
      <div class="status-indicator" :class="statusClass"></div>
    </div>
    
    <!-- 主要内容区 -->
    <div class="task-content">
      <!-- 顶部：ID和状态 -->
      <div class="task-header">
        <div class="task-id">
          <el-icon><Document /></el-icon>
          <span class="id-text">{{ task_id }}</span>
        </div>
        <div class="task-status" :class="statusClass">
          <span>{{ statusText }}</span>
        </div>
      </div>

      <!-- 任务描述 -->
      <div class="task-goal">
        <div class="goal-label">任务目标</div>
        <div class="goal-text">{{ final_goal }}</div>
      </div>

      <!-- 当前处理项 -->
      <div class="current-todo" v-if="current_todo">
        <div class="todo-label">正在处理</div>
        <div class="todo-text">
          <span class="pulse-dot"></span>
          {{ current_todo }}
        </div>
      </div>

      <!-- 底部信息 -->
      <div class="task-footer">
        <div class="agent-info">
          <el-avatar :size="24" class="agent-avatar">
            <el-icon><User /></el-icon>
          </el-avatar>
          <span class="agent-name">{{ agent_identity }}</span>
        </div>
        <div class="duration-info">
          <el-icon><Clock /></el-icon>
          <span>{{ formattedDuration }}</span>
        </div>
      </div>
    </div>

    <!-- 右侧操作区 -->
    <div class="task-actions">
      <el-button
        type="danger"
        class="terminate-btn"
        :disabled="status === 'completed' || status === 'failed' || status === 'cancelled'"
        @click="handleTerminate"
      >
        <el-icon><VideoPause /></el-icon>
        终止
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { ConfirmDialog } from '../comp/confirmDialog.js'

// ----------------------------------------------------------------------
// Props
// ----------------------------------------------------------------------
interface TaskCardProps {
  history_id: string
  task_id: string
  agent_identity: string
  final_goal: string
  current_todo: string
  duration: number  // 秒数
  status: "in_progress"| "completed"| "pending"| "failed"| "cancelled"
}

const props = defineProps<TaskCardProps>()

// ----------------------------------------------------------------------
// Emits
// ----------------------------------------------------------------------
const emit = defineEmits<{
  terminate: [history_id: string, task_id: string]
}>()

// ----------------------------------------------------------------------
// Computed
// ----------------------------------------------------------------------
const statusClass = computed(() => {
  return {
    'status-pending': props.status === 'pending',
    'status-running': props.status === 'in_progress',
    'status-completed': props.status === 'completed',
    'status-cancelled': props.status === 'cancelled',
    'status-failed': props.status === 'failed'
  }
})

const statusText = computed(() => {
  const map: Record<string, string> = {
    pending: '等待中',
    in_progress: '运行中',
    completed: '已完成',
    cancelled: '已取消',
    failed: '失败'
  }
  return map[props.status] || props.status
})

const formattedDuration = computed(() => {
  const seconds = props.duration
  if (seconds < 60) return `${seconds}秒`
  if (seconds < 3600) {
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins}分${secs}秒`
  }
  const hours = Math.floor(seconds / 3600)
  const mins = Math.floor((seconds % 3600) / 60)
  return `${hours}时${mins}分`
})

// ----------------------------------------------------------------------
// Methods
// ----------------------------------------------------------------------
const handleTerminate = async () => {
  try {
    await ConfirmDialog.confirm(
      `确定要终止任务 ${props.task_id} 吗？`,
      '终止确认',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
    )
    emit('terminate', props.history_id, props.task_id)
  } catch (err) {
    ElMessage({ type: 'error', message: '终止失败', plain: true })
  }
}
</script>

<style scoped>
.task-card {
  display: flex;
  background: var(--apix-panel-layer-3-background);
  border: 1px solid transparent;
  border-radius: var(--apix-border-radius-base);
  box-shadow: var(--apix-shadow-layer-1);
  overflow: hidden;
  transition: box-shadow 0.22s var(--apix-cubic-bezier);
  position: relative;
}

.task-card:hover {
  border: 1px solid var(--apix-primary-color);
  box-shadow: var(--apix-shadow-layer-2);
  background: var(--apix-panel-layer-5-background);
}

.task-card.is-completed {
  opacity: 0.85;
}

.task-card.is-failed {
  background: color-mix(in srgb, var(--apix-danger-color) 15%, transparent);
}

.task-card.is-failed:hover {
  border-color: var(--apix-danger-color);
}

/* 状态指示条 */
.status-indicator-wrapper {
  padding: 1px 1px 1px 3px;
  width: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.status-indicator {
  border-radius: 3px;
  width: 4px;
  height: 90%;
  flex-shrink: 0;
  transition: background-color 0.3s ease;
}

.status-pending {
  background: linear-gradient(180deg, var(--apix-tertiary-light-color) 0%, var(--apix-secondary-light-color) 100%);
}

.status-running {
  background: linear-gradient(180deg, var(--apix-primary-active) 0%, var(--apix-primary-color) 100%);
  animation: pulse-bar 2s ease-in-out infinite;
}

.status-completed {
  background: linear-gradient(180deg, var(--apix-success-active) 0%, var(--apix-success-color) 100%);
}

.status-failed {
  background: linear-gradient(180deg, var(--apix-danger-active) 0%, var(--apix-danger-color) 100%);
}

@keyframes pulse-bar {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}

/* 内容区 */
.task-content {
  flex: 1;
  padding: 16px 8px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
}

/* 头部 */
.task-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
}

.task-id {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--apix-tertiary-dark-color);
}

.id-text {
  font-size: 12px;
  letter-spacing: 0.5px;
}

.task-status {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 500;
  transition: background 0.3s ease,
    color 0.3s ease;
}

.task-status.status-pending {
  background: var(--apix-tertiary-light-color);
  color: var(--apix-tertiary-dark-color);
}

.task-status.status-running {
  background: var(--apix-primary-color);
  color: var(--apix-primary-light);
}

.task-status.status-completed {
  background: var(--apix-success-color);
  color: var(--apix-success-light);
}

.task-status.status-failed {
  background: var(--apix-danger-color);
  color: var(--apix-danger-light);
}

.task-status .el-icon {
  font-size: 14px;
}

.task-status.status-running .el-icon {
  animation: rotating 2s linear infinite;
}

@keyframes rotating {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* 任务目标 */
.task-goal {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.goal-label {
  font-size: 11px;
  color: var(--apix-tertiary-dark-color);
  text-transform: uppercase;
  letter-spacing: 0.8px;
  font-weight: 500;
}

.goal-text {
  font-size: 15px;
  color: var(--apix-default-dark-color);
  font-weight: 500;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* 当前处理项 */
.current-todo {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.todo-label {
  font-size: 11px;
  color: var(--apix-primary-color);
  text-transform: uppercase;
  letter-spacing: 0.8px;
  font-weight: 600;
}

.todo-text {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--apix-tertiary-dark-color);
  background: var(--apix-default-light-color);
  padding: 8px 12px;
  border-radius: 8px;
  border-left: 3px solid var(--apix-primary-active);
}

.pulse-dot {
  width: 6px;
  height: 6px;
  background: var(--apix-tertiary-dark-color);
  border-radius: 50%;
  animation: pulse-dot 1.5s ease-in-out infinite;
  flex-shrink: 0;
}

@keyframes pulse-dot {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(0.8); }
}

/* 底部信息 */
.task-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 4px;
  padding-top: 12px;
  border-top: 1px solid var(--apix-default-light-color);
}

.agent-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.agent-avatar {
  background: linear-gradient(135deg, rgb(136, 202, 197) 0%, rgb(100, 180, 170) 100%);
  color: white;
  font-size: 12px;
}

.agent-name {
  font-size: 13px;
  color: var(--apix-secondary-dark-color);
  font-weight: 500;
}

.duration-info {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--apix-tertiary-dark-color);
}

.duration-info .el-icon {
  font-size: 14px;
  color: var(--apix-primary-active);
}

/* 操作区 */
.task-actions {
  display: flex;
  align-items: center;
  padding: 0 20px;
  border-left: 1px solid var(--apix-default-light-color);
}

.terminate-btn {
  width: 80px;
  height: 36px;
  font-size: 13px;
  font-weight: 500;
  border-radius: var(--apix-button-border-radius);
  border: none;
  background: linear-gradient(135deg, var(--apix-danger-active) 0%, var(--apix-danger-color) 100%);
  box-shadow: var(--apix-shadow-layer-1);
  transition: transform 0.3s var(--apix-cubic-bezier),
              box-shadow 0.3s var(--apix-cubic-bezier),
              background 0.3s var(--apix-cubic-bezier),
              opacity 0.3s var(--apix-cubic-bezier);
}

.terminate-btn:hover:not(:disabled) {
  transform: scale(1.05);
  box-shadow: var(--apix-shadow-layer-2);
}

.terminate-btn:active:not(:disabled) {
  transform: scale(1.02);
}

.terminate-btn:disabled {
  background: var(--apix-secondary-light-color);
  box-shadow: none;
  cursor: not-allowed;
  opacity: 0.5;
}

.terminate-btn .el-icon {
  margin-right: 4px;
  font-size: 14px;
}
</style>