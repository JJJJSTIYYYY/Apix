<template>
  <div class="edit-dialog-mask">
    <el-dialog
      v-model="visible"
      :title="isEdit ? '编辑供应商' : '新建供应商'"
      width="560px"
      destroy-on-close
      class="provider-dialog selectable"
      :close-on-click-modal="false"
    >
      <div class="form-wrapper">

        <div class="info-tag">
          <svg t="1777748237891" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="5587" width="20" height="20"><path d="M512 64C264.6 64 64 264.6 64 512s200.6 448 448 448 448-200.6 448-448S759.4 64 512 64z m0 820c-205.4 0-372-166.6-372-372s166.6-372 372-372 372 166.6 372 372-166.6 372-372 372z" p-id="5588" fill="var(--apix-tertiary-dark-color)"></path><path d="M512 688m-48 0a48 48 0 1 0 96 0 48 48 0 1 0-96 0Z" p-id="5589" fill="var(--apix-tertiary-dark-color)"></path><path d="M488 576h48c4.4 0 8-3.6 8-8V296c0-4.4-3.6-8-8-8h-48c-4.4 0-8 3.6-8 8v272c0 4.4 3.6 8 8 8z" p-id="5590" fill="var(--apix-tertiary-dark-color)"></path></svg>
          <div>不同的模型供应商所采用的协议可能存在差异，有可能引发工具调用失败、无法进行深度思考，甚至出现报错等异常情况</div>
        </div>

        <!-- 名称 -->
        <div class="form-item">
          <div class="label">供应商名称</div>
          <el-input
            v-model="localName"
            placeholder="请输入自定义的供应商名称"
            maxlength="50"
            show-word-limit
            class="input"
          />
        </div>

        <!-- 类型 -->
        <div class="form-item">
          <div class="label">兼容协议</div>
          <el-input
            v-model="localType"
            placeholder="OpenAI"
            class="input"
            disabled
          />
        </div>

        <!-- Endpoint -->
        <div class="form-item">
          <div class="label">Endpoint</div>
          <el-input
            v-model="localEndpoint"
            placeholder="https://api.openai.com/v1"
            class="input"
          />
        </div>

        <!-- ApiKey -->
        <div class="form-item">
          <div class="label">API_Key</div>
          <el-input
            v-model="localApiKey"
            placeholder="sk-xxxx"
            class="input"
            type="password"
            show-password
          />
        </div>

        <!-- Model list -->
        <div class="form-item">
          <div class="label model-list-label">
            模型列表
            <div>
              <button class="auto-get" @click="autoFetch">+ 自动获取</button>
            </div>
          </div>
          <el-input-tag
            v-model="localModelList"
            placeholder="请输入支持的模型列表"
            aria-label="输入后请按回车确认"
            class="input-tag"
          />
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
            :disabled="!localName.trim()"
          >
            保存
          </el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { ElMessage } from 'element-plus'

/* ---------------- Props ---------------- */
const props = defineProps<{
  modelValue: boolean
  provider?: {
    provider_id: string
    name: string
    endpoint: string
    description: string
    type: string
    model_list: string[]
    api_key: string
  } | null
}>()

/* ---------------- Emits ---------------- */
const emit = defineEmits<{
  (e: 'update:modelValue', val: boolean): void
  (e: 'save', payload: {
    is_editing: boolean
    provider_id?: string
    name: string
    endpoint: string
    type: string
    description: string
    model_list: string[]
    api_key: string
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

/* ---------------- Local State ---------------- */

const localName = ref('')
const localType = ref('openai')
const localEndpoint = ref('')
const localModelList = ref<string[]>([])
const localDescription = ref('')
const localApiKey = ref('')

const isEdit = computed(() => !!props.provider)

/* ---------------- 初始化 ---------------- */

watch(
  () => props.provider,
  async (provider) => {

    if (provider) {

      localName.value = provider.name
      localType.value = provider.type || 'openai'
      localEndpoint.value = provider.endpoint
      localDescription.value = provider.description || ''
      localModelList.value = provider.model_list || []
      localApiKey.value = provider.api_key || ''
    } else {

      localName.value = ''
      localType.value = 'openai'
      localEndpoint.value = ''
      localDescription.value = ''
      localModelList.value = []
      localApiKey.value = ''
    }

  },
  { immediate: true }
)

/* ---------------- 校验 ---------------- */

const canSave = computed(() =>
  localName.value.trim() &&
  localEndpoint.value.trim() &&
  localModelList.value.length > 0
)

/* ---------------- Methods ---------------- */

const autoFetch = async () => {
  if (!localEndpoint.value.trim() || !localApiKey.value.trim()) {
    ElMessage({
      type: 'warning',
      message: '请先填写 Endpoint 和 API Key',
    })
    return
  }

  try {
    const models = await window.api.autoFetchModelList(localEndpoint.value.trim(), localApiKey.value.trim())

    if (Array.isArray(models)) {
      localModelList.value = models
      ElMessage({
        type: 'success',
        message: '模型列表已更新',
      })
    } else {
      ElMessage({
        type: 'warning',
        message: '获取失败，请手动填写',
      })
    }
  } catch (error) {
    console.error('[autoFetch] error:', error)
    ElMessage({
      type: 'warning',
      message: '获取失败，请手动填写或尝试重新获取',
    })
  }
}

const handleCancel = () => {
  visible.value = false
}

const handleSave = () => {

  if (!canSave.value) return

  const payload = {
    is_editing: isEdit.value,

    provider_id: props.provider?.provider_id,

    name: localName.value.trim(),
    endpoint: localEndpoint.value.trim(),
    type: localType.value,
    description: localDescription.value.trim(),
    model_list: localModelList.value,
    api_key: localApiKey.value.trim(),
  }

  emit('save', payload)
  visible.value = false
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

/* ---------------- Dialog Base ---------------- */
:deep(.el-overlay) {
  background-color: transparent;
}

:deep(.el-overlay-dialog) {
  background-color: transparent;
  overflow: hidden !important;
  scrollbar-width: none !important;
}

:deep(.provider-dialog) {
  border-radius: var(--apix-panel-border-radius) !important;
  overflow: hidden;
  box-shadow: var(--apix-shadow-lg);
}

:deep(.el-dialog) {
  --el-dialog-border-radius: 32px !important;
  overflow: hidden;
  margin-top: 5.5vh !important;
  background-color: var(--apix-panel-layer-5-background);
}

/* Header */
:deep(.provider-dialog .el-dialog__header) {
  padding: 20px 24px 16px;
  padding-top: 6px;
  margin-right: 0;
  border-bottom: 1px solid var(--apix-default-light-color);
  background: transparent;
}

:deep(.provider-dialog .el-dialog__title) {
  font-size: 16px;
  font-weight: 600;
  color: var(--apix-default-dark-color);
  letter-spacing: 0.3px;
}

/* Close button */
:deep(.provider-dialog .el-dialog__headerbtn) {
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

:deep(.provider-dialog .el-dialog__headerbtn:hover) {
  color: var(--apix-danger-color);
  background: var(--apix-danger-light);
}

:deep(.provider-dialog .el-dialog__headerbtn .el-dialog__close) {
  font-size: 16px;
  transition: color 0.2s ease;
}

:deep(.provider-dialog .el-dialog__headerbtn:hover .el-dialog__close) {
  color: var(--apix-danger-color);
}

/* Body */
:deep(.provider-dialog .el-dialog__body) {
  padding: 24px;
  background: transparent;
}

/* Footer */
:deep(.provider-dialog .el-dialog__footer) {
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

/* ---------------- Input ---------------- */

/* 通用 input/select wrapper */
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

/* hover */
:deep(.el-input-tag__wrapper:hover),
.input :deep(.el-input__wrapper:hover),
.input :deep(.el-select__wrapper:hover) {
  box-shadow: inset 0 0 0 1px var(--apix-default-light-color) !important;
}

/* focus */
:deep(.el-input-tag__wrapper.is-focused),
.input :deep(.el-input__wrapper.is-focus),
.input :deep(.el-select__wrapper.is-focus) {
  box-shadow: inset 0 0 0 2px var(--apix-primary-color) !important;
  background: transparent !important;
}

/* input text */
.input-tag :deep(.el-input-tag__inner),
.input :deep(.el-input__inner) {
  color: var(--apix-primary-dark) !important;
  font-size: 14px !important;
}

/* password icon */
.input :deep(.el-input__password) {
  color: var(--apix-tertiary-dark-color) !important;
}

/* word count */
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

/* ---------------- Textarea ---------------- */

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

/* Auto Get */
.model-list-label {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.auto-get {
  font-size: 12px;
  color: var(--apix-primary-color);
  border: none;
  background: transparent;
  cursor: pointer;
}

.auto-get:hover {
  text-decoration: underline;
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
</style>