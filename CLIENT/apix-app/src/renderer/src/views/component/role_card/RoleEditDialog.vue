<template>
  <el-dialog
    v-model="visible"
    :title="isEdit ? '编辑角色卡' : '新建角色卡'"
    width="520px"
    destroy-on-close
    class="role-dialog"
    :close-on-click-modal="false"
  >
    <div class="form-wrapper">
      <!-- 角色名称 -->
      <div class="form-item">
        <div class="label">角色名称</div>
        <el-input
          v-model="localName"
          placeholder="请输入角色名称"
          maxlength="50"
          show-word-limit
          class="role-input"
        />
      </div>

      <!-- 角色定义 -->
      <div class="form-item">
        <div class="label">角色定义</div>
        <el-input
          v-model="localDefinition"
          type="textarea"
          :rows="6"
          placeholder="请输入角色行为定义"
          class="role-textarea"
          resize="none"
        />
        <div class="char-counter">
          {{ charCount }} 字符 · 约 {{ approxTokens }} tokens
        </div>
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
  role?: {
    id: string
    name: string
    definition: string
    enabled: boolean
  } | null
}>()

/* ---------------- Emits ---------------- */
const emit = defineEmits<{
  (e: 'update:modelValue', val: boolean): void
  (e: 'save', role: {
    id: number
    name: string
    definition: string
    enabled: boolean
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
const localDefinition = ref('')
const localEnabled = ref(false)

const isEdit = computed(() => !!props.role)

/* 当打开弹窗时初始化 */
watch(
  () => props.role,
  (role) => {
    if (role) {
      localName.value = role.name
      localDefinition.value = role.definition
      localEnabled.value = role.enabled
    } else {
      localName.value = ''
      localDefinition.value = ''
      localEnabled.value = false
    }
  },
  { immediate: true }
)

/* ---------------- 字符统计 ---------------- */
const charCount = computed(() => localDefinition.value.length)
const approxTokens = computed(() =>
  Math.ceil(localDefinition.value.length / 4)
)

/* ---------------- Methods ---------------- */
const handleCancel = () => {
  visible.value = false
}

const handleSave = () => {
  if (!localName.value.trim()) return

  const roleData = {
    id: props.role?.id ?? Date.now(),
    name: localName.value.trim(),
    definition: localDefinition.value.trim(),
    enabled: props.role?.enabled ?? false,
  }

  emit('save', roleData)
  visible.value = false
}
</script>

<style scoped>
/* 弹窗整体样式覆盖 */
:deep(.role-dialog) {
  border-radius: 32px !important;
  overflow: hidden;
}
:deep(.el-dialog) {
  --el-dialog-border-radius: 32px !important;
  overflow: hidden;
}

:deep(.role-dialog .el-dialog__header) {
  padding: 20px 24px 16px;
  margin-right: 0;
  border-bottom: 1px solid rgba(136, 202, 197, 0.2);
  background: rgba(255, 255, 255, 0.8);
}

:deep(.role-dialog .el-dialog__title) {
  font-size: 15px;
  font-weight: 600;
  color: #2f3a3a;
  letter-spacing: 0.3px;
}

:deep(.role-dialog .el-dialog__headerbtn) {
  top: 20px;
  right: 20px;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  transition: all 0.2s ease;
}

:deep(.role-dialog .el-dialog__headerbtn:hover) {
  background: rgba(136, 202, 197, 0.1);
}

:deep(.role-dialog .el-dialog__headerbtn .el-dialog__close) {
  color: #5a6a6a;
  font-size: 16px;
  transition: color 0.2s ease;
}

:deep(.role-dialog .el-dialog__headerbtn:hover .el-dialog__close) {
  color: rgb(136, 202, 197);
}

:deep(.role-dialog .el-dialog__body) {
  padding: 24px;
  background: rgba(255, 255, 255, 0.6);
  backdrop-filter: blur(10px);
}

:deep(.role-dialog .el-dialog__footer) {
  padding: 16px 24px 24px;
  border-top: 1px solid rgba(136, 202, 197, 0.15);
  background: rgba(255, 255, 255, 0.8);
}

/* 表单容器 */
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
  padding-left: 4px;
  border-left: 3px solid rgb(136, 202, 197);
  padding-left: 10px;
}

/* 输入框样式统一 */
.role-input :deep(.el-input__wrapper) {
  box-shadow: inset 0 0 0 1px rgba(0, 0, 0, 0.08);
  border-radius: 10px;
  padding: 4px 12px;
  background: rgba(255, 255, 255, 0.7);
  transition: all 0.2s ease;
}

.role-input :deep(.el-input__wrapper:hover) {
  box-shadow: inset 0 0 0 1px rgba(136, 202, 197, 0.5);
}

.role-input :deep(.el-input__wrapper.is-focus) {
  box-shadow: inset 0 0 0 2px rgb(136, 202, 197);
  background: rgba(255, 255, 255, 0.9);
}

.role-input :deep(.el-input__inner) {
  color: #2f3a3a;
  font-size: 14px;
}

.role-input :deep(.el-input__count) {
  color: #8a9595;
  font-size: 11px;
  background: transparent;
}

/* 文本域样式 */
.role-textarea :deep(.el-textarea__inner) {
  box-shadow: inset 0 0 0 1px rgba(0, 0, 0, 0.08);
  border-radius: 10px;
  padding: 12px;
  background: rgba(255, 255, 255, 0.7);
  color: #2f3a3a;
  font-size: 14px;
  line-height: 1.6;
  transition: all 0.2s ease;
}

.role-textarea :deep(.el-textarea__inner:hover) {
  box-shadow: inset 0 0 0 1px rgba(136, 202, 197, 0.5);
}

.role-textarea :deep(.el-textarea__inner:focus) {
  box-shadow: inset 0 0 0 2px rgb(136, 202, 197);
  background: rgba(255, 255, 255, 0.9);
  outline: none;
}

/* 字符计数器 */
.char-counter {
  text-align: right;
  font-size: 11px;
  color: #8a9595;
  margin-top: 6px;
  padding-right: 4px;
  font-weight: 500;
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