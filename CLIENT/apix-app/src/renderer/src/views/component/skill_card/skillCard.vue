<template>
  <div class="skill-card">

    <!-- Header - 保持不动 -->
    <div class="skill-header">
      <el-switch
        v-model="localEnabled"
        size="small"
        @change="handleToggle"
      />
      <div class="skill-actions">
        <button
          class="icon-btn delete-btn"
          title="Delete Skill"
          @click="handleDelete"
        >
          <el-icon><Delete /></el-icon>
        </button>
      </div>
    </div>

    <!-- 内容区域 - 重新布局 -->
    <div class="skill-content">
      <!-- Skill Name -->
      <div class="skill-title-wrapper">
        <div class="skill-icon">
          <el-icon><Collection /></el-icon>
        </div>
        <div class="skill-title" :title="skillName">
          {{ skillName }}
        </div>
      </div>

      <!-- Description -->
      <div class="skill-description-wrapper">
        <div class="skill-description" :title="skillDescription">
          {{ skillDescription }}
        </div>
      </div>
    </div>

    <!-- Footer - 标签式布局 -->
    <div class="skill-footer">
      <div class="footer-tag version-tag">
        <el-icon><CollectionTag /></el-icon>
        <span>{{ skillVersion }}</span>
      </div>
      <div class="footer-tag size-tag">
        <el-icon><Box /></el-icon>
        <span>{{ formattedSize }}</span>
      </div>
      <div class="footer-tag time-tag" :title="uploadAt">
        <el-icon><Clock /></el-icon>
        <span>{{ uploadAt }}</span>
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, watch, computed } from 'vue'
import { ConfirmDialog } from '../comp/confirmDialog.js'
import { Delete, Collection, CollectionTag, Box, Clock } from '@element-plus/icons-vue'

/* ---------------- Props ---------------- */
const props = defineProps({
  skillId: { type: String, required: true },
  skillName: { type: String, required: true },
  skillDescription: { type: String, required: true },
  skillVersion: { type: String, required: true },
  packageSize: { type: Number, required: true },
  uploadAt: { type: String, required: true },
  enabled: { type: Boolean, required: true },
})

/* ---------------- Emits ---------------- */
const emit = defineEmits(['update:enabled', 'delete'])

/* ---------------- Local state ---------------- */
const localEnabled = ref(props.enabled)

/* ---------------- Watch ---------------- */
watch(() => props.enabled, (val) => { localEnabled.value = val })

/* ---------------- Computed ---------------- */
const formattedSize = computed(() => {
  const size = props.packageSize || 0
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  if (size < 1024 * 1024 * 1024) return `${(size / 1024 / 1024).toFixed(1)} MB`
  return `${(size / 1024 / 1024 / 1024).toFixed(1)} GB`
})

/* ---------------- Methods ---------------- */
const handleToggle = (val) => {
  emit('update:enabled', { skill_id: props.skillId, enabled: val })
}

const handleDelete = async () => {
  try {
    await ConfirmDialog.confirm(
      `确定要删除技能包 "${props.skillName}" 吗？`,
      '删除确认',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
    )
    emit('delete', props.skillId)
  } catch (err) {
    console.error("skillCard: handleDelete error:", err)
    ElMessage({ type: 'error', message: '删除失败', plain: true })
  }
}
</script>

<style scoped>
.skill-card {
  position: relative;
  padding: 14px 16px;
  border-radius: 12px;
  height: 220px;
  width: 221px;

  display: flex;
  flex-direction: column;
  
  background: rgb(245, 247, 247);
  border: 1px solid rgba(255, 255, 255, 0.28);
  box-shadow:
    0 2px 6px rgba(0, 0, 0, 0.166);
  transition: all 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.skill-card:hover {
  transform: translateY(-1px);
  box-shadow:
    0 10px 26px rgba(4, 52, 42, 0.166),
    0 2px 6px rgba(0, 0, 0, 0.05);
}

/* Header - 保持原有样式 */
.skill-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  flex-shrink: 0;
}

.skill-actions {
  display: flex;
  gap: 4px;
}

/* 内容区域 - 占据剩余空间 */
.skill-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-height: 0; /* 关键：允许 flex 子项收缩 */
  margin-bottom: 12px;
}

/* 标题区域 - 带图标 */
.skill-title-wrapper {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.skill-icon {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  background: linear-gradient(135deg, #85a3f0 0%, #b1a6ee 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 14px;
  flex-shrink: 0;
}

.skill-title {
  font-size: 15px;
  font-weight: 600;
  color: #2f3a3a;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  line-height: 1.4;
}

/* 描述区域 - 自适应高度 */
.skill-description-wrapper {
  flex: 1;
  position: relative;
  overflow: hidden;
}

.skill-description {
  font-size: 13px;
  line-height: 1.6;
  color: #586666;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
}

/* 底部 - 标签式布局 */
.skill-footer {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 6px;
  column-gap: 8px;
  flex-shrink: 0;
  padding-top: 10px;
  border-top: 1px solid rgba(0, 0, 0, 0.06);
}

.footer-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 500;
  background: rgba(0, 0, 0, 0.04);
  color: #6b7280;
  transition: all 0.2s ease;
}

.footer-tag:hover {
  background: rgba(0, 0, 0, 0.08);
  transform: translateY(-1px);
}

.footer-tag .el-icon {
  font-size: 12px;
}

.version-tag {
  color: #059669;
  background: rgba(5, 150, 105, 0.1);
  border-radius: 6px;
}

.version-tag:hover {
  background: rgba(5, 150, 105, 0.15);
}

.size-tag {
  color: #d97706;
  background: rgba(217, 119, 6, 0.1);
}

.size-tag:hover {
  background: rgba(217, 119, 6, 0.15);
}

.time-tag {
  color: #6b7280;
  max-width: 100%;
  overflow: hidden;
  grid-column: 1 / -1;
}

.time-tag span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 按钮样式 */
.icon-btn {
  border: none;
  background: transparent;
  cursor: pointer;
  font-size: 14px;
  padding: 4px;
  border-radius: 6px;
  width: 26px;
  height: 26px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
}

.icon-btn:hover {
  background: rgba(0, 0, 0, 0.06);
}

.delete-btn:hover {
  background: rgba(239, 68, 68, 0.1);
  color: #ef4444;
  transform: rotate(4deg);
}
</style>