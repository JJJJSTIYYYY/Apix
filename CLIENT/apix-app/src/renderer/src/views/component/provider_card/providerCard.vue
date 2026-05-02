<template>
  <div class="provider-card selectable">

    <!-- Header -->
    <div class="provider-header">
      <el-switch
        v-model="localEnabled"
        size="small"
        @change="handleToggle"
      />

      <div class="provider-actions">
        <button
          class="icon-btn delete-btn"
          title="Delete Provider"
          @click="handleDelete"
        >
          <el-icon><Delete /></el-icon>
        </button>

        <button
          class="icon-btn"
          title="Edit Provider"
          @click="handleEdit"
        >
          <el-icon><Setting /></el-icon>
        </button>
      </div>
    </div>

    <!-- Content -->
    <div class="provider-content">

      <div class="provider-title-wrapper">
        <div class="provider-icon">
          <el-icon><Connection /></el-icon>
        </div>

        <div class="provider-title" :title="name">
          {{ name }}
        </div>
      </div>

      <div class="provider-description-wrapper">
        <div class="provider-description" :title="desc">
          {{ desc }}
        </div>
      </div>

      <div class="footer-tag endpoint-tag">
        <el-icon><Link /></el-icon>
        <span class="tag-text">{{ endpoint }}</span>
      </div>

    </div>

    <!-- Footer -->
    <div class="provider-footer">

      <div class="footer-tag type-tag">
        <el-icon><Collection /></el-icon>
        <span>{{ type }}</span>
      </div>

      <div class="footer-tag models-tag">
        <el-icon><Grid /></el-icon>
        <span>{{ modelList.length }} models</span>
      </div>

      <!-- Connection Test -->
      <button
        class="status-tag"
        :class="{ is_connecting: connecting }"
        :disabled="connecting"
        @click="handleTestConnection"
      >
        <el-icon v-if="connecting" class="spin-icon"><Loading /></el-icon>
        <el-icon v-else><Connection /></el-icon>
        <span>{{ connecting ? 'Testing...' : 'Test' }}</span>
      </button>

      <div class="footer-tag time-tag" :title="updatedAt">
        <el-icon><Clock /></el-icon>
        <span>{{ updatedAt.split(" ")[0] }}</span>
      </div>

    </div>

  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { ConfirmDialog } from '../comp/confirmDialog.js'

/* ---------------- Props ---------------- */

const props = defineProps({
  provider_id: { type: String, required: true },
  name: { type: String, required: true },
  endpoint: { type: String, required: true },
  updatedAt: { type: String, required: true },
  type: { type: String, required: true },
  desc: { type: String, required: true },
  modelList: { type: Array, default: () => [] },
  api_key: { type: String, required: false, default: '' },
  enabled: { type: Boolean, required: false, default: false },
})

/* ---------------- Emits ---------------- */

const emit = defineEmits([
  'edit',
  'delete',
  'update:enabled'
])

/* ---------------- Local state ---------------- */

const connecting = ref(false)

const localEnabled = ref(props.enabled)
watch(() => props.enabled, (val) => { localEnabled.value = val })

/* ---------------- Methods ---------------- */

const handleToggle = (val) => {
  emit('update:enabled', { id: props.provider_id, enabled: val })
}

const handleTestConnection = async () => {
  if (connecting.value) return

  connecting.value = true

  try {
    await window.api.testProviderConnection(props.provider_id)

    ElMessage({
      type: 'success',
      message: '连接测试成功',
      plain: true,
    })

  } catch (err) {

    console.error('testProviderConnection failed:', err)

    ElMessage({
      type: 'error',
      message: '连接测试失败: ' + String(err),
      plain: true,
    })

  } finally {
    connecting.value = false
  }
}

const handleDelete = async () => {
  try {

    await ConfirmDialog.confirm(
      `确定要删除 Provider "${props.name}" 吗？`,
      '删除确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    emit('delete', props.provider_id)

  } catch (err) {
    return
  }
}

const handleEdit = () => {
  emit('edit', props.provider_id)
}
</script>

<style scoped>
.provider-card {
  position: relative;
  padding: 14px 16px;
  border-radius: 12px;
  height: 250px;
  width: 221px;

  display: flex;
  flex-direction: column;

  background: rgb(245, 247, 247);
  border: 1px solid rgba(255, 255, 255, 0.28);

  box-shadow:
    0 2px 6px rgba(0, 0, 0, 0.166);

  transition: all 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.provider-card:hover {
  transform: translateY(-1px);

  box-shadow:
    0 10px 26px rgba(4, 52, 42, 0.166),
    0 2px 6px rgba(0, 0, 0, 0.05);
}

/* Header */

.provider-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  flex-shrink: 0;
}

.provider-actions {
  display: flex;
  gap: 4px;
}

/* Content */

.provider-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 12px;
}

.provider-title-wrapper {
  display: grid;
  grid-template-columns: 30px auto;
  align-items: center;
  gap: 8px;
}

.provider-icon {
  width: 28px;
  height: 28px;
  border-radius: 6px;

  background: linear-gradient(135deg, #6431c9 0%, #6c6ae1 100%);

  display: flex;
  align-items: center;
  justify-content: center;

  color: white;
  font-size: 14px;
}

.provider-title {
  font-size: 15px;
  font-weight: 600;
  color: #2f3a3a;

  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.provider-description-wrapper {
  flex: 1;
  overflow: hidden;
}

.provider-description {
  font-size: 13px;
  line-height: 1.6;
  height: 3lh;
  color: #586666;

  overflow: hidden;
  text-overflow: ellipsis;

  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
}

/* Footer */

.provider-footer {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 6px;
  column-gap: 8px;

  padding-top: 10px;

  border-top: 1px solid rgba(0,0,0,0.06);
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
  overflow: hidden;
  max-width: 100%;
  transition: all 0.2s ease;
}

.footer-tag:hover {
  transform: translateY(-1px);
}

.endpoint-tag {
  color: #2563eb;
  background: rgba(37, 99, 235, 0.1);
}

/* 文本省略在 span 上，保持 flex 布局正常 */
.tag-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0; /* 关键：允许 flex item 收缩 */
}

/* 确保图标不收缩 */
.footer-tag .el-icon {
  flex-shrink: 0;
}

.type-tag {
  color: #7c3aed;
  background: rgba(124, 58, 237, 0.1);
}

.models-tag {
  color: #d97706;
  background: rgba(217,119,6,0.1);
}

/* Status Tag - Enhanced with animations */

.status-tag {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: none;
  /* width: fit-content; */
  font-size: 11px;
  font-weight: 600;
  padding: 5px 10px;
  border-radius: 999px;
  cursor: pointer;
  user-select: none;
  overflow: hidden;
  
  /* Smooth transitions for all properties */
  transition: 
    all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1),
    background-color 0.4s ease,
    color 0.3s ease,
    transform 0.2s ease,
    box-shadow 0.3s ease;
}

/* Status: Connected (Success) */
.status-tag.has_connected {
  background: rgba(34, 197, 94, 0.15);
  color: #15803d;
  box-shadow: 
    0 0 0 1px rgba(34, 197, 94, 0.2),
    0 2px 4px rgba(34, 197, 94, 0.1);
}

.status-tag.has_connected:hover {
  background: rgba(34, 197, 94, 0.25);
  color: #166534;
  transform: translateY(-1px) scale(1.02);
  box-shadow: 
    0 0 0 1px rgba(34, 197, 94, 0.3),
    0 4px 12px rgba(34, 197, 94, 0.2);
}

.status-tag.has_connected:active {
  transform: translateY(0) scale(0.98);
}

/* Check icon animation */
.status-tag.has_connected .check-icon {
  animation: checkPop 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
}

@keyframes checkPop {
  0% { transform: scale(0) rotate(-45deg); opacity: 0; }
  50% { transform: scale(1.2) rotate(10deg); }
  100% { transform: scale(1) rotate(0deg); opacity: 1; }
}

/* Status: Disconnected (Warning) */
.status-tag.not_connected {
  background: rgba(239, 68, 68, 0.12);
  color: #dc2626;
  box-shadow: 
    0 0 0 1px rgba(239, 68, 68, 0.15),
    0 2px 4px rgba(239, 68, 68, 0.08);
  animation: pulseWarning 2s ease-in-out infinite;
}

.status-tag.not_connected:hover {
  background: rgba(239, 68, 68, 0.2);
  color: #b91c1c;
  transform: translateY(-1px) scale(1.02);
  box-shadow: 
    0 0 0 1px rgba(239, 68, 68, 0.25),
    0 4px 12px rgba(239, 68, 68, 0.15);
  animation: none;
}

@keyframes pulseWarning {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.85; }
}

/* Status: Connecting (Loading) */
.status-tag.is_connecting {
  background: linear-gradient(
    90deg,
    rgba(99, 102, 241, 0.15) 0%,
    rgba(139, 92, 246, 0.15) 50%,
    rgba(99, 102, 241, 0.15) 100%
  );
  background-size: 200% 100%;
  color: #4f46e5;
  cursor: not-allowed;
  box-shadow: 
    0 0 0 1px rgba(99, 102, 241, 0.2),
    0 0 20px rgba(99, 102, 241, 0.15);
}

/* Spinning loader */
.spin-icon {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* Progress dots */
.progress-dots {
  display: inline-flex;
  gap: 3px;
  margin-left: 4px;
}

.progress-dots .dot {
  width: 4px;
  height: 4px;
  background: currentColor;
  border-radius: 50%;
  opacity: 0.6;
  animation: dotBounce 1.4s ease-in-out infinite both;
}

.progress-dots .dot:nth-child(1) {
  animation-delay: -0.32s;
}

.progress-dots .dot:nth-child(2) {
  animation-delay: -0.16s;
}

@keyframes dotBounce {
  0%, 80%, 100% { 
    transform: scale(0);
    opacity: 0.3;
  }
  40% { 
    transform: scale(1);
    opacity: 1;
  }
}

/* Status icon container */
.status-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 14px;
  height: 14px;
  transition: transform 0.3s ease;
}

.status-tag:hover .status-icon {
  transform: scale(1.1);
}

/* Status text with fade transition */
.status-text {
  position: relative;
  transition: opacity 0.2s ease;
}

/* Disabled state */
.status-tag:disabled {
  pointer-events: none;
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