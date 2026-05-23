<template>
  <div class="provider-page-wrapper">
    <div class="main-wrapper">

      <div class="page-title-wrapper">
        <div class="title-wrapper">
          <h1 class="data-page-title">
            LLM 供应商
          </h1>

          <div class="btn-wrapper">
            <el-button 
              type="primary" 
              class="upload-btn"
              @click="createProvider"
            >
              新建供应商
              <el-icon style="padding-left: 4px;"><Plus /></el-icon>
            </el-button>

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
              placeholder="通过供应商名称、endpoint、供应商描述搜索供应商"
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
<span>1. 什么是自定义大模型供应商: 系统支持接入符合 OpenAI API 兼容协议的大模型服务，以提供非系统内置的模型服务。</span>

<span>2. 如何配置与添加: 请准备供应商的 API Endpoint、API Key，点击新建供应商并填写上述信息并保存。添加后建议先进行连接测试，确认响应正常后再用于对话任务。</span>

<span>3. 注意事项与建议: 请确保供应商服务稳定可用，部分第三方模型可能在响应速度、上下文长度或兼容协议上存在差异。系统不能保证使用自定义供应商时所有功能正常使用。</span>
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
    v-if="dialogVisible"
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
    console.error('[Provider page onMounted error]:', err)
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

  store.persistState('providers')

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

    store.persistState('providers')

    return mergedList

  } catch (err) {

    console.error('getProviders failed:', err)

    ElMessage({
      type: 'error',
      message: '获取供应商失败',
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

    store.persistState('providers')

    ElMessage({
      type: 'success',
      message: '删除成功',
      plain: true,
    })

  } catch (err) {

    console.error('deleteProvider failed:', err)

    ElMessage({
      type: 'error',
      message: '删除供应商失败: ' + String(err),
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

    store.persistState('providers')

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

.test-btn,
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

.test-btn:hover,
.upload-btn:hover {
  background-color: var(--apix-primary-hover);
}

.test-btn:active,
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
.provider-grid {
  border-top: 4px solid var(--apix-secondary-light-color);
  margin-top: 20px; 
  padding-top: 32px;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
  margin-bottom: 20px;
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