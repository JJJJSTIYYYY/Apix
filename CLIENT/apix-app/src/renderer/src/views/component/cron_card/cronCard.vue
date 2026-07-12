<template>
  <div class="task-card selectable">
    <!-- Header -->
    <div class="task-header">
      <el-switch
        v-model="localEnabled"
        size="small"
        @change="handleToggle"
      />

      <div class="task-actions">
        <button
          class="icon-btn delete-btn"
          title="Delete TASK"
          @click="handleDelete"
        >
          <el-icon><Delete /></el-icon>
        </button>

        <button
          class="icon-btn"
          title="Edit TASK"
          @click="handleEdit"
        >
          <el-icon><Setting /></el-icon>
        </button>
      </div>
    </div>

    <!-- Content -->
    <div class="task-content">
      <div class="task-title-wrapper">
        <div class="task-icon">
          <svg t="1783625438402" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="6815" width="16" height="16"><path d="M539.116 565.261V381.197c0-4.396-1.777-8.709-4.859-11.821a16.605 16.605 0 0 0-11.706-4.879h-47.934a16.563 16.563 0 0 0-11.697 4.879 16.937 16.937 0 0 0-4.857 11.821v217.36c0 4.398 1.776 8.69 4.857 11.802a16.564 16.564 0 0 0 4.263 3.092l183.109 123.561a16.56 16.56 0 0 0 9.17 2.815 17.12 17.12 0 0 0 3.525-0.38c4.385-0.935 8.164-3.627 10.568-7.467l23.036-37.137c4.724-7.59 2.588-17.624-4.796-22.647l-152.68-106.933z m374.63 21.199c0 218.09-180.069 394.873-402.206 394.873-222.137 0-402.207-176.782-402.207-394.873 0-198.012 155.164-361.957 348.76-390.457v-76.566H410.42c-21.61 0-39.1-17.182-39.1-38.38 0.001-21.198 17.49-38.39 39.1-38.39H613.38c21.588 0 39.11 17.192 39.11 38.39s-17.52 38.38-39.11 38.38h-48.588v76.546c193.677 28.426 348.955 192.404 348.955 390.477z" fill="currentColor" p-id="6816"></path></svg>
        </div>

        <div class="task-title" :title="name">
          {{ name }}
        </div>
      </div>

      <div class="task-description-wrapper">
        <div class="task-description" :title="description">
          {{ description }}
        </div>

        <div class="task_prompt" :title="prompt">
          <svg t="1783627269754" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="14588" width="16" height="16"><path d="M800 704v17.888h-184.128c-29.664 0-61.184 18.848-74.912 44.832L512 821.44l-28.96-54.752c-13.728-25.952-45.248-44.8-74.912-44.8H224V256h576v448z m5.312-512H218.688C186.336 192 160 219.488 160 253.248v471.392c0 33.76 26.4 61.248 58.816 61.248h189.312c5.92 0 15.712 5.728 18.368 10.752l38.048 71.968 2.912 4.544c11.168 14.528 27.392 22.848 44.544 22.848 17.152 0 33.376-8.32 44.544-22.848l40.96-76.512c2.464-4.608 11.968-10.752 18.368-10.752h189.472c32.352 0 58.656-27.488 58.656-61.248V253.248C864 219.488 837.664 192 805.312 192z" fill="currentColor" p-id="14589"></path><path d="M336 448c-12.352 0-23.488 4.8-32 12.448A47.68 47.68 0 0 0 288 496c0 14.176 6.24 26.752 16 35.552a47.68 47.68 0 0 0 32 12.448 48 48 0 0 0 0-96M688 448a48 48 0 0 0 0 96c12.352 0 23.488-4.8 32-12.448 9.76-8.8 16-21.376 16-35.552a47.68 47.68 0 0 0-16-35.552 47.68 47.68 0 0 0-32-12.448M512 448c-12.352 0-23.488 4.8-32 12.448a47.68 47.68 0 0 0-16 35.552c0 14.176 6.24 26.752 16 35.552A47.68 47.68 0 0 0 512 544c12.352 0 23.488-4.8 32-12.448 9.76-8.8 16-21.376 16-35.552a47.68 47.68 0 0 0-16-35.552A47.68 47.68 0 0 0 512 448" fill="currentColor" p-id="14590"></path></svg>
          <span class="task_prompt_content">{{ prompt }}</span>
        </div>

        <div class="task_execute" @click="showPythonCode" style="cursor: pointer;">
          <svg t="1783626892697" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="12598" width="16" height="16"><path d="M153.770667 517.558857l200.387047-197.241905L302.86019 268.190476 48.761905 518.290286l254.439619 243.614476 50.590476-52.833524-200.021333-191.512381zM658.285714 320.316952L709.583238 268.190476l254.098286 250.09981L709.241905 761.904762l-50.590476-52.833524 200.021333-191.512381L658.285714 320.316952z m-112.981333-86.186666L393.99619 785.554286l70.534096 19.358476 151.30819-551.399619-70.534095-19.358476z" fill="currentColor" p-id="12599"></path></svg>
          <span>{{ !execute || execute === '' ? '没有等待执行的 Python 代码' : "Python 代码已在执行计划中" }}</span>
        </div>
      </div>
    </div>

    <!-- Footer -->
    <div class="task-footer">
      <div
        class="footer-tag time-tag"
        :title="exec_time"
      >
        <el-icon><Clock /></el-icon>
        <span style="margin-right: 12px;">计划执行时间:</span>
        <span>{{ exec_time }}</span>
      </div>

      <div class="footer-tag repeat-tag">
        <el-icon><Refresh /></el-icon>
        <span>{{ repeatLabel[repeat] }}</span>
      </div>

      <div class="footer-tag platform-tag">
        <el-icon><User /></el-icon>
        <span>{{ platform }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, toRaw, watch } from 'vue'
import { ConfirmDialog } from '../comp/confirmDialog.js'
import { mdDisplayer } from '../comp/mdDisplayer.js'

/* ---------------- Props ---------------- */

const props = defineProps({
  task_id: { type: String, required: true, },
  history_id: { type: String, required: true, },
  platform: { type: String, required: true, },
  name: { type: String, required: true, },
  prompt: { type: String, required: true, },
  execute: { type: String, required: true, },
  exec_time: { type: String, required: true, },
  repeat: { type: String as () => 'once' | 'day' | 'week' | 'month' | 'year', required: true, },
  enabled: { type: Boolean, required: true, },
  created_at: { type: String, required: true, },
  description: { type: String, default: '', },
})

const repeatLabel = {
  once: '不重复执行',
  day: '每天执行',
  week: '每周执行',
  month: '每月执行',
  year: '每年执行'
}

/* ---------------- Emits ---------------- */

const emit = defineEmits([
  'edit',
  'delete',
  'update:enabled',
])

/* ---------------- Local state ---------------- */

const localEnabled = ref(props.enabled)

watch(
  () => props.enabled,
  (val) => {
    localEnabled.value = val
  }
)

/* ---------------- Methods ---------------- */

const handleToggle = (val: boolean) => {
  emit('update:enabled', {
    id: props.task_id,
    enabled: val,
  })
}

const handleDelete = async () => {
  try {
    await ConfirmDialog.confirm(
      `确定要删除该定时任务吗？<br>${props.name}`,
      '删除确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )

    emit('delete', props.task_id)
  } catch {
    return
  }
}

const handleEdit = () => {
  emit('edit', props.task_id)
}

const showPythonCode = () => {
  if (!!!props.execute) return
  const codeBlock = "```python\n" + props.execute + "\n```"
  mdDisplayer.show(codeBlock, '源代码')
}
</script>

<style scoped>
.task-card {
  position: relative;
  padding: 14px 16px;
  border-radius: 12px;
  height: 250px;
  width: 486px;

  display: flex;
  flex-direction: column;

  background: var(--apix-panel-layer-2-background);
  border: 1px solid var(--apix-default-light-color);

  box-shadow: var(--apix-shadow-layer-2);

  transition: box-shadow 0.4s cubic-bezier(0.34, 2, 0.64, 1);
}

.task-card:hover {
  border: 1px solid var(--apix-primary-color);
}

.task-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  flex-shrink: 0;
}

.task-actions {
  display: flex;
  gap: 4px;
}

.task-content {
  flex: 1;
  display: flex;
  position: relative;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 12px;
  height: 163px;
}

.task-title-wrapper {
  display: grid;
  grid-template-columns: 30px auto;
  align-items: center;
  gap: 8px;
}

.task-icon {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  background: linear-gradient(135deg, #0ea5e9 0%, #38bdf8 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 14px;
}

.task-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--apix-default-dark-color);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task-description-wrapper {
  flex: 1;
  overflow: hidden;
}

.task-description {
  font-size: 13px;
  line-height: 1.6;
  color: var(--apix-tertiary-dark-color);
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
}

.task_prompt {
  margin-top: 6px;
  padding: 4px 8px;
  font-size: 13px;
  line-height: 1.6;
  overflow: hidden;
  color: var(--apix-secondary-dark-color);
  font-weight: 500;
  /* background: var(--apix-default-light-color); */
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 6px;
}

.task_prompt_content {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
  display: -webkit-box;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
  max-width: 430px;
}

.task_execute {
  position: absolute;
  bottom: -6px;
  font-size: 13px;
  line-height: 1.6;
  color: var(--apix-tertiary-dark-color);
  font-weight: 200;
  padding: 4px 8px;
  border-radius: 6px;
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 6px;
  background: var(--apix-default-light-color);
}

.task-footer {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 6px;
  column-gap: 8px;
  padding-top: 10px;
  border-top: 1px solid var(--apix-default-light-color);
}

.footer-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 500;
  background: var(--apix-default-light-color);
  color: var(--apix-secondary-dark-color);
  overflow: hidden;
  max-width: 100%;
  transition: all 0.2s ease;
  text-overflow: ellipsis;
  -webkit-line-clamp: 1;
}

.footer-tag:hover {
  transform: translateY(-1px);
}

.footer-tag .el-icon {
  flex-shrink: 0;
}

.tag-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}

.repeat-tag {
  color: #7c3aed;
  background: rgba(124, 58, 237, 0.1);
}

.platform-tag {
  color: #d97706;
  background: rgba(217, 119, 6, 0.1);
}

.time-tag {
  color: #64748b;
  grid-column: 1 / 3;
}

.enabled-tag {
  color: #15803d;
  background: rgba(34, 197, 94, 0.12);
}

.disabled-tag {
  color: #dc2626;
  background: rgba(239, 68, 68, 0.12);
}

.icon-btn {
  border: none;
  background: transparent;
  cursor: pointer;
  font-size: 14px;
  padding: 4px;
  border-radius: 6px;
  width: 26px;
  height: 26px;
  color: var(--apix-default-dark-color);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
}

.icon-btn:hover {
  background: var(--apix-default-light-color);
}

.delete-btn:hover {
  background-color: color-mix(in srgb, var(--apix-danger-color) 15%, transparent);
  color: var(--apix-danger-color);
  transform: rotate(4deg);
}
</style>
