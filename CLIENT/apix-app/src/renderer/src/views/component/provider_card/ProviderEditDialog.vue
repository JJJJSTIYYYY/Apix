<template>
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
        <svg t="1777748237891" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="5587" width="20" height="20"><path d="M512 64C264.6 64 64 264.6 64 512s200.6 448 448 448 448-200.6 448-448S759.4 64 512 64z m0 820c-205.4 0-372-166.6-372-372s166.6-372 372-372 372 166.6 372 372-166.6 372-372 372z" p-id="5588" fill="#707070"></path><path d="M512 688m-48 0a48 48 0 1 0 96 0 48 48 0 1 0-96 0Z" p-id="5589" fill="#707070"></path><path d="M488 576h48c4.4 0 8-3.6 8-8V296c0-4.4-3.6-8-8-8h-48c-4.4 0-8 3.6-8 8v272c0 4.4 3.6 8 8 8z" p-id="5590" fill="#707070"></path></svg>
        <div>不同的模型供应商所采用的协议可能存在差异，有可能引发工具调用失败、无法进行深度思考，甚至出现报错等异常情况</div>
      </div>

      <!-- 名称 -->
      <div class="form-item">
        <div class="label">名称</div>
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
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue'

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
/* ---------------- Dialog Base ---------------- */
:deep(.provider-dialog) {
  border-radius: 32px !important;
  overflow: hidden;
}

:deep(.el-dialog) {
  --el-dialog-border-radius: 32px !important;
  overflow: hidden;
}

/* Header */
:deep(.provider-dialog .el-dialog__header) {
  padding: 20px 24px 16px;
  margin-right: 0;
  border-bottom: 1px solid rgba(136, 202, 197, 0.2);
  background: rgba(255, 255, 255, 0.8);
}

:deep(.provider-dialog .el-dialog__title) {
  font-size: 15px;
  font-weight: 600;
  color: #2f3a3a;
  letter-spacing: 0.3px;
}

/* Close button */
:deep(.provider-dialog .el-dialog__headerbtn) {
  top: 20px;
  right: 20px;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  transition: all 0.2s ease;
}

:deep(.provider-dialog .el-dialog__headerbtn:hover) {
  background: rgba(136, 202, 197, 0.1);
}

:deep(.provider-dialog .el-dialog__headerbtn .el-dialog__close) {
  color: #5a6a6a;
  font-size: 16px;
  transition: color 0.2s ease;
}

:deep(.provider-dialog .el-dialog__headerbtn:hover .el-dialog__close) {
  color: rgb(136, 202, 197);
}

/* Body */
:deep(.provider-dialog .el-dialog__body) {
  padding: 24px;
  background: rgba(255, 255, 255, 0.6);
  backdrop-filter: blur(10px);
}

/* Footer */
:deep(.provider-dialog .el-dialog__footer) {
  padding: 16px 24px 24px;
  border-top: 1px solid rgba(136, 202, 197, 0.15);
  background: rgba(255, 255, 255, 0.8);
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
  font-weight: 400;
  color: #2f3a3ac3;
  padding-left: 10px;
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
  color: #2f3a3a;
  border-left: 3px solid rgb(136, 202, 197);
  padding-left: 10px;
}

/* ---------------- Icon ---------------- */

.icon-wrapper {
  display: flex;
  justify-content: center;
  margin-bottom: 6px;
}

.provider-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
}

/* ---------------- Input ---------------- */

/* 通用 input/select wrapper */
:deep(.el-input-tag__wrapper),
.input :deep(.el-input__wrapper),
.input :deep(.el-select__wrapper) {
  box-shadow: inset 0 0 0 1px rgba(0, 0, 0, 0.08) !important;
  border-radius: 10px !important;
  padding: 4px 12px !important;
  background: rgba(255, 255, 255, 0.7) !important;
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
  box-shadow: inset 0 0 0 1px rgba(136, 202, 197, 0.5) !important;
}

/* focus */
:deep(.el-input-tag__wrapper.is-focused),
.input :deep(.el-input__wrapper.is-focus),
.input :deep(.el-select__wrapper.is-focus) {
  box-shadow: inset 0 0 0 2px rgb(136, 202, 197) !important;
  background: rgba(255, 255, 255, 0.9) !important;
}

/* input text */
.input-tag :deep(.el-input-tag__inner),
.input :deep(.el-input__inner) {
  color: #2f3a3a !important;
  font-size: 14px !important;
}

/* password icon */
.input :deep(.el-input__suffix) {
  color: #8a9595 !important;
}

/* word count */
.input :deep(.el-input__count) {
  color: #8a9595 !important;
  font-size: 11px !important;
  background: transparent !important;
}

/* ---------------- Textarea ---------------- */

.textarea :deep(.el-textarea__inner) {
  box-shadow: inset 0 0 0 1px rgba(0, 0, 0, 0.08);
  border-radius: 10px;
  padding: 12px;
  background: rgba(255, 255, 255, 0.7);
  color: #2f3a3a;
  font-size: 14px;
  line-height: 1.6;
  transition: all 0.2s ease;
}

.textarea :deep(.el-textarea__inner:hover) {
  box-shadow: inset 0 0 0 1px rgba(136, 202, 197, 0.5);
}

.textarea :deep(.el-textarea__inner:focus) {
  box-shadow: inset 0 0 0 2px rgb(136, 202, 197);
  background: rgba(255, 255, 255, 0.9);
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
  color: rgb(0, 173, 155);
  border: none;
  background: transparent;
  cursor: pointer;
  transition: all 0.2s ease;
}

.auto-get:hover {
  color: rgb(0, 173, 155);
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
  border-radius: 8px;
  padding: 8px 20px;
  color: #5a6a6a;
  border: 1px solid rgba(0, 0, 0, 0.1);
  background: rgba(255, 255, 255, 0.6);
  transition: all 0.2s ease;
}

.cancel-btn:hover {
  color: #2f3a3a;
  border-color: rgba(136, 202, 197, 0.4);
  background: rgba(136, 202, 197, 0.08);
}

/* 保存按钮 - 主色 */
.save-btn {
  border-radius: 8px;
  padding: 8px 24px;
  background: rgb(136, 202, 197);
  border: none;
  color: #fff;
  font-weight: 500;
  transition: all 0.2s ease;
  box-shadow: 0 2px 8px rgba(136, 202, 197, 0.3);
}

.save-btn:hover:not(:disabled) {
  background: rgb(120, 185, 180);
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(136, 202, 197, 0.4);
}

.save-btn:active:not(:disabled) {
  transform: translateY(0);
  box-shadow: 0 2px 6px rgba(136, 202, 197, 0.3);
}

.save-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  background: rgba(136, 202, 197, 0.5);
}
</style>