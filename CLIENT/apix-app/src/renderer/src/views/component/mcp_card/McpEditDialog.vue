<template>
  <div class="edit-dialog-mask">
    <el-dialog
      v-model="visible"
      :title="isEdit ? '编辑 MCP' : '新建 MCP'"
      width="620px"
      destroy-on-close
      class="mcp-dialog selectable"
      :close-on-click-modal="false"
    >
      <div class="form-wrapper">
        <div class="info-tag">
          <svg
            t="1777748237891"
            class="icon"
            viewBox="0 0 1024 1024"
            version="1.1"
            xmlns="http://www.w3.org/2000/svg"
            width="20"
            height="20"
          >
            <path
              d="M512 64C264.6 64 64 264.6 64 512s200.6 448 448 448 448-200.6 448-448S759.4 64 512 64z m0 820c-205.4 0-372-166.6-372-372s166.6-372 372-372 372 166.6 372 372-166.6 372-372 372z"
              fill="var(--apix-tertiary-dark-color)"
            />
            <path
              d="M512 688m-48 0a48 48 0 1 0 96 0 48 48 0 1 0-96 0Z"
              fill="var(--apix-tertiary-dark-color)"
            />
            <path
              d="M488 576h48c4.4 0 8-3.6 8-8V296c0-4.4-3.6-8-8-8h-48c-4.4 0-8 3.6-8 8v272c0 4.4 3.6 8 8 8z"
              fill="var(--apix-tertiary-dark-color)"
            />
          </svg>
          <div>
            请根据实际 MCP 服务填写连接信息。stdio 用于本地进程，streamable_http、websocket、sse 用于远程 MCP 服务。
          </div>
        </div>

        <div class="form-item">
          <div class="label">MCP 名称</div>
          <el-input
            v-model="localName"
            placeholder="Filesystem MCP"
            maxlength="50"
            show-word-limit
            class="input"
          />
        </div>

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

        <div class="form-item">
          <div class="label">生命周期</div>
          <el-radio-group
            v-model="localLifecycle"
            class="transport-group"
          >
            <el-radio label="keep_alive" title="保持session连接，在下次唤醒Agent时仍能够复用session">Keep alive</el-radio>
            <el-radio label="always_close" title="保持无状态，不复用session">Always close immediately</el-radio>
          </el-radio-group>
        </div>

        <div class="form-item">
          <div class="label">Transport</div>
          <el-radio-group
            v-model="localTransport"
            class="transport-group"
          >
            <el-radio label="stdio">stdio</el-radio>
            <el-radio label="streamable_http">streamable_http</el-radio>
            <el-radio label="websocket">websocket</el-radio>
            <el-radio label="sse">sse</el-radio>
          </el-radio-group>
        </div>

        <!-- stdio -->
        <template v-if="localTransport === 'stdio'">
          <div class="form-item">
            <div class="label">Command</div>
            <el-input
              v-model="localCommand"
              placeholder="请输入进程启动命令，如python、npx等"
              class="input"
            />
          </div>

          <div class="form-item">
            <div class="label model-list-label">
              Args
              <div class="mini-hint">按回车添加</div>
            </div>
            <el-input-tag
              v-model="localArgs"
              placeholder="请输入启动参数"
              aria-label="输入后请按回车确认"
              class="input-tag"
            />
          </div>

          <div class="form-item">
            <div class="label">Environment</div>
            <el-input
              v-model="localEnvText"
              type="textarea"
              :rows="4"
              placeholder='{"TOKEN":"xxx"}'
              class="textarea"
              resize="none"
            />
          </div>

          <div class="form-item">
            <div class="label">Working Directory</div>
            <el-input
              v-model="localCwd"
              placeholder="为MCP服务指定工作目录，此项将会影响相对路径计算等"
              class="input"
            />
          </div>

          <div class="form-item">
            <div class="label">Encoding</div>
            <el-input
              v-model="localEncoding"
              placeholder="utf-8"
              class="input"
            />
          </div>

          <div
            class="form-item"
          >
            <div class="label">Session Kwargs</div>
            <el-input
              v-model="localSessionKwargsText"
              type="textarea"
              :rows="4"
              placeholder='{"ssl": false}'
              class="textarea"
              resize="none"
            />
          </div>
        </template>

        <!-- remote -->
        <template v-else>
          <div class="form-item">
            <div class="label">URL</div>
            <el-input
              v-model="localUrl"
              placeholder="https://mcp.example.com/mcp"
              class="input"
            />
          </div>

          <div
            v-if="localTransport === 'streamable_http' || localTransport === 'sse'"
            class="form-item"
          >
            <div class="label">Headers</div>
            <el-input
              v-model="localHeadersText"
              type="textarea"
              :rows="4"
              placeholder='{"Authorization":"Bearer xxx"}'
              class="textarea"
              resize="none"
            />
          </div>

          <div
            class="form-item"
          >
            <div class="label">Session Kwargs</div>
            <el-input
              v-model="localSessionKwargsText"
              type="textarea"
              :rows="4"
              placeholder='{"ssl": false}'
              class="textarea"
              resize="none"
            />
          </div>

          <div
            v-if="localTransport === 'streamable_http'"
            class="form-item"
          >
            <el-checkbox v-model="localTerminateOnClose">Terminate on Close</el-checkbox>
          </div>
        </template>
      </div>

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
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'

type McpTransport = 'stdio' | 'streamable_http' | 'websocket' | 'sse'

interface McpConfig {
  command?: string
  args?: string[]
  env?: Record<string, string>
  lifecycle?: string

  cwd?: string
  encoding?: string

  url?: string

  headers?: Record<string, string>

  session_kwargs?: Record<string, any>
  terminate_on_close?: boolean
}

interface McpDialogItem {
  mcp_id: string
  name: string
  description: string
  transport: McpTransport
  config?: McpConfig
}

const props = defineProps<{
  modelValue: boolean
  mcp?: McpDialogItem | null
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', val: boolean): void
  (e: 'save', payload: {
    is_editing: boolean
    mcp_id?: string

    name: string
    description: string

    transport: McpTransport

    config: McpConfig
  }): void
}>()

const visible = ref(props.modelValue)

watch(() => props.modelValue, val => { visible.value = val })
watch(visible, val => { emit('update:modelValue', val) })

const localName = ref('')
const localDescription = ref('')
const localTransport = ref<McpTransport>('stdio')
const localLifecycle = ref<McpTransport>('keep_alive')

const localCommand = ref('')
const localArgs = ref<string[]>([])
const localEnvText = ref('{}')
const localCwd = ref('')
const localEncoding = ref('utf-8')

const localUrl = ref('')
const localHeadersText = ref('{}')
const localSessionKwargsText = ref('{}')
const localTerminateOnClose = ref(false)

const isEdit = computed(() => !!props.mcp)

const canSave = computed(() => {
  if (!localName.value.trim()) return false
  if (localTransport.value === 'stdio') return !!localCommand.value.trim()
  return !!localUrl.value.trim()
})

watch(() => props.mcp, mcp => {
  if (!mcp) {
    resetForm()
    return
  }

  localName.value = mcp.name || ''
  localDescription.value = mcp.description || ''
  localTransport.value = mcp.transport || 'stdio'

  const config = mcp.config || {}

  localLifecycle.value = config.lifecycle ?? 'keep_alive'
  localCommand.value = config.command ?? ''
  localArgs.value = Array.isArray(config.args) ? [...config.args] : []
  localEnvText.value = stringifyJson(config.env ?? {})
  localCwd.value = config.cwd ?? ''
  localEncoding.value = config.encoding ?? 'utf-8'
  localUrl.value = config.url ?? ''
  localTerminateOnClose.value = config.terminate_on_close ?? false
  localHeadersText.value = stringifyJson(config.headers ?? {})
  localSessionKwargsText.value = stringifyJson(config.session_kwargs ?? {})
}, { immediate: true })

function resetForm() {
  localName.value = ''
  localDescription.value = ''
  localTransport.value = 'stdio'
  localCommand.value = ''
  localArgs.value = []
  localEnvText.value = '{}'
  localCwd.value = ''
  localEncoding.value = 'utf-8'
  localUrl.value = ''
  localHeadersText.value = '{}'
  localSessionKwargsText.value = '{}'
}

function parseJsonObject(text: string, fallback: Record<string, string> = {}) {
  const trimmed = text.trim()
  if (!trimmed) return fallback

  const parsed = JSON.parse(trimmed)
  if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
    return parsed as Record<string, string>
  }
  throw new Error('JSON must be an object')
}

function parseJson(text: string, fallback: any = {}) {
  const trimmed = text.trim()
  if (!trimmed) return fallback
  return JSON.parse(trimmed)
}

function stringifyJson(value: unknown) {
  try {
    return JSON.stringify(value ?? {}, null, 2)
  } catch {
    return '{}'
  }
}

const handleCancel = () => {
  visible.value = false
}

const handleSave = () => {
  if (!canSave.value) return

  try {
    const config: McpConfig = {}

    if (localTransport.value === 'stdio') {
      config.command = localCommand.value.trim()
      config.args = [...localArgs.value]
      config.env = parseJsonObject(localEnvText.value, {})
      config.session_kwargs = parseJson(localSessionKwargsText.value, {})
      config.lifecycle = localLifecycle.value

      if (localCwd.value.trim()) {
        config.cwd = localCwd.value.trim()
      }
      if (localEncoding.value.trim()) {
        config.encoding = localEncoding.value.trim()
      }
    } else {
      config.url = localUrl.value.trim()

      if (localTransport.value === 'streamable_http' || localTransport.value === 'sse') {
        config.headers = parseJsonObject(localHeadersText.value, {})
      }
      if (localTransport.value === 'streamable_http') {
        config.terminate_on_close = localTerminateOnClose.value
      }
    }

    emit('save', {
      is_editing: isEdit.value,
      mcp_id: props.mcp?.mcp_id,
      name: localName.value.trim(),
      description: localDescription.value.trim(),
      transport: localTransport.value,
      config,
    })

    visible.value = false
  } catch (error) {
    console.error('[McpEditDialog] save failed:', error)
    ElMessage({
      type: 'warning',
      message: 'JSON 格式不正确，请检查配置项',
      plain: true,
    })
  }
}
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

:deep(.el-overlay) {
  background-color: transparent;
}

:deep(.el-overlay-dialog) {
  background-color: transparent;
  overflow: hidden !important;
  scrollbar-width: none !important;
}

:deep(.mcp-dialog) {
  border-radius: var(--apix-panel-border-radius) !important;
  overflow: hidden;
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

:deep(.mcp-dialog .el-dialog__header) {
  padding: 20px 24px 16px;
  padding-top: 6px;
  margin-right: 0;
  border-bottom: 1px solid var(--apix-default-light-color);
  background: transparent;
}

:deep(.mcp-dialog .el-dialog__title) {
  font-size: 16px;
  font-weight: 600;
  color: var(--apix-default-dark-color);
  letter-spacing: 0.3px;
}

:deep(.mcp-dialog .el-dialog__headerbtn) {
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

:deep(.mcp-dialog .el-dialog__headerbtn:hover) {
  color: var(--apix-danger-color);
  background: var(--apix-danger-light);
}

:deep(.mcp-dialog .el-dialog__headerbtn .el-dialog__close) {
  font-size: 16px;
  transition: color 0.2s ease;
}

:deep(.mcp-dialog .el-dialog__headerbtn:hover .el-dialog__close) {
  color: var(--apix-danger-color);
}

:deep(.mcp-dialog .el-dialog__body) {
  padding: 24px;
  background: transparent;
}

:deep(.mcp-dialog .el-dialog__footer) {
  padding: 16px 24px 24px;
  padding-bottom: 8px;
  border-top: 1px solid var(--apix-default-light-color);
  background: transparent;
}

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

.label {
  font-size: 13px;
  font-weight: 600;
  color: var(--apix-default-dark-color);
  border-left: 3px solid var(--apix-primary-color);
  padding-left: 10px;
}

.transport-group {
  display: flex;
  gap: 18px;
  flex-wrap: wrap;
}

:deep(.el-input-tag__wrapper),
.input :deep(.el-input__wrapper),
.input :deep(.el-select__wrapper) {
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

:deep(.el-input-tag__wrapper:hover),
.input :deep(.el-input__wrapper:hover),
.input :deep(.el-select__wrapper:hover) {
  box-shadow: inset 0 0 0 1px var(--apix-default-light-color) !important;
}

:deep(.el-input-tag__wrapper.is-focused),
.input :deep(.el-input__wrapper.is-focus),
.input :deep(.el-select__wrapper.is-focus) {
  box-shadow: inset 0 0 0 2px var(--apix-primary-color) !important;
  background: transparent !important;
}

.input-tag :deep(.el-input-tag__inner),
.input :deep(.el-input__inner) {
  color: var(--apix-primary-dark) !important;
  font-size: 14px !important;
}

.input :deep(.el-input__password) {
  color: var(--apix-tertiary-dark-color) !important;
}

.input :deep(.el-input__count) {
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

.textarea :deep(.el-textarea__inner) {
  box-shadow: inset 0 0 0 1px var(--apix-default-light-color) !important;
  border-radius: var(--apix-button-border-radius) !important;
  padding: 12px;
  background: transparent;
  color: var(--apix-primary-dark) !important;
  font-size: 14px;
  line-height: 1.6;
  transition: all 0.2s ease;
}

.textarea :deep(.el-textarea__inner:hover) {
  box-shadow: inset 0 0 0 1px var(--apix-default-light-color) !important;
}

.textarea :deep(.el-textarea__inner:focus) {
  box-shadow: inset 0 0 0 2px var(--apix-primary-color) !important;
  background: transparent !important;
  outline: none;
}

.model-list-label {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.mini-hint {
  font-size: 11px;
  font-weight: 400;
  color: var(--apix-tertiary-dark-color);
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

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
</style>
