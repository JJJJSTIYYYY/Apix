<template>
  <div class="edit-dialog-mask">
    <el-dialog
      v-model="visible"
      :title="isEdit ? '编辑定时任务' : '新建定时任务'"
      width="560px"
      destroy-on-close
      class="cron-dialog selectable"
      :close-on-click-modal="false"
    >
      <div class="form-wrapper">

        <!-- 名称 -->
        <div class="form-item">
          <div class="label">任务名称</div>
          <el-input
            v-model="localTaskName"
            placeholder="请输入定时任务名称"
            maxlength="50"
            show-word-limit
            class="input"
          />
        </div>

        <!-- 类型 -->
        <div class="form-item">
          <div class="label bind-conversation-label">
            {{ localAlwaysCreateConversation ? '选择工作目录' : '绑定会话' }}
            <div class="always-create-conversation">
              <el-checkbox v-model="localAlwaysCreateConversation">任务执行时总是使用新的会话</el-checkbox>
            </div>
          </div>
          <div 
            class="conversation-select-bar"
            v-if="!localAlwaysCreateConversation"
          >
            <el-select-v2
              v-model="localHistoryId"
              :options="historyListView"
              placeholder="请选择绑定会话"
              filterable
              class="select"
              @visible-change="syncHistoryList"
            />
            <el-button
              type="primary"
              class="refresh-btn"
              @click="handleCreateConversation"
            >
              新建会话
              <el-icon style="padding-left: 4px;"><Plus /></el-icon>
            </el-button>
          </div>
          <div 
            class="conversation-select-bar"
            v-else
          >
            <el-input
              v-model="localHistoryId"
              placeholder="输入目录路径"
              maxlength="255"
              show-word-limit
              class="input"
            />
            <el-button
              type="primary"
              class="refresh-btn"
              @click="selectDir"
            >
              选择目录
              <el-icon style="padding-left: 4px;"><Plus /></el-icon>
            </el-button>
          </div>
        </div>

        <!-- prompt -->
        <div class="form-item">
          <div class="label">任务提示词</div>
          <el-input
            v-model="localPrompt"
            placeholder="请输入任务提示词"
            show-word-limit
            type="textarea"
            class="textarea"
            :rows="3"
          />
        </div>

        <!-- execute -->
        <div class="form-item">
          <div class="label select-python-label">
            执行脚本
            <div>
              <button class="select-python" @click="selectPythonFile">
                <el-icon><Upload /></el-icon>
                选择文件
              </button>
            </div>
          </div>
          <el-input
            v-model="localExecute"
            placeholder="请输入Python代码或脚本路径"
            show-word-limit
            type="textarea"
            class="textarea"
            :rows="1"
          />
        </div>

        <!-- execute time -->
        <div class="form-item">
          <div class="label exec-time-label">
            {{ localUseCronExpression ? 'Cron 表达式' : '计划执行时间' }}
            <div class="always-create-conversation">
              <el-checkbox v-model="localUseCronExpression">使用 Cron 表达式</el-checkbox>
            </div>
          </div>
          <el-date-picker
            v-model="localExecTime"
            v-if="!localUseCronExpression"
            type="datetime"
            placeholder="请选择日期时间"
            format="YYYY-MM-DD HH:mm:ss"
            value-format="YYYY-MM-DD HH:mm:ss"
            style="width: 100%; overflow: visible"
          />
          <el-input
            v-else
            v-model="localCronExpression"
            placeholder="输入 Cron 表达式"
            class="input"
          />
        </div>

        <!-- repeat -->
        <div class="form-item" v-if="!localUseCronExpression">
          <div class="label">执行周期</div>
          <el-radio-group
            v-model="localRepeat"
            class="repeat-group"
          >
            <el-radio label="once">不重复</el-radio>
            <el-radio label="day">每天</el-radio>
            <el-radio label="week">每周</el-radio>
            <el-radio label="month">每月</el-radio>
          </el-radio-group>
        </div>

        <!-- 描述 -->
        <div class="form-item">
          <div class="label">描述</div>
          <el-input
            v-model="localDescription"
            type="textarea"
            :rows="3"
            placeholder="可选"
            class="textarea"
            resize="none"
          />
        </div>

      </div>

      <!-- Footer -->
      <template #footer>
        <div class="dialog-footer">
          <el-button 
            @click="handleCancel"
            class="cancel-btn"
          >
            取消
          </el-button>
          <el-button 
            type="primary" 
            @click="handleSave"
            class="save-btn"
            :disabled="!canSave"
          >
            保存
          </el-button>
        </div>
      </template>
    </el-dialog>
  </div>  
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useAuthStore } from '../../../store/auth.js'
import { InputDialog } from '../comp/inputDialog.js'
import { useAppCacheData } from '../../../store/app'

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
}

const props = defineProps<{
  modelValue: boolean
  cron?: TaskItem | null
}>()

/* ---------------- Emits ---------------- */
const emit = defineEmits<{
  (e: 'update:modelValue', val: boolean): void
  (e: 'save', payload: {
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
  }): void
}>()

/* ---------------- Dialog Visible ---------------- */
const visible = ref(props.modelValue)

watch(
  () => props.modelValue,
  val => visible.value = val
)

watch(visible, val => {
  emit('update:modelValue', val)
})

// ----------------------------------------------------------------------
// Store & Auth
// ----------------------------------------------------------------------
const authStore = useAuthStore()
const cid = ref('')
const store = useAppCacheData()

/* ---------------- Local State ---------------- */

const localHistoryId = ref('')
const localPlatform = ref('default')
const localTaskName = ref('')
const localPrompt = ref('')
const localExecute = ref('')
const localExecTime = ref('')
const localRepeat = ref('')
const localDescription = ref('')
const localHistoryList = ref<Array<{ id: string, preview: string }>>([])
const historyListView = computed(() => {
  return localHistoryList.value.map(item => ({ label: item.preview, value: item.id }))
})
const localAlwaysCreateConversation = ref(false)
const localUseCronExpression = ref(false)
const localCronExpression = ref('')

const isEdit = computed(() => !!props.cron)

/* ---------------- 初始化 ---------------- */

const getHistoryList = async () => {
  try {
    const res = await window.api.getChatlist(cid.value)
    const raw_list = res.messages
    const chat_list: Array<{ id: string, preview: string }> = []

    for (const raw_chat of raw_list) {
      chat_list.push({
        id: String(raw_chat.conversation_uid),
        preview: raw_chat.title,
      })
    }
    return chat_list
  } catch (error) {
    console.error('[autoFetch] error:', error)
    ElMessage({
      type: 'warning',
      message: '获取会话历史失败',
    })
  }
}

const syncHistoryList = async (visible: boolean) => {
  if (!visible) return
  try {
    const list = await getHistoryList()
    if (list) {
      localHistoryList.value = list
    }
  } catch (error) {
    console.error('[syncHistoryList] error:', error)
  }
}

watch(
  () => props.cron,
  async (cron) => {
    if(cid.value === '') {
      await authStore.restore()
      cid.value = authStore.user?.user_uid || ''
    }

    if (cron) {
      await syncHistoryList(true)
      localAlwaysCreateConversation.value = Boolean(cron.extra_config?.always_create_conversation)
      localUseCronExpression.value = Boolean(cron.extra_config?.use_cron_expression)
      localCronExpression.value = cron.extra_config?.cron_expression || ''
      localHistoryId.value = cron.history_id
      localPlatform.value = cron.platform || 'default'
      localTaskName.value = cron.name
      localPrompt.value = cron.prompt || ''
      localExecute.value = cron.execute || ''
      localExecTime.value = cron.exec_time || ''
      localRepeat.value = cron.repeat || 'once'
      localDescription.value = cron.description || ''
    } else {
      localAlwaysCreateConversation.value = false
      localUseCronExpression.value = false
      localCronExpression.value = ''
      localHistoryId.value = ''
      localPlatform.value = 'default'
      localTaskName.value = ''
      localPrompt.value = ''
      localExecute.value = ''
      localExecTime.value = ''
      localRepeat.value = 'once'
      localDescription.value = ''
    }

  },
  { immediate: true }
)

const handleCreateConversation = async () => {
  try {
    const conversationTitle = (
      await InputDialog.open('请输入一个会话标题', '新建会话', {
        defaultValue: '',
        confirmButtonText: '下一步'
      })
    ).trim()

    let selectedWorkspace = ''

    const result = await window.api.openFileDialog(
      'folder',
      [],
      '选择一个工作目录'
    )

    if (!result.canceled && result.filePaths.length !== 0) {
      selectedWorkspace = result.filePaths[0]
    }

    const hid = await createConversation(
      conversationTitle,
      selectedWorkspace
    )

    store.setWorkDir(hid, selectedWorkspace)

    await syncHistoryList(true)
    localHistoryId.value = hid
  } catch {
    // User cancelled
  }
}

const createConversation = async (conversationTitle: string, workspace: string) => {
  const res = await window.api.newChat(cid.value, workspace ?? "", conversationTitle)
  return String(res.messages)
}

const selectPythonFile = async () => {
    const result = await window.api.openFileDialog(
      'file',
      ['.py'],
      '选择一个Python文件'
    )

    if (result.canceled || result.filePaths.length === 0) {
      return
    }

    localExecute.value = "file://"+result.filePaths[0]
}

const selectDir = async () => {
    const result = await window.api.openFileDialog('folder')

    if (result.canceled || result.filePaths.length === 0) {
      return
    }

    localHistoryId.value = "dir://"+result.filePaths[0]
}

/* ---------------- 校验 ---------------- */

const canSave = computed(() =>
  (localHistoryId.value.trim() || localAlwaysCreateConversation) &&
  localPlatform.value.trim() &&
  localTaskName.value.trim() &&
  (localExecTime.value.trim() || (localUseCronExpression && localCronExpression.value.trim())) &&
  (localRepeat.value.trim() || localUseCronExpression)
)

/* ---------------- Methods ---------------- */

const handleCancel = () => {
  visible.value = false
}

const handleSave = () => {

  if (!canSave.value) return

  let parsedRepeat = localRepeat.value
  if (localUseCronExpression.value) {
    parsedRepeat = 'cron'
  }

  const payload = {
    is_editing: isEdit.value,

    task_id: props.cron?.task_id,
    history_id: localHistoryId.value || '',
    platform: localPlatform.value.platform || 'default',
    task_name: localTaskName.value.trim(),
    prompt: localPrompt.value.trim(),
    execute: localExecute.value.trim(),
    exec_time: localExecTime.value,
    repeat: parsedRepeat,
    description: localDescription.value.trim(),
    extra_config: {
      always_create_conversation: localAlwaysCreateConversation.value,
      use_cron_expression: localUseCronExpression.value,
      cron_expression: localCronExpression.value
    },
  }

  emit('save', payload)
  visible.value = false
}

onMounted(async () => {
  try {
    if(cid.value === '') {
      await authStore.restore()
      cid.value = authStore.user?.user_uid || ''
    }
  } catch (err) {
    console.error('[Task page onMounted error]:', err)
  }
})
</script>


<style scoped>
.edit-dialog-mask {
  position: absolute;
  width: 100%;
  height: 100%;
  max-width: 100%;
  inset: 0;
  z-index: 9999;

  display: flex;
  align-items: center;
  justify-content: center;

  border-radius: var(--apix-border-radius-base);
  overflow: hidden;

  background: var(--apix-mask-background);
  backdrop-filter: saturate(180%) blur(6px);
  animation: opacityFadeIn 0.5s var(--apix-cubic-bezier);
}

@keyframes opacityFadeIn {
  0% { 
    opacity: 0.3; 
  }
  100% { 
    opacity: 1; 
  }
}

/* ---------------- Dialog Base ---------------- */
:deep(.el-overlay) {
  background-color: transparent;
}

:deep(.el-overlay-dialog) {
  background-color: transparent;
  overflow: hidden !important;
  scrollbar-width: none !important;
}

:deep(.cron-dialog) {
  border-radius: var(--apix-panel-border-radius) !important;
  box-shadow: var(--apix-shadow-lg);
  
  max-height: calc(92vh - 30px);
  overflow: scroll !important;
  scrollbar-width: none !important;
}

:deep(.el-dialog) {
  --el-dialog-border-radius: 32px !important;
  overflow: hidden;
  margin-top: 3.5vh !important;
  background-color: var(--apix-panel-layer-5-background);
}

/* Header */
:deep(.cron-dialog .el-dialog__header) {
  padding: 20px 24px 16px;
  padding-top: 6px;
  margin-right: 0;
  border-bottom: 1px solid var(--apix-default-light-color);
  background: transparent;
}

:deep(.cron-dialog .el-dialog__title) {
  font-size: 16px;
  font-weight: 600;
  color: var(--apix-default-dark-color);
  letter-spacing: 0.3px;
}

/* Close button */
:deep(.cron-dialog .el-dialog__headerbtn) {
  top: 18px;
  right: 20px;
  width: 28px;
  height: 28px;
  
  border-radius: var(--apix-button-border-radius);
  color: var(--apix-default-dark-color);

  border: none;
  cursor: pointer;
  font-size: 18px;
  line-height: 1;

  background: var(--apix-default-light-color);
}

:deep(.cron-dialog .el-dialog__headerbtn:hover) {
  color: var(--apix-danger-color);
  background: var(--apix-danger-light);
}

:deep(.cron-dialog .el-dialog__headerbtn .el-dialog__close) {
  font-size: 16px;
  transition: color 0.2s ease;
}

:deep(.cron-dialog .el-dialog__headerbtn:hover .el-dialog__close) {
  color: var(--apix-danger-color);
}

/* Body */
:deep(.cron-dialog .el-dialog__body) {
  padding: 24px;
  background: transparent;
}

/* Footer */
:deep(.cron-dialog .el-dialog__footer) {
  padding: 16px 24px 24px;
  padding-bottom: 8px;
  border-top: 1px solid var(--apix-default-light-color);
  background: transparent;
}

/* ---------------- Form ---------------- */

.form-wrapper {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.info-tag {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-direction: row;
  font-size: 12px;
  color: var(--apix-tertiary-dark-color);
}

.form-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

/* Label */
.label {
  font-size: 13px;
  font-weight: 600;
  color: var(--apix-default-dark-color);
  border-left: 3px solid var(--apix-primary-color);
  padding-left: 10px;
}

.exec-time-label,
.select-python-label,
.bind-conversation-label {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.select-python {
  font-size: 13px;
  color: var(--apix-primary-color);
  border: none;
  background: transparent;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 4px;
}

.select-python:hover {
  text-decoration: underline;
}

:deep(.el-checkbox) {
  height: 20px !important;
}

:deep(.el-checkbox__label) {
  font-size: 13px !important;
  font-weight: 400;
  color: var(--apix-tertiary-dark-color);
}

.always-create-conversation {
  font-size: 12px !important;
  color: var(--apix-primary-color);
  border: none;
  background: transparent;
  cursor: pointer;
}

.conversation-select-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-direction: row;
  transition: opacity 0.2s ease;
}

.conversation-select-bar.enable {
  opacity: 0.6;
}

.refresh-btn {
  margin: 0 !important;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 105px;
  height: 36px;
  font-size: 14px;
  font-weight: bold;
  border-radius: var(--apix-button-border-radius);
  color: var(--apix-lightest-color);
  background: var(--apix-primary-color);
  transition: transform 0.2s var(--apix-cubic-bezier),
    background-color 0.2s var(--apix-cubic-bezier);
  border: none;
}

.refresh-btn:hover {
  background-color: var(--apix-primary-hover);
}

.refresh-btn:active {
  transform: scale(0.98);
  background-color: var(--apix-primary-active);
}

.repeat-group {
  display: flex;
  gap: 18px;
  flex-wrap: wrap;
}

/* ---------------- Input ---------------- */

/* 通用 input/select wrapper */
:deep(.el-input-tag__wrapper),
:deep(.el-input__wrapper),
:deep(.el-select__wrapper) {
  box-shadow: inset 0 0 0 1px var(--apix-default-light-color) !important;
  border-radius: var(--apix-button-border-radius) !important;
  padding: 4px 12px !important;
  background: transparent !important;
  transition: all 0.2s ease !important;
}
:deep(.el-input-tag__wrapper) {
  height: 38px;
  max-height: 38px;
  overflow: scroll;
}

/* hover */
:deep(.el-input-tag__wrapper:hover),
:deep(.el-input__wrapper:hover),
:deep(.el-select__wrapper:hover) {
  box-shadow: inset 0 0 0 1px var(--apix-default-light-color) !important;
}

/* focus */
:deep(.el-input-tag__wrapper.is-focused),
:deep(.el-input__wrapper.is-focus),
:deep(.el-select__wrapper.is-focus) {
  box-shadow: inset 0 0 0 2px var(--apix-primary-color) !important;
  background: transparent !important;
}

/* input text */
:deep(.el-input-tag__inner),
:deep(.el-input__inner) {
  color: var(--apix-primary-dark) !important;
  font-size: 14px !important;
}

/* password icon */
:deep(.el-input__password) {
  color: var(--apix-tertiary-dark-color) !important;
}

/* word count */
:deep(.el-input__count) {
  color: var(--apix-tertiary-dark-color) !important;
  font-size: 11px !important;
  background: transparent !important;
}

:deep(.el-input .el-input__count .el-input__count-inner) {
  background: transparent !important;
}

:deep(.el-tag.el-tag--info) {
  color: var(--apix-tertiary-dark-color) !important;
  background-color: var(--apix-default-light-color);
}

/* ---------------- Textarea ---------------- */

.textarea :deep(.el-textarea__inner) {
  box-shadow: inset 0 0 0 1px var(--apix-default-light-color) !important;
  border-radius: var(--apix-button-border-radius) !important;
  padding: 12px;
  background: transparent;
  color: var(--apix-primary-dark) !important;
  font-size: 14px;
  line-height: 1.6;
  transition: box-shadow 0.2s ease,
    color 0.2s ease;
}

.textarea :deep(.el-textarea__inner:hover) {
  box-shadow: inset 0 0 0 1px var(--apix-default-light-color) !important;
}

.textarea :deep(.el-textarea__inner:focus) {
  box-shadow: inset 0 0 0 2px var(--apix-primary-color) !important;
  background: transparent !important;
  outline: none;
}

/* 底部按钮区域 */
.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

/* 取消按钮 */
.cancel-btn {
  min-width: 80px;
  padding: 6px 16px;
  border-radius: var(--apix-button-border-radius);
  border: none;
  font-size: 14px;
  cursor: pointer;
  color: var(--apix-default-dark-color);
  background: transparent;
}

.cancel-btn:hover {
  color: var(--apix-primary-dark);
}

/* 保存按钮 - 主色 */
.save-btn {
  min-width: 80px;
  padding: 6px 16px;
  border-radius: var(--apix-button-border-radius);
  border: none;
  font-size: 14px;
  cursor: pointer;
  transition: opacity 0.2s var(--apix-cubic-bezier),
    color 0.2s var(--apix-cubic-bezier),
    background-color 0.2s var(--apix-cubic-bezier);

  background: color-mix(in srgb, var(--apix-lightest-color) 85%, transparent);
  color: var(--apix-darkest-color);
  box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--apix-darkest-color) 8%, transparent);
}

.save-btn:hover:not(:disabled) {
  background-color: color-mix(in srgb, var(--apix-lightest-color) 44.6%, transparent);
}

.save-btn:hover:disabled {
  color: var(--apix-darkest-color);
}

.save-btn:active:not(:disabled) {
  background-color: color-mix(in srgb, var(--apix-default-color) 44.6%, transparent);
}

.save-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  background-color: color-mix(in srgb, var(--apix-lightest-color) 44.6%, transparent);
}

/* ---------------- Selector ---------------- */

:deep(.el-select__wrapper) {
  height: 38px;
  box-shadow: inset 0 0 0 1px var(--apix-default-light-color) !important;
  border-radius: var(--apix-button-border-radius) !important;
  padding: 4px 12px !important;
  background: transparent !important;
  transition: all 0.2s ease !important;
}

:deep(.el-select__wrapper.is-focused) {
  box-shadow: inset 0 0 0 2px var(--apix-primary-color) !important;
  background: transparent !important;
}

:deep(.el-select__wrapper .el-tooltip__trigger .el-tooltip__trigger) {
  display: block !important;
  opacity: 1 !important;
}

:deep(.el-select__selected-item.el-select__placeholder) {
  color:var(--apix-primary-color);
}

:deep(.el-select__selected-item.el-select__placeholder.is-transparent) {
  color:var(--el-text-color-placeholder);
  opacity: 0.6;
}

:deep(.el-slider__button) {
  background-color:var(--apix-primary-light);
  border: 2px solid var(--apix-primary-active);
  border-radius: var(--apix-button-border-radius);
}

:deep(.el-slider__button:hover) {
  width: 24px;
  transform: none;
}

:deep(.el-popper:deep(*)) {
  color: transparent;
}

span.el-popper__arrow {
  display: none;
}

:deep(.el-slider__button:active) {
  transform: scale(1.2);
  overflow: hidden;
  border: 2px solid color-mix(in srgb, var(--apix-primary-color) 25%, transparent);
  -webkit-backdrop-filter: saturate(180%) blur(16px);
  backdrop-filter: saturate(180%) blur(3px);
  transition: all 0.3s var(--apix-cubic-bezier);
  background-color: color-mix(in srgb, var(--apix-panel-base-layer-background) 30%, transparent);
  color: var(--apix-info-dark-text);
}
</style>