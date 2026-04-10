<template>
  <el-dialog
    v-model="visible"
    title="编辑文档描述"
    width="520px"
    destroy-on-close
    class="rag-dialog"
    :close-on-click-modal="false"
  >
    <div class="form-wrapper">
      <!-- 文档名称（只读） -->
      <div class="form-item">
        <div class="label">文档名称</div>
        <el-input
          :model-value="props.rag?.name || ''"
          readonly
          class="rag-input is-readonly"
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
          class="rag-textarea"
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
:deep(.rag-dialog) {
  border-radius: 16px;
  overflow: hidden;
}

:deep(.rag-dialog .el-dialog__header) {
  padding: 20px 24px 16px;
  margin-right: 0;
  border-bottom: 1px solid rgba(136, 202, 197, 0.2);
  background: rgba(255, 255, 255, 0.8);
}

:deep(.rag-dialog .el-dialog__title) {
  font-size: 15px;
  font-weight: 600;
  color: #2f3a3a;
  letter-spacing: 0.3px;
}

:deep(.rag-dialog .el-dialog__headerbtn) {
  top: 20px;
  right: 20px;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  transition: all 0.2s ease;
}

:deep(.rag-dialog .el-dialog__headerbtn:hover) {
  background: rgba(136, 202, 197, 0.1);
}

:deep(.rag-dialog .el-dialog__headerbtn .el-dialog__close) {
  color: #5a6a6a;
  font-size: 16px;
  transition: color 0.2s ease;
}

:deep(.rag-dialog .el-dialog__headerbtn:hover .el-dialog__close) {
  color: rgb(136, 202, 197);
}

:deep(.rag-dialog .el-dialog__body) {
  padding: 24px;
  background: rgba(255, 255, 255, 0.6);
  backdrop-filter: blur(10px);
}

:deep(.rag-dialog .el-dialog__footer) {
  padding: 16px 24px 24px;
  border-top: 1px solid rgba(136, 202, 197, 0.15);
  background: rgba(255, 255, 255, 0.8);
}

.form-wrapper {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.form-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.label {
  font-size: 13px;
  font-weight: 600;
  color: #2f3a3a;
  border-left: 3px solid rgb(136, 202, 197);
  padding-left: 10px;
}

.rag-input :deep(.el-input__wrapper) {
  box-shadow: inset 0 0 0 1px rgba(0, 0, 0, 0.08);
  border-radius: 10px;
  padding: 4px 12px;
  background: rgba(255, 255, 255, 0.7);
  transition: all 0.2s ease;
}

.rag-input :deep(.el-input__inner) {
  color: #2f3a3a;
  font-size: 14px;
}

.is-readonly :deep(.el-input__wrapper) {
  background: rgba(245, 247, 250, 0.9);
  cursor: not-allowed;
}

.is-readonly :deep(.el-input__inner) {
  color: #7a8585;
  cursor: not-allowed;
}

.rag-textarea :deep(.el-textarea__inner) {
  box-shadow: inset 0 0 0 1px rgba(0, 0, 0, 0.08);
  border-radius: 10px;
  padding: 12px;
  background: rgba(255, 255, 255, 0.7);
  color: #2f3a3a;
  font-size: 14px;
  line-height: 1.6;
  transition: all 0.2s ease;
  font-family: inherit;
}

.rag-textarea :deep(.el-textarea__inner:hover) {
  box-shadow: inset 0 0 0 1px rgba(136, 202, 197, 0.5);
}

.rag-textarea :deep(.el-textarea__inner:focus) {
  box-shadow: inset 0 0 0 2px rgb(136, 202, 197);
  background: rgba(255, 255, 255, 0.9);
  outline: none;
}

.char-counter {
  text-align: right;
  font-size: 11px;
  color: #8a9595;
  margin-top: 6px;
  padding-right: 4px;
  font-weight: 500;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

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