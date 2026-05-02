<template>
  <div class="rag-page-wrapper">

    <div class="main-wrapper">

      <div class="title-wrapper">
        <h1 class="data-page-title">
          RAG 知识库
        </h1>

        <div class="btn-wrapper">
          <el-button 
            type="primary" 
            class="upload-btn noselect"
            @click="uploadDocument"
          >
            上传文档
            <el-icon class="el-icon--right">
              <Upload />
            </el-icon>
          </el-button>
          <n-select
            v-model:value="store.config.embeddingModel"
            :options="modelSelectOptions"
            class="model-select noselect"
            :class="{ errorServer: errorServer }"
            :consistent-menu-width="false"
            :show-arrow="false"
            @focus="getEmbedModel"
          />
        </div>

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
    const result = await window.api.openFileDialog('file')

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
  background-color: rgba(255, 255, 255, 0.5);
  box-shadow: 
    inset 0 0 0 2px rgba(255, 255, 255, 0.8),
    0 0px 26px rgba(218, 218, 218, 0.206),
    0 0px 6px rgba(218, 218, 218, 0.09);
  border-radius: 24px;
  margin: 12px 12px 12px 0;
}

.title-wrapper {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  padding: 0px 12px;
  border-radius: 24px;
}

.data-page-title {
  padding-left: 6px;
  font-size: 24px;
  color: rgb(82, 108, 106);
  margin-bottom: 0px;
}

.main-wrapper {
  position: relative;
  justify-content: center;
  width: 1050px;
  height: calc(100vh - 76px) !important;
  left: calc((100% - 1090px) / 2);
  padding: 10px 20px;
  overflow-y: scroll;
  border-radius: 16px;
  align-items: center;
}

.model-select {
  font-size: 12px !important;
  font-weight: bold !important;
  width: 180px !important;
  height: 32px !important;
  border: none !important;
  border-radius: 12px !important;
  color: white !important;
  transition: all 0.3s cubic-bezier(0.215, 0.61, 0.355, 1);
  overflow: hidden;
}

.model-select:deep(.n-base-selection__border) {
  opacity: 0;
}

.model-select:deep(.n-base-selection__state-border) {
  opacity: 0;
}

.model-select:hover {
  background-color: rgb(147, 195, 196) !important;
}

.model-select:active {
  transform: scale(0.98);
}

.model-select:deep(*) {
  color: white !important;
  align-items: center;
  background: transparent !important;
}

.model-select:not(.errorServer):deep(.n-base-selection) {
  background: rgb(158, 207, 208) !important;
}

.model-select.errorServer:deep(.n-base-selection) {
  background: #f35555ee !important;
}

.model-select:deep(.n-base-selection-label) {
  height: 32px !important;
  position: relative;
  color: white !important;
  background-color: transparent !important;
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
  border-radius: 12px;
  color: #ffffff;
  background: rgb(158, 207, 208);
  transition: all 0.3s cubic-bezier(0.215, 0.61, 0.355, 1);
  border: none;
}

.upload-btn:hover {
  background-color: rgb(147, 195, 196);
}

.upload-btn:active {
  transform: scale(0.98);
}

.btn-wrapper {
  width: 100%; 
  display: flex; 
  margin: 16px 0 0 0;
  gap: 12px;
}

.search-wrapper {
  width: 100%; 
  display: flex; 
  margin: 16px 0;
  gap: 12px;
}

.search-wrapper :deep(.el-input) {
  height: 32px !important;
  flex: 1;
  min-width: 0;
  transform-origin: left center;
  transform: scale(1);
  transform-origin: center;
  transition: transform 0.22s cubic-bezier(0.34, 1, 0.64, 1);
}

.search-wrapper :deep(.el-input__wrapper) {
  height: 32px !important;
  background: transparent;
  border: none;
  border-radius: 0px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.1);
  box-shadow: none;
  padding: 0 12px 0 10px;
  transition: all 0.13s ease, border-color 0.18s ease, box-shadow 0.18s ease;
}

/* ---------- Grid layout ---------- */
.doc-grid {
  border-top: 4px solid rgba(0, 0, 0, 0.08);
  margin-top: 20px; 
  padding-top: 32px;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
  margin-bottom: 20px;
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
  width: 80%;
  border-radius: 16px;
  text-align: center;
  align-self: center;
  background-color: rgba(255, 255, 255, 0.5);
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