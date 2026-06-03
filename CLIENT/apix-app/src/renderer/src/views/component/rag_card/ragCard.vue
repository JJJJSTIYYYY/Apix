<template>
  <div class="rag-card selectable">

    <!-- Header -->
    <div class="rag-header">

      <!-- Active Switch -->
      <el-switch
        v-model="localActive"
        size="small"
        :disabled="embedding"
        @change="handleToggle"
      />

      <div class="rag-actions">
        <button
          class="icon-btn delete-btn"
          title="Delete Document"
          @click="handleDelete"
        >
          <el-icon><Delete /></el-icon>
        </button>
        <button
          class="icon-btn"
          title="Edit Document"
          @click="handleEdit"
        >
          <el-icon><Setting /></el-icon>
        </button>
      </div>

    </div>

    <!-- Content -->
    <div class="rag-content">

      <!-- Title -->
      <div class="rag-title-wrapper">
        <div class="rag-icon">
          <svg t="1780298775080" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="19492" width="16" height="16"><path d="M803.5 62H459.14v309.85l-84.62-77.46-87.56 77.46V62h-66.47c-47.54 0-86.09 38.54-86.09 86.09v727.82c0 47.54 38.55 86.09 86.09 86.09H803.5c47.55 0 86.1-38.55 86.1-86.09V148.09c0-47.55-38.55-86.09-86.1-86.09z m-2.64 781.13c-7.7 7.7-18.34 12.46-30.09 12.46H253.23c-23.5 0-42.55-19.05-42.55-42.55 0-11.75 4.76-22.39 12.46-30.09 7.7-7.7 18.34-12.46 30.09-12.46h517.54c23.5 0 42.55 19.05 42.55 42.55 0 11.75-4.76 22.39-12.46 30.09z m0-172.18c-7.7 7.7-18.34 12.46-30.09 12.46H253.23c-23.5 0-42.55-19.05-42.55-42.55 0-11.75 4.76-22.39 12.46-30.09 7.7-7.7 18.34-12.46 30.09-12.46h517.54c23.5 0 42.55 19.05 42.55 42.55 0 11.75-4.76 22.39-12.46 30.09z" p-id="19493" fill="currentColor"></path></svg>
        </div>

        <div class="rag-title" :title="name">
          {{ name }}
        </div>
      </div>

      <!-- Description -->
      <div class="rag-description-wrapper">
        <div class="rag-description" :title="desc">
          {{ desc }}
        </div>
      </div>

      <!-- Embedding Model -->
      <div class="footer-tag model-tag">
        <el-icon><Cpu /></el-icon>
        <span class="tag-text">{{ embeddingModel }}</span>
      </div>

    </div>

    <!-- Footer -->
    <div class="rag-footer">

      <div class="footer-tag type-tag">
        <el-icon><Files /></el-icon>
        <span>{{ type }}</span>
      </div>

      <div class="footer-tag size-tag">
        <el-icon><Box /></el-icon>
        <span>{{ size }}</span>
      </div>
      
      <!-- Index Status Button -->
      <button
        class="status-tag"
        :class="statusClass"
        :disabled="embedding"
        @click="handleReEmbedding"
      >
        <span class="status-icon">
          <el-icon v-if="embedding" class="spin-icon"><Loading /></el-icon>
          <el-icon v-else-if="props.indexed" class="check-icon"><CircleCheck /></el-icon>
          <el-icon v-else class="warning-icon"><Warning /></el-icon>
        </span>
        <span class="status-text">{{ statusText }}</span>
        <span v-if="embedding" class="progress-dots">
          <span class="dot"></span>
          <span class="dot"></span>
          <span class="dot"></span>
        </span>
      </button>

      <div class="footer-tag time-tag" :title="updatedAt">
        <el-icon><Clock /></el-icon>
        <span>{{ updatedAt.split(" ")[0] }}</span>
      </div>

    </div>

  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { ConfirmDialog } from '../comp/confirmDialog.js'
import { useAppCacheData } from '../../../store/app'

/* ---------------- Props ---------------- */

const props = defineProps({
  client_id: { type: String, required: true },
  document_id: { type: String, required: true },
  name: { type: String, required: true },
  embeddingModel: { type: String, required: true },
  updatedAt: { type: String, required: true },
  size: { type: String, required: true },
  type: { type: String, required: true },
  desc: { type: String, required: true },
  indexed: { type: Boolean, required: true },
  active: { type: Boolean, required: true },
})

/* ---------------- Emits ---------------- */

const emit = defineEmits([
  'reindex',
  'edit', 'delete',
  'update:active'
])

const store = useAppCacheData()

/* ---------------- Local state ---------------- */
// Whether the document is currently embedding
const embedding = ref(false)
const localActive = ref(props.active)

/* ---------------- Watch ---------------- */
watch(() => props.active, (val) => {
  localActive.value = val
})

/* ---------------- Computed ---------------- */

const statusText = computed(() => {
  if (embedding.value) return 'Waiting'
  return props.indexed ? 'Indexed' : 'Not Indexed'
})

const statusClass = computed(() => {
  if (embedding.value) return 'is_embedding'
  return props.indexed ? 'has_indexed' : 'not_indexed'
})

/* ---------------- Methods ---------------- */

const handleToggle = (val) => {
  emit('update:active', {
    document_id: props.document_id,
    active: val
  })
}

const handleReEmbedding = async () => {
  if (embedding.value) return

  embedding.value = true

  try {
    await window.api.embedDocumentFile(props.client_id, props.document_id, store.config.embeddingModel)
    ElMessage({
      type: 'success',
      message: '文档已更新',
      plain: true,
    })
    emit('reindex', props.document_id)
  } catch (err) {
    console.error('reindexDocument failed:', err)
    ElMessage({
      type: 'error',
      message: '文档重新索引失败: ' + String(err),
      plain: true,
    })
  } finally {
    embedding.value = false
  }
}

const handleDelete = async () => {
  try {

    await ConfirmDialog.confirm(
      `确定要删除文档 "${props.name}" 吗？`,
      '删除确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    emit('delete', props.document_id)

  } catch (err) {

    console.error("ragCard: handleDelete error:", err)

    ElMessage({
      type: 'error',
      message: '删除失败',
      plain: true
    })

  }
}

const handleEdit = () => {
  emit('edit', props.document_id)
}
</script>

<style scoped>
.rag-card {
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

.rag-card:hover {
  border: 1px solid var(--apix-primary-color);
  box-shadow: var(--apix-shadow-layer-2);
}

/* Header */

.rag-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  flex-shrink: 0;
}

.rag-actions {
  display: flex;
  gap: 4px;
}

/* Content */

.rag-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 12px;
}

.rag-title-wrapper {
  display: grid;
  grid-template-columns: 30px auto;
  align-items: center;
  gap: 8px;
}

.rag-icon {
  width: 28px;
  height: 28px;
  border-radius: 6px;

  background: linear-gradient(135deg, #739FDB 0%, #94B8E8 100%);

  display: flex;
  align-items: center;
  justify-content: center;

  color: white;
  font-size: 14px;
}

.rag-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--apix-default-dark-color);

  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rag-description-wrapper {
  flex: 1;
  overflow: hidden;
}

.rag-description {
  font-size: 13px;
  line-height: 1.6;
  height: 3lh;
  color: var(--apix-tertiary-dark-color);

  overflow: hidden;
  text-overflow: ellipsis;

  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
}

/* Footer */

.rag-footer {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 6px;
  column-gap: 8px;

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
  transform: translateY(-1px);
}

.model-tag {
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

.size-tag {
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

/* Status: Indexed (Success) */
.status-tag.has_indexed {
  background: rgba(34, 197, 94, 0.15);
  color: #15803d;
  box-shadow: 
    0 0 0 1px rgba(34, 197, 94, 0.2),
    0 2px 4px rgba(34, 197, 94, 0.1);
}

.status-tag.has_indexed:hover {
  background: rgba(34, 197, 94, 0.25);
  color: #166534;
  transform: translateY(-1px) scale(1.02);
  box-shadow: 
    0 0 0 1px rgba(34, 197, 94, 0.3),
    0 4px 12px rgba(34, 197, 94, 0.2);
}

.status-tag.has_indexed:active {
  transform: translateY(0) scale(0.98);
}

/* Check icon animation */
.status-tag.has_indexed .check-icon {
  animation: checkPop 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
}

@keyframes checkPop {
  0% { transform: scale(0) rotate(-45deg); opacity: 0; }
  50% { transform: scale(1.2) rotate(10deg); }
  100% { transform: scale(1) rotate(0deg); opacity: 1; }
}

/* Status: Not Indexed (Warning) */
.status-tag.not_indexed {
  background: rgba(239, 68, 68, 0.12);
  color: #dc2626;
  box-shadow: 
    0 0 0 1px rgba(239, 68, 68, 0.15),
    0 2px 4px rgba(239, 68, 68, 0.08);
  animation: pulseWarning 2s ease-in-out infinite;
}

.status-tag.not_indexed:hover {
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

/* Status: Embedding (Loading) */
.status-tag.is_embedding {
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