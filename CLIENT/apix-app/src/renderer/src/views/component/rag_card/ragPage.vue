<template>
  <div class="rag-page-wrapper">

    <div class="main-wrapper">

      <div class="page-title-wrapper">
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
              placeholder="通过文档名称、文档描述搜索文档"
              clearable
              style="max-width: 420px;"
            >
              <template #prefix>
                <el-icon><Search /></el-icon>
              </template>
            </el-input>
          </div>
        </div>

        <div class="page-docs">
<span>1. 文档处理规范: 推荐使用 Markdown、TXT、JSON 格式，单文件不超过 20MB。PDF、Word、Excel、PPT 格式支持有限。文档上传后需要等待索引完成，请确保服务器算力充足并已安装 Ollama。</span>

<span>2. 嵌入模型与一致性要求: 仅支持通过 Ollama 部署的 Embedding 模型。更换嵌入模型后，必须重新处理所有未索引的文档，否则因向量空间不兼容会导致检索失真。切换模型后原有嵌入结果不会被自动删除，可手动删除。</span>

<span>3. 使用建议与注意事项: 文档上传后可设置文档描述，以帮助模型索引对应文档提升检索精确度。仅启用状态的文档会加载给 Agent 进行检索</span>
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
      <!-- <div class="explain-tag-wrapper">
        <div
          class="explain-tag"
          v-html="ragDocs"
        ></div>
      </div>

      <div style="width: 100%; height: 60px;"></div> -->

    </div>
  </div>

  <RagEditDialog
    v-if="dialogVisible"
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
    console.error('[Rag page onMounted error]:', err)
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
  background-color: transparent;
  height: calc(100vh - 36px);
}

.page-title-wrapper {
  display: flex;
  justify-content: space-between;
}

.page-docs {
  min-width: 500px;
  max-width: 500px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  font-size: 12px;
  color: var(--apix-tertiary-dark-color);
  text-indent: 2em;
}

.title-wrapper {
  margin: 8px 0;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  padding: 0px 12px;
  min-width: 500px;
  max-width: 500px;
}

.data-page-title {
  padding-left: 6px;
  font-size: 24px;
  color: var(--apix-default-dark-color);
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
  align-items: center;
  scrollbar-width: none;
}

.model-select {
  font-size: 14px !important;
  font-weight: bold !important;
  width: 180px !important;
  height: 32px !important;
  background: var(--apix-primary-color) !important;
  border: none !important;
  border-radius: var(--apix-border-radius-base) !important;
  color: var(--apix-lightest-color) !important;
  transition: background-color 0.3s var(--apix-cubic-bezier),
    opacity 0.3s var(--apix-cubic-bezier),
    transform 0.3s var(--apix-cubic-bezier);
  overflow: hidden;
}

.model-select:deep(.n-base-selection__border) {
  opacity: 0;
}

.model-select:deep(.n-base-selection__state-border) {
  opacity: 0;
}

.model-select:hover {
  background-color: var(--apix-primary-hover) !important;
}

.model-select:active {
  transform: scale(0.98);
  background-color: var(--apix-primary-active) !important;
}

.model-select:deep(*) {
  color: var(--apix-lightest-color) !important;
  align-items: center;
  background: transparent !important;
}

.model-select:not(.errorServer):deep(.n-base-selection) {
  background: var(--apix-primary-color) !important;
}

.model-select.errorServer:deep(.n-base-selection) {
  background: var(--apix-danger-color) !important;
}

.model-select:deep(.n-base-selection-label) {
  height: 32px !important;
  position: relative;
  color: var(--apix-lightest-color) !important;
  background-color: transparent !important;
}

.model-select:deep(.n-base-selection-input) {
  padding: 6px 8px !important;
}

.model-select:deep(.n-base-selection-placeholder__inner) {
  color: var(--apix-lightest-color) !important;
  font-weight: 300 !important;
  font-size: 14px;
}

.upload-btn {
  margin: 0 !important;
  width: 105px;
  height: 32px;
  font-size: 14px;
  font-weight: bold;
  border-radius: var(--apix-button-border-radius);
  color: var(--apix-lightest-color);
  background: var(--apix-primary-color);
  transition: background-color 0.3s var(--apix-cubic-bezier),
    transform 0.3s var(--apix-cubic-bezier);
  border: none;
}

.upload-btn:hover {
  background-color: var(--apix-primary-hover);
}

.upload-btn:active {
  transform: scale(0.98);
  background-color: var(--apix-primary-active);
}

.btn-wrapper {
  width: 100%; 
  display: flex; 
  margin: 8px 0;
  gap: 12px;
}

.search-wrapper {
  width: 100%;
  margin: 8px 0;
  display: flex;
  gap: 12px;
}

.search-wrapper :deep(.el-input) {
  flex: 1;
  min-width: 0;
  height: 38px !important;
  transform-origin: center;
  transform: scale(1);
  transition: transform 0.22s var(--apix-cubic-bezier);
}

.search-wrapper :deep(.el-input__wrapper) {
  height: 38px !important;
  padding: 0 12px 0 10px;
  background: transparent;
  background-color: var(--apix-panel-layer-4-background);
  border: none;
  border-radius: var(--apix-border-radius-base);
  box-shadow: var(--apix-shadow-layer-1);
  transition: all 0.13s var(--apix-cubic-bezier);
}

/* ---------- Grid layout ---------- */
.doc-grid {
  border-top: 4px solid var(--apix-secondary-light-color);
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
  width: 80%;
  border-radius: 16px;
  text-align: center;
  align-self: center;
  background-color: rgba(255, 255, 255, 0.5);
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