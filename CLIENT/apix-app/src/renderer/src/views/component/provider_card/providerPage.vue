<template>
  <div class="provider-page-wrapper">
    <div class="main-wrapper">

      <div class="title-wrapper">
        <h1 class="data-page-title">
          LLM 提供商
        </h1>

        <div class="btn-wrapper">
          <div class="ab-bar-btns">
            <el-button 
              type="primary" 
              class="upload-btn"
              @click="createProvider"
            >
              新建提供商
              <el-icon style="padding-left: 4px;"><Plus /></el-icon>
            </el-button>
          </div>

          <div class="ab-bar-btns">
            <el-button 
              type="primary" 
              class="test-btn"
              @click="testConnection"
            >
              测试连接
              <el-icon style="padding-left: 4px;"><Link /></el-icon>
            </el-button>
          </div>
        </div>

        <!-- Search -->
        <div class="search-wrapper">
          <el-input
            v-model="searchKeyword"
            placeholder="Search provider by name / endpoint / description"
            clearable
            style="max-width: 420px;"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
        </div>
      </div>

      <!-- Provider grid -->
      <transition-group
        v-if="filteredProviderList.length"
        name="provider-fade"
        tag="div"
        class="provider-grid"
      >
        <ProviderCard
          v-for="(provider, index) in filteredProviderList"
          :key="provider.provider_id"
          :provider_id="provider.provider_id"
          :name="provider.name"
          :endpoint="provider.endpoint"
          :updatedAt="provider.updated_at"
          :type="provider.type"
          :desc="provider.description"
          :modelList="provider.model_list"
          :api_key="provider.api_key"
          :enabled="provider.enabled"
          :style="{ '--stagger-index': index }"
          @update:enabled="handleProviderToggle"
          @delete="handleDeleteProvider"
          @edit="openProviderDialog"
        />
      </transition-group>

      <!-- Empty -->
      <div
        v-else
        style="width: 100%; text-align: center; color: #999; margin-top: 40px; min-height: 600px; line-height: 400px; font-size: 16px;"
      >
        No providers found
      </div>

      <div style="width: 100%; height: 60px;"></div>

    </div>
  </div>

  <ProviderEditDialog
    v-model="dialogVisible"
    :provider="editingProvider"
    @save="handleSaveProvider"
  />
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import ProviderCard from './providerCard.vue'
import ProviderEditDialog from './ProviderEditDialog.vue'
import { useAuthStore } from '../../../store/auth'
import { useAppCacheData } from '../../../store/app'
import { ConfirmDialog } from '../comp/confirmDialog.js'

const store = useAppCacheData()
const authStore = useAuthStore()
const cid = ref('')

// ----------------------------------------------------------------------
// Init
// ----------------------------------------------------------------------

onMounted(async () => {
  try {
    await authStore.restore()
    cid.value = authStore.user.user_uid
    providerList.value = await getProviders(cid.value)
  } catch (err) {
    console.error('初始化失败', err)
  }
})

// ----------------------------------------------------------------------
// Search
// ----------------------------------------------------------------------

const searchKeyword = ref('')

// ----------------------------------------------------------------------
// Provider structure
// ----------------------------------------------------------------------

interface ProviderItem {
  provider_id: string
  name: string
  endpoint: string
  description: string
  type: string
  updated_at: string
  model_list: string[]
  api_key?: string
  enabled?: boolean
}

// ----------------------------------------------------------------------
// Data
// ----------------------------------------------------------------------

const providerList = ref<ProviderItem[]>([])

// ----------------------------------------------------------------------
// Filter
// ----------------------------------------------------------------------

const filteredProviderList = computed(() => {
  const keyword = searchKeyword.value.trim().toLowerCase()

  if (!keyword) return providerList.value

  return providerList.value.filter(p =>
    p.name.toLowerCase().includes(keyword) ||
    p.endpoint.toLowerCase().includes(keyword) ||
    p.description.toLowerCase().includes(keyword)
  )
})

// ----------------------------------------------------------------------
// Provider API
// ----------------------------------------------------------------------

// 单选启用
const handleProviderToggle = ({ id, enabled }: { id: string; enabled: boolean }) => {
  console.log('Provider switch:', id, enabled)
  let activeProvider: {
    provider_id: string
    name: string
    api_key: string
  } | null = null

  store.providers.forEach(pr => {

    if (pr.provider_id === id) {
      pr.enabled = enabled

      if (enabled) {
        activeProvider = {
          provider_id: pr.provider_id,
          name: pr.provider_name,
          api_key: pr.api_key || '',
        }
      }

    } else {
      pr.enabled = false
    }

  })

  if (activeProvider) {
    store.saveAppConfig('activeProvider', activeProvider)
  } else {
    store.saveAppConfig('activeProvider', {
      provider_id: '',
      name: '',
      api_key: '',
    })
  }

  store.persistLocalProviders()

  // 同步 UI
  const localMap = new Map(
    store.providers.map(p => [p.provider_id, p])
  )

  providerList.value = providerList.value.map(p => ({
    ...p,
    enabled: localMap.get(p.provider_id)?.enabled || false
  }))
}

// 获取 Provider 列表
const getProviders = async (cid: string): Promise<ProviderItem[]> => {

  try {

    const res = await window.api.getLlmProviders(cid)

    if (!Array.isArray(res)) {
      throw new Error('invalid provider list')
    }

    // 1. 后端数据
    const serverList: ProviderItem[] = res.map((p: any) => ({
      provider_id: p.provider_id,
      name: p.provider_name,
      endpoint: p.endpoint,
      description: p.description || '',
      type: p.type || 'openai',
      updated_at: formatTime(p.created_at),
      model_list: Array.isArray(p.model_list) ? p.model_list : [],
    }))

    // 2. 本地缓存同步
    const localMap = new Map(
      store.providers.map(p => [p.provider_id, p])
    )

    const nextLocalProviders: typeof store.providers = []

    for (const sp of serverList) {

      const local = localMap.get(sp.provider_id)

      if (local) {
        nextLocalProviders.push({
          provider_id: sp.provider_id,
          provider_name: sp.name,
          api_key: local.api_key || '',
          enabled: !!local.enabled,
        })
      } else {
        nextLocalProviders.push({
          provider_id: sp.provider_id,
          provider_name: sp.name,
          api_key: '',
          enabled: false,
        })
      }
    }

    store.providers = nextLocalProviders

    // 3. merge UI 数据（优化为 map）
    const localMap2 = new Map(
      nextLocalProviders.map(p => [p.provider_id, p])
    )

    const mergedList: ProviderItem[] = serverList.map(sp => {
      const local = localMap2.get(sp.provider_id)

      return {
        ...sp,
        api_key: local?.api_key || '',
        enabled: local?.enabled || false,
      }
    })

    // 4. activeProvider 同步
    const active = nextLocalProviders.find(p => p.enabled)

    if (active) {
      store.saveAppConfig('activeProvider', {
        provider_id: active.provider_id,
        name: active.provider_name,
        api_key: active.api_key || '',
      })
    } else {
      store.saveAppConfig('activeProvider', {
        provider_id: '',
        name: '',
        api_key: '',
      })
    }

    store.persistLocalProviders()

    return mergedList

  } catch (err) {

    console.error('getProviders failed:', err)

    ElMessage({
      type: 'error',
      message: '获取提供商失败',
      plain: true,
    })

    return []

  }

}

// 删除
const handleDeleteProvider = async (providerId: string) => {
  const index = providerList.value.findIndex(p => p.provider_id === providerId)
  if (index === -1) return

  try {

    await window.api.updateLlmProvider(providerId, cid.value, {
      is_deleted: true
    })

    providerList.value.splice(index, 1)

    // 同步本地缓存
    store.providers = store.providers.filter(p => p.provider_id !== providerId)

    // 如果删除的是当前激活的
    if (store.config.activeProvider?.provider_id === providerId) {
      store.saveAppConfig('activeProvider', {
        provider_id: '',
        name: '',
        api_key: '',
      })
    }

    store.persistLocalProviders()

    ElMessage({
      type: 'success',
      message: '删除成功',
      plain: true,
    })

  } catch (err) {

    console.error('deleteProvider failed:', err)

    ElMessage({
      type: 'error',
      message: '删除提供商失败: ' + String(err),
      plain: true,
    })

  }
}

// ----------------------------------------------------------------------
// Dialog logic
// ----------------------------------------------------------------------

const dialogVisible = ref(false)
const editingProvider = ref<ProviderItem | null>(null)

const openProviderDialog = (providerId: string) => {
  const provider = providerList.value.find(p => p.provider_id === providerId)
  if (!provider) return

  // 从 store 拿本地缓存（api_key / enabled）
  const local = store.providers.find(p => p.provider_id === providerId)

  editingProvider.value = {
    ...provider,
    api_key: local?.api_key || '',
    enabled: local?.enabled || false,
  }

  dialogVisible.value = true
}

const createProvider = () => {
  editingProvider.value = null

  dialogVisible.value = true
}

// 保存
const handleSaveProvider = async (payload: {
  is_editing: boolean
  provider_id?: string
  name: string
  endpoint: string
  type: string
  description: string
  model_list: string[]
  api_key: string
}) => {

  try {

    const providerMeta = JSON.parse(JSON.stringify({
      provider_name: payload.name,
      type: payload.type,
      endpoint: payload.endpoint,
      model_list: payload.model_list,
      description: payload.description,
    }))

    let provider_id = payload.provider_id

    if (!payload.is_editing) {

      const res = await window.api.createLlmProvider(
        cid.value,
        providerMeta
      )

      provider_id = res.provider_id

    } else {

      if (!provider_id) throw new Error('provider_id missing')

      await window.api.updateLlmProvider(
        provider_id,
        cid.value,
        providerMeta
      )
    }

    providerList.value = await getProviders(cid.value)

    // 写回 api_key
    const target = store.providers.find(p => p.provider_id === provider_id)

    if (target) {
      target.api_key = payload.api_key || ''
      target.provider_name = payload.name
    }

    // 同步 activeProvider
    const active = store.providers.find(p => p.enabled)

    if (active) {
      store.saveAppConfig('activeProvider', {
        provider_id: active.provider_id,
        name: active.provider_name,
        api_key: active.api_key || '',
      })
    }

    store.persistLocalProviders()

    ElMessage({
      type: 'success',
      message: '保存成功',
      plain: true,
    })

  } catch (err) {

    console.error('saveProvider failed:', err)

    ElMessage({
      type: 'error',
      message: '保存失败: ' + String(err),
      plain: true,
    })

  }

}

// ----------------------------------------------------------------------
// Test Connection（占位）
// ----------------------------------------------------------------------

const testConnection = () => {
  ElMessage({
    type: 'info',
    message: '请在卡片中测试连接',
    plain: true,
  })
}

// ----------------------------------------------------------------------
// Utils
// ----------------------------------------------------------------------

function formatTime(time: string) {
  return time?.replace?.('T', ' ') || ''
}
</script>


<style scoped>
.provider-page-wrapper {
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

.test-btn,
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

.test-btn {
  width: 90px;
}

.test-btn:hover,
.upload-btn:hover {
  background-color: rgb(147, 195, 196);
}

.test-btn:active,
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
.provider-grid {
  border-top: 4px solid rgba(0, 0, 0, 0.08);
  margin-top: 20px; 
  padding-top: 32px;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
  margin-bottom: 20px;
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
.provider-fade-enter-active {
  transition: 
    opacity 0.5s cubic-bezier(0.215, 0.61, 0.355, 1),
    transform 0.5s cubic-bezier(0.215, 0.61, 0.355, 1);
  transition-delay: calc(var(--stagger-index, 0) * 60ms);
}

.provider-fade-enter-from {
  opacity: 0;
  transform: translateY(20px) scale(0.9);
}

.provider-fade-enter-to {
  opacity: 1;
  transform: translateY(0) scale(1);
}

/* Leave animation - quick fade out */
.provider-fade-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
  position: absolute;
}

.provider-fade-leave-to {
  opacity: 0;
  transform: scale(0.9);
}

/* Move animation for reordering */
.provider-fade-move {
  transition: transform 0.4s cubic-bezier(0.215, 0.61, 0.355, 1);
}
</style>