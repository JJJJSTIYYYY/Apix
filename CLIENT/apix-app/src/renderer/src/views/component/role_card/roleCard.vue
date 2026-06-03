<template>
  <div class="role-card selectable">
    <!-- Header - 保持不动 -->
    <div class="role-header">
      <el-switch
        v-model="localEnabled"
        size="small"
        @change="handleToggle"
      />
      <div class="role-actions">
        <button
          class="icon-btn delete-btn"
          title="Delete Role"
          @click="handleDelete"
        >
          <el-icon><Delete /></el-icon>
        </button>
        <button
          class="icon-btn"
          title="Edit Role"
          @click="handleEdit"
        >
          <el-icon><Setting /></el-icon>
        </button>
      </div>
    </div>

    <!-- 内容区域 - 统一布局 -->
    <div class="role-content">
      <!-- Title -->
      <div class="role-title-wrapper">
        <div class="role-icon">
          <el-icon><UserFilled /></el-icon>
        </div>
        <div class="role-title" :title="roleName">
          {{ roleName }}
        </div>
      </div>

      <!-- Definition -->
      <div class="role-definition-wrapper">
        <div class="role-definition" :title="roleDefinition">
          {{ roleDefinition }}
        </div>
      </div>
    </div>

    <!-- Footer - 标签式布局 -->
    <div class="role-footer">
      <div class="footer-tag char-count-tag">
        <el-icon><Document /></el-icon>
        <span>{{ charCount }} 字符</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, computed } from 'vue'
import { Delete, Setting, UserFilled, Document } from '@element-plus/icons-vue'
import { ConfirmDialog } from '../comp/confirmDialog.js'

/* ---------------- Props ---------------- */
const props = defineProps({
  id: { type: Number, required: true },
  roleName: { type: String, required: true },
  roleDefinition: { type: String, required: true },
  enabled: { type: Boolean, required: true },
})

/* ---------------- Emits ---------------- */
const emit = defineEmits(['update:enabled', 'edit', 'delete'])

/* ---------------- Local state ---------------- */
const localEnabled = ref(props.enabled)

/* ---------------- Watch ---------------- */
watch(() => props.enabled, (val) => { localEnabled.value = val })

/* ---------------- Computed ---------------- */
const charCount = computed(() => props.roleDefinition?.length || 0)

/* ---------------- Methods ---------------- */
const handleToggle = (val) => {
  emit('update:enabled', { id: props.id, enabled: val })
}

const handleEdit = () => {
  emit('edit', props.id)
}

const handleDelete = async () => {
  try {
    await ConfirmDialog.confirm(
      `确定要删除角色卡 "${props.roleName}" 吗？`,
      '删除确认',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
    )
    emit('delete', props.id)
  } catch (err) {
    console.error("roleCard: handleDelete error:", err)
    ElMessage({ type: 'error', message: '删除失败', plain: true })
  }
}
</script>

<style scoped>
.role-card {
  position: relative;
  padding: 14px 16px;
  border-radius: 12px;
  height: 250px;
  width: 221px;

  display: flex;
  flex-direction: column;

  background: var(--apix-panel-layer-2-background);
  border: 1px solid var(--apix-default-light-color);

  box-shadow: var(--apix-shadow-layer-2);

  transition: box-shadow 0.4s cubic-bezier(0.34, 2, 0.64, 1);
}

.role-card:hover {
  border: 1px solid var(--apix-primary-color);
  box-shadow: var(--apix-shadow-layer-2);
}

/* Header - 保持原有样式 */
.role-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  flex-shrink: 0;
}

.role-actions {
  display: flex;
  gap: 4px;
}

/* 内容区域 - 统一布局 */
.role-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-height: 0;
  margin-bottom: 12px;
}

/* 标题区域 - 带图标 */
.role-title-wrapper {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.role-icon {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  background: linear-gradient(135deg, #e8a8f4 0%, #ee788a 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 14px;
  flex-shrink: 0;
}

.role-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--apix-default-dark-color);

  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 定义区域 - 自适应高度 */
.role-definition-wrapper {
  flex: 1;
  position: relative;
  overflow: hidden;
}

.role-definition {
  font-size: 13px;
  line-height: 1.6;
  height: 3lh;
  color: var(--apix-tertiary-dark-color);

  overflow: hidden;
  text-overflow: ellipsis;
  
  display: -webkit-box;
  -webkit-line-clamp: 6;
  -webkit-box-orient: vertical;
}

/* 底部 - 标签式布局 */
.role-footer {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  flex-shrink: 0;
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
  background: rgba(0, 0, 0, 0.08);
  transform: translateY(-1px);
}

.footer-tag .el-icon {
  font-size: 12px;
}

.char-count-tag {
  color: #7c3aed;
  background: rgba(124, 58, 237, 0.1);
}

.char-count-tag:hover {
  background: rgba(124, 58, 237, 0.15);
}

/* Buttons */
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