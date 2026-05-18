<template>
  <div class="task-row" :class="`task-row--${computedStatus}`">
    <!-- 状态指示器 -->
    <div class="task-row__indicator">
      <div v-if="isLoading" class="indicator indicator--spinning" />
      <div v-else class="indicator" :class="`indicator--${computedStatus}`">
        <svg v-if="computedStatus === 'completed'" viewBox="0 0 16 16" fill="none">
          <path d="M3 8L6.5 11.5L13 5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        <svg v-else-if="computedStatus === 'error'" viewBox="0 0 16 16" fill="none">
          <path d="M8 5V9M8 11H8.01" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
        </svg>
      </div>
    </div>

    <!-- 内容 -->
    <div class="task-row__content">
      {{ content }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

type Status = 'pending' | 'in_progress' | 'completed' | 'error'

interface Props {
  content: string
  status: Status
  pending?: boolean
}

const props = defineProps<Props>()

const isLoading = computed(() => props.status === 'in_progress' && props.pending !== false)
const computedStatus = computed(() => {
  if (props.status === 'in_progress' && props.pending === false) return 'pending'
  return props.status
})
</script>

<style scoped>
.task-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 12px;
  border-radius: 6px;
  font-size: 14px;
  line-height: 20px;
  color: var(--apix-darkest-color);
  transition: background-color 0.15s ease;
}

.task-row:hover {
  background-color: var(--apix-panel-layer-1-background);
}

/* 完成状态 */
.task-row--completed {
  color: var(--apix-secondary-dark-color);
}

.task-row--completed .task-row__content {
  text-decoration: line-through;
  text-decoration-color: var(--apix-darkest-color);
}

/* 错误状态 */
.task-row--error {
  color: var(--apix-danger-hover);
  background-color: var(--apix-danger-light);
}

.task-row--error:hover {
  background-color: var(--apix-danger-light);
}

/* 等待状态 */
.task-row--pending {
  color: var(--apix-secondary-dark-color);
}

/* 状态指示器 */
.task-row__indicator {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.indicator {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  box-sizing: border-box;
  border: 1.5px solid currentColor;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
}

/* 各状态样式 */
.indicator--pending {
  border-color: var(--apix-secondary-light-color);
}

.indicator--in_progress {
  border-color: var(--apix-info-hover);
  border-top-color: transparent;
}

.indicator--completed {
  background-color: var(--apix-success-color);
  border-color: var(--apix-success-color);
  color: white;
}

.indicator--error {
  background-color: var(--apix-danger-hover);
  border-color: var(--apix-danger-hover);
  color: white;
}

/* 加载动画 */
.indicator--spinning {
  border-color: var(--apix-info-hover);
  border-top-color: transparent;
  animation: spin 0.6s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* 图标 */
.indicator svg {
  width: 10px;
  height: 10px;
}

/* 内容区域 */
.task-row__content {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>