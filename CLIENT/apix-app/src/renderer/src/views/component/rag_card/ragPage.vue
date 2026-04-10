<template>
  <div class="rag-page-wrapper">
    <div class="ab-bar">
      <div class="ab-bar-btns">
        <n-select
          v-model:value="store.config.embeddingModel"
          :options="modelSelectOptions"
          class="model-select"
          :class="{ errorServer: errorServer }"
          :consistent-menu-width="false"
          :show-arrow="false"
          @focus="getEmbedModel"
        />
        <el-button 
          type="primary" 
          class="upload-btn"
          @click="uploadDocument"
        >
          上传文档
          <el-icon class="el-icon--right">
            <Upload />
          </el-icon>
        </el-button>
      </div>
    </div>

    <div class="main-wrapper selectable">

      <h1 style="width: 100%; text-align: center; font-size: 20px;">
        RAG 知识库
      </h1>

      <!-- Search -->
      <div class="search-wrapper">
        <el-input
          v-model="searchKeyword"
          placeholder="Search documents by name / description"
          clearable
          style="max-width: 420px;"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
      </div>

      <!-- Document grid -->
      <transition-group
        v-if="filteredDocList.length"
        name="doc-fade"
        tag="div"
        class="doc-grid"
      >
        <RagDocumentCard
          v-for="(doc, index) in filteredDocList"
          :client_id="cid"
          :key="doc.id"
          :document_id="doc.id"
          :name="doc.name"
          :embeddingModel="doc.embeddingModel"
          :updatedAt="doc.updatedAt"
          :size="doc.size"
          :type="doc.type"
          :desc="doc.desc"
          :indexed="doc.indexed"
          :active="doc.active"
          :style="{ '--stagger-index': index }"
          @delete="handleDeleteDocument"
          @reindex="handleReindexDocument"
          @edit="openRagDialog"
          @update:active="handleRagToggle"
        />
      </transition-group>

      <!-- Empty -->
      <div
        v-else
        style="width: 100%; text-align: center; color: #999; margin-top: 40px; min-height: 600px; line-height: 400px; font-size: 16px;"
      >
        No documents found
      </div>

      <div style="width: 100%; height: 60px;"></div>

      <!-- Explain -->
      <div class="explain-tag-wrapper">
        <div
          class="explain-tag"
          v-html="ragDocs"
        ></div>
      </div>

      <div style="width: 100%; height: 60px;"></div>

    </div>
  </div>

  <RagEditDialog
    v-model="dialogVisible"
    :rag="editingRag"
    @save="handleSaveRag"
  />
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import RagDocumentCard from './ragCard.vue'
import ragDocs from '../../../assets/docs/ragDocs.html?raw'
import { useAuthStore } from '../../../store/auth'
import { NSelect } from 'naive-ui'
import { useAppCacheData } from '../../../store/app'
import RagEditDialog from './RagEditDialog.vue'

const authStore = useAuthStore()
const store = useAppCacheData()
const cid = ref('')

onMounted(async () => {
  try {
    await authStore.restore()
    cid.value = authStore.user.user_uid
    docList.value = await getAvailableDocuments(cid.value)
  } catch (err) {
    console.error('初始化失败', err)
  }
})

// ----------------------------------------------------------------------
// Search
// ----------------------------------------------------------------------

const searchKeyword = ref('')

// ----------------------------------------------------------------------
// Document structure
// ----------------------------------------------------------------------

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

// ----------------------------------------------------------------------
// Document list
// ----------------------------------------------------------------------

const docList = ref<RagDocumentItem[]>([])

// ----------------------------------------------------------------------
// Embedding model list
// ----------------------------------------------------------------------

const errorServer = ref(false)
const modelSelectOptions = ref<{ label: string; value: string }[]>([])

const getEmbedModel = async () => {
  try {
    const models = await window.api.getEmbedList(
      'ollama:local',
      'api_key'
    )

    modelSelectOptions.value.length = 0
    modelSelectOptions.value.push(
      ...models.map((name: string) => ({
        label: name,
        value: name,
      }))
    )

    errorServer.value = false
    ensureValidModel()
  } catch (err) {
    errorServer.value = true
    modelSelectOptions.value = [
      {
        label: 'Server Error: Please make sure AI service is accessible.',
        value: '',
      },
    ]
    console.error('getModelsList failed:', err)
  }
}

function ensureValidModel() {
  const options = modelSelectOptions.value
  if (options.length === 0) return

  const current = store.config.embeddingModel
  const isValid = options.some(opt => opt.value === current)

  if (!current || !isValid) {
    const firstValue = options[0].value
    store.saveAppConfig('embeddingModel', firstValue)
    console.log('Use default model:', firstValue)
  }
}

watch(
  () => store.config.embeddingModel,
  (val, oldVal) => {
    if (val === oldVal) return
    if (!val) return

    store.saveAppConfig('embeddingModel', val)
    console.log('Update model to:', val)
  },
  { immediate: true }
)

// ----------------------------------------------------------------------
// Filter
// ----------------------------------------------------------------------

const filteredDocList = computed(() => {
  const keyword = searchKeyword.value.trim().toLowerCase()

  if (!keyword) return docList.value

  return docList.value.filter(doc =>
    doc.name.toLowerCase().includes(keyword) ||
    doc.desc.toLowerCase().includes(keyword)
  )
})

// ----------------------------------------------------------------------
// Dialog logic
// ----------------------------------------------------------------------

const dialogVisible = ref(false)
const editingRag = ref<RagDocumentItem | null>(null)

const openRagDialog = (id: string) => {
  const ragDoc = docList.value.find(r => r.id === id)
  if (!ragDoc) return

  editingRag.value = { ...ragDoc }
  dialogVisible.value = true
}

// ----------------------------------------------------------------------
// API logic
// ----------------------------------------------------------------------

const getAvailableDocuments = async (cid: string): Promise<RagDocumentItem[]> => {
  try {
    const res = await window.api.getAvailableDocuments(cid, 999)

    if (!Array.isArray(res)) {
      throw new Error('invalid document list')
    }

    const docs: RagDocumentItem[] = res.map((d: any) => ({
      client_id: cid,
      id: d.document_id,
      name: d.document_name,
      embeddingModel: Array.isArray(d.embed_engine)
        ? d.embed_engine.join(', ')
        : String(d.embed_engine ?? "Not Indexed"),
      updatedAt: formatTime(d.upload_at),
      size: formatSize(Number(d.document_size ?? 0)),
      type: formatMimeType(d.mime_type),
      desc: d.document_description || 'No description here.',
      indexed: (() => {
        const current = store.config.embeddingModel
        const engine = d.embed_engine

        if (!engine) return false

        return String(engine).includes(String(current));
      })(),
      active: Boolean(d.is_active)
    }))

    return docs
  } catch (err) {
    console.error('getAvailableDocuments failed:', err)

    ElMessage({
      type: 'error',
      message: '获取文档列表失败',
      plain: true,
    })

    return []
  }
}

// ----------------------------------------------------------------------
// Reindex / Delete
// ----------------------------------------------------------------------

const handleRagToggle = async ({
  document_id,
  active,
}: {
  document_id: string
  active: boolean
}) => {
  const doc = docList.value.find(d => d.id === document_id)
  if (!doc) return
  try {
    await window.api.updateDocumentsStatus(cid.value, document_id, active)
    doc.active = active
  }
  catch (err) {
    console.error('handleRagToggle failed:', err)

    ElMessage({
      type: 'error',
      message: '文档更新失败: ' + String(err),
      plain: true,
    })

  }
}

const handleReindexDocument = async (docId: string) => {
  const doc = docList.value.find(d => d.id === docId)
  if (!doc) return

  doc.indexed = true
}

const handleDeleteDocument = async (docId: string) => {
  const index = docList.value.findIndex(d => d.id === docId)
  if (index === -1) return

  try {
    await window.api.deleteDocument(cid.value, docId)
    docList.value.splice(index, 1)
  } catch (err) {
    console.error('deleteDocument failed:', err)
    ElMessage({
      type: 'error',
      message: '文档删除失败: ' + String(err),
      plain: true,
    })
  }
}

// ----------------------------------------------------------------------
// Upload
// ----------------------------------------------------------------------

const isUploading = ref(false)

const uploadDocument = async () => {
  if (isUploading.value) return

  try {
    const result = await window.api.openFileDialog()

    if (result.canceled || result.filePaths.length === 0) {
      return
    }

    isUploading.value = true

    const plainFiles = result.filePaths.map((path: string) => ({
      name: path.split(/[\\/]/).pop() || 'unknown',
      path,
    }))

    const resp = await window.api.uploadDocumentFiles(cid.value, plainFiles)

    if (!resp?.success) {
      throw new Error(resp?.message || 'upload failed')
    }

    const messages = Array.isArray(resp.messages) ? resp.messages : []
    console.log("uploadDocument: ", messages)
    if (messages.length > 0) {
      await refreshDocuments()
    }
    else {
      throw new Error("请检查文档类型是否合法！");
    }

    ElMessage({
      type: 'success',
      message: `文档上传成功 (${messages.length})`,
      plain: true,
    })
  } catch (err) {
    console.error('uploadDocument failed:', err)

    ElMessage({
      type: 'error',
      message: '文档上传失败: ' + String(err),
      plain: true,
    })
  } finally {
    isUploading.value = false
  }
}

// ----------------------------------------------------------------------
// Save
// ----------------------------------------------------------------------

const handleSaveRag = async (ragData: RagDocumentItem) => {
  const index = docList.value.findIndex(d => d.id === ragData.id)

  if (index !== -1) {
    try {
      await window.api.updateDocumentsDesc(cid.value, ragData.id, ragData.desc)
      docList.value[index] = ragData
      ElMessage({
        type: 'success',
        message: '文档已更新',
        plain: true,
      })
    } catch (err) {
      console.error('handleSaveRag failed:', err)

      ElMessage({
        type: 'error',
        message: '文档更新失败: ' + String(err),
        plain: true,
      })
    }
  }
}

// ----------------------------------------------------------------------
// Helpers
// ----------------------------------------------------------------------

async function refreshDocuments() {
  docList.value = await getAvailableDocuments(cid.value)
}

function formatSize(bytes: number) {
  if (!Number.isFinite(bytes) || bytes <= 0) return '0 B'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`
  return `${(bytes / 1024 / 1024 / 1024).toFixed(1)} GB`
}

function formatTime(time: string) {
  if (!time) return ''
  return time.replace('T', ' ').replace(/\.\d+$/, '')
}

function formatMimeType(mimeType: string) {
  if (!mimeType) return 'Unknown'

  const map: Record<string, string> = {
    'application/pdf': 'PDF',
    'text/markdown': 'Markdown',
    'text/plain': 'Text',
    'application/msword': 'Word',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'Word',
    'application/vnd.ms-excel': 'Excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'Excel',
    'application/vnd.ms-powerpoint': 'PPT',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation': 'PPT',
    'application/json': 'JSON',
    'text/html': 'HTML',
    'text/csv': 'CSV',
  }

  return map[mimeType] || mimeType
}
</script>


<style scoped>
.rag-page-wrapper {
  position: relative;
}

.main-wrapper {
  position: relative;
  justify-content: center;
  width: 1050px;
  height: calc(100vh - 52px) !important;
  left: calc((100% - 1090px) / 2);
  padding: 10px 20px;
  overflow-y: scroll;
  border-radius: 16px;
  align-items: center;
}

.ab-bar {
  width: 100%;
  position: absolute;
  bottom: 24px;
  display: flex;
  flex-direction: column;
  align-items: center;
  z-index: 999;
}

.ab-bar-btns {
  display: flex;
  flex-direction: row;
  gap: 16px;
  z-index: 999;
}

.model-select:deep(.n-base-selection__border) {
  opacity: 0;
}

.model-select:deep(.n-base-selection__state-border) {
  opacity: 0;
}

.model-select {
  width: 105px !important;
  height: 32px !important;
  border: none !important;
  border-radius: 32px !important;
  color: white !important;
  -webkit-transition: all 0.3s cubic-bezier(0.215, 0.61, 0.355, 1);
  transition: all 0.3s cubic-bezier(0.215, 0.61, 0.355, 1);
}

.model-select:hover {
  transform: scale(1.05);
}

.model-select:active {
  transform: scale(1.02);
}

.model-select:deep(*) {
  color: white !important;
  align-items: center;
  font-size: 14px;
}

.model-select:not(.errorServer):deep(.n-base-selection) {
  /* border: 1px solid #5485801c !important; */
  width: 105px !important;
  height: 32px !important;
  font-size: 12px !important;
  font-weight: bold;
  border-radius: 32px !important;
  min-height: 28px;
  color: white !important;

  -webkit-backdrop-filter: saturate(500%) blur(16px);
  backdrop-filter: saturate(500%) blur(16px);

  background: color-mix(in oklch, rgb(98, 156, 174) 40%, transparent);

  box-shadow:
    0 14px 30px rgba(0, 166, 255, 0.13),
    0 6px 14px rgba(4, 52, 42, 0.08),
    0 2px 6px rgba(0, 0, 0, 0.02);
}

.model-select.errorServer:deep(.n-base-selection) {
  /* border: 1px solid #f35555bb !important; */
  font-size: 12px !important;
  width: 105px !important;
  height: 32px !important;
  font-weight: bold;
  border-radius: 32px !important;
  min-height: 28px;
  color: white !important;

  -webkit-backdrop-filter: saturate(500%) blur(16px);
  backdrop-filter: saturate(500%) blur(16px);

  background: color-mix(in oklch, #f35555ee 40%, transparent);

  box-shadow:
    0 14px 30px rgba(255, 0, 0, 0.13),
    0 6px 14px rgba(52, 11, 4, 0.08),
    0 2px 6px rgba(0, 0, 0, 0.02);
}

.model-select:deep(.n-base-selection-label) {
  position: relative;
  color: white !important;
  height: 28px;
  background-color: rgba(98, 156, 174, 0) !important;
}

.model-select:deep(.n-base-selection-input) {
  padding: 6px 8px !important;
}

.model-select:deep(.n-base-selection-placeholder__inner) {
  color: rgba(255, 255, 255, 0.731) !important;
  font-weight: 500;
  font-size: 14px;
}

.upload-btn {
  width: 105px;
  height: 32px;
  font-size: 14px;
  font-weight: bold;
  border-radius: 32px;
  color: #ffffff;

  -webkit-backdrop-filter: saturate(500%) blur(16px);
  backdrop-filter: saturate(500%) blur(16px);

  background: color-mix(in oklch, #00a6ff 40%, transparent);

  -webkit-transition: all 0.3s cubic-bezier(0.215, 0.61, 0.355, 1);
  transition: all 0.3s cubic-bezier(0.215, 0.61, 0.355, 1);

  box-shadow:
    0 14px 30px rgba(0, 166, 255, 0.13),
    0 6px 14px rgba(4, 52, 42, 0.08),
    0 2px 6px rgba(0, 0, 0, 0.02);

  border: none;
}

.upload-btn:hover {
  transform: scale(1.05);
}

.upload-btn:active {
  transform: scale(1.02);
}

.search-wrapper {
  width: 100%; 
  display: flex; 
  justify-content: center; 
  margin: 16px 0;
}

.search-wrapper :deep(.el-input) {
  flex: 1;
  min-width: 0;
  transform-origin: left center;
  transform: scale(1);
  transform-origin: center;
  transition: transform 0.22s cubic-bezier(0.34, 3.5, 0.64, 1);
}

.search-wrapper.is-focused :deep(.el-input) {
  transform: scale(0.97);
  transform-origin: center;
}

.search-wrapper :deep(.el-input:hover) {
  transform: scale(1.02);
  transform-origin: center;
  transition: transform 0.22s ease;
}

.search-wrapper :deep(.el-input__wrapper) {
  height: 34px;
  border-radius: 999px;
  background: rgba(228, 228, 228, 0.22);
  border: 1px solid rgba(255, 255, 255, 0.28);
  box-shadow:
    0 10px 26px rgba(0, 0, 0, 0.08),
    0 2px 6px rgba(0, 0, 0, 0.05);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  padding: 0 12px 0 10px;
  transition: all 0.13s ease, border-color 0.18s ease, box-shadow 0.18s ease;
}

.search-wrapper.is-focused :deep(.el-input__wrapper) {
  background: rgba(255, 255, 255, 0.536);
  border-color: rgba(255, 255, 255, 0.76);
  z-index: 99;
}

/* ---------- Grid layout ---------- */
.doc-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
  margin-bottom: 20px;
  min-height: 600px;
}

/* ---------- Explain tag ---------- */
.explain-tag-wrapper {
  width: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
}

.explain-tag {
  border-top: 6px solid #00a6ff;
  background: color-mix(in oklch, #fbfbfb 40%, transparent);
  backdrop-filter: blur(3px);
  width: 80%;
  border-radius: 16px;
  text-align: center;
  align-self: center;
}

/* Scrollbar cleanup */
.main-wrapper::-webkit-scrollbar {
  width: 0px;
  height: 0px;
}

.main-wrapper::-webkit-scrollbar-track {
  background: transparent;
}

.main-wrapper::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.3);
}

.main-wrapper::-webkit-scrollbar-thumb:hover {
  background: rgba(0, 0, 0, 0.5);
}

/* File card animation with CSS stagger */
.doc-fade-enter-active {
  transition: 
    opacity 0.5s cubic-bezier(0.215, 0.61, 0.355, 1),
    transform 0.5s cubic-bezier(0.215, 0.61, 0.355, 1);
  transition-delay: calc(var(--stagger-index, 0) * 60ms);
}

.doc-fade-enter-from {
  opacity: 0;
  transform: translateY(20px) scale(0.9);
}

.doc-fade-enter-to {
  opacity: 1;
  transform: translateY(0) scale(1);
}

/* Leave animation - quick fade out */
.doc-fade-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
  position: absolute;
}

.doc-fade-leave-to {
  opacity: 0;
  transform: scale(0.9);
}

/* Move animation for reordering */
.doc-fade-move {
  transition: transform 0.4s cubic-bezier(0.215, 0.61, 0.355, 1);
}
</style>