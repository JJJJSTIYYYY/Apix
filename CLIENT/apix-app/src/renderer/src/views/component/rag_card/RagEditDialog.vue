<template>
  <div class="edit-dialog-mask">
    <el-dialog
      v-model="visible"
      title="编辑文档描述"
      width="520px"
      destroy-on-close
      class="rag-dialog selectable"
      :close-on-click-modal="false"
    >
      <div class="form-wrapper">
        <!-- 文档名称（只读） -->
        <div class="form-item">
          <div class="label">文档名称</div>
          <el-input
            :model-value="props.rag?.name || ''"
            readonly
            class="input is-readonly"
          />
        </div>

        <!-- 文档描述 -->
        <div class="form-item">
          <div class="label">文档描述</div>
          <el-input
            v-model="localDesc"
            type="textarea"
            :rows="6"
            placeholder="请输入文档描述"
            class="textarea"
            resize="none"
            maxlength="1000"
            show-word-limit
          />
          <div class="char-counter">
            {{ charCount }} 字符 · 约 {{ approxTokens }} tokens
          </div>
        </div>
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
            :disabled="!props.rag"
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

interface RagDocumentItem {
  client_id: string
  id: string
  name: string
  embeddingModel: string
  updatedAt: string
  size: string
  type: string
  desc: string
  indexed: boolean
  active: boolean
}

const props = defineProps<{
  modelValue: boolean
  rag?: RagDocumentItem | null
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', val: boolean): void
  (e: 'save', rag: RagDocumentItem): void
}>()

const visible = ref(props.modelValue)
const localDesc = ref('')

watch(
  () => props.modelValue,
  val => {
    visible.value = val
  }
)

watch(visible, val => {
  emit('update:modelValue', val)
})

watch(
  () => props.rag,
  (rag) => {
    if (rag) {
      localDesc.value = rag.desc || ''
    } else {
      localDesc.value = ''
    }
  },
  { immediate: true }
)

const charCount = computed(() => localDesc.value.length)
const approxTokens = computed(() => Math.ceil(localDesc.value.length / 4))

const handleCancel = () => {
  visible.value = false
}

const handleSave = () => {
  if (!props.rag) return

  emit('save', {
    ...props.rag,
    desc: localDesc.value.trim(),
  })

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

:deep(.rag-dialog) {
  border-radius: var(--apix-panel-border-radius) !important;
  overflow: hidden;
  box-shadow: var(--apix-shadow-lg);
}

:deep(.el-dialog) {
  --el-dialog-border-radius: 32px !important;
  overflow: hidden;
  margin-top: 18vh !important;
  background-color: var(--apix-panel-layer-5-background);
}

/* Header */
:deep(.rag-dialog .el-dialog__header) {
  padding: 20px 24px 16px;
  padding-top: 6px;
  margin-right: 0;
  border-bottom: 1px solid var(--apix-default-light-color);
  background: transparent;
}

:deep(.rag-dialog .el-dialog__title) {
  font-size: 16px;
  font-weight: 600;
  color: var(--apix-default-dark-color);
  letter-spacing: 0.3px;
}

/* Close button */
:deep(.rag-dialog .el-dialog__headerbtn) {
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

:deep(.rag-dialog .el-dialog__headerbtn:hover) {
  color: var(--apix-danger-color);
  background: var(--apix-danger-light);
}

:deep(.rag-dialog .el-dialog__headerbtn .el-dialog__close) {
  font-size: 16px;
  transition: color 0.2s ease;
}

:deep(.rag-dialog .el-dialog__headerbtn:hover .el-dialog__close) {
  color: var(--apix-danger-color);
}

/* Body */
:deep(.rag-dialog .el-dialog__body) {
  padding: 24px;
  background: transparent;
}

/* Footer */
:deep(.rag-dialog .el-dialog__footer) {
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

:deep(.el-textarea .el-input__count) {
  color: var(--apix-tertiary-dark-color) !important;
  font-size: 11px !important;
  background: transparent !important;
}

/* Auto Get */
.model-list-label {
  display: flex;
  justify-content: space-between;
  align-items: center;
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

.is-readonly :deep(.el-input__wrapper) {
  background: transparent;
  cursor: not-allowed;
}

.is-readonly :deep(.el-input__inner) {
  color: transparent;
  cursor: not-allowed;
}

.char-counter {
  text-align: right;
  font-size: 11px;
  color: #8a9595;
  margin-top: 6px;
  padding-right: 4px;
  font-weight: 500;
}
</style>