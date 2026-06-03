<template>
  <div class="mcp-page-wrapper">
    <div class="main-wrapper">
      <div class="page-title-wrapper">
        <div class="title-wrapper">
          <h1 class="data-page-title">
            MCP 服务
          </h1>

          <div class="btn-wrapper">
            <el-button
              type="primary"
              class="upload-btn"
              @click="createMcp"
            >
              新建 MCP
              <el-icon style="padding-left:4px;">
                <Plus />
              </el-icon>
            </el-button>
          </div>

          <div class="search-wrapper">
            <el-input
              v-model="searchKeyword"
              placeholder="通过名称、连接地址、描述搜索 MCP"
              clearable
              style="max-width:420px;"
            >
              <template #prefix>
                <el-icon>
                  <Search />
                </el-icon>
              </template>
            </el-input>
          </div>
        </div>

        <div class="page-docs">
          <span>
            1. MCP（Model Context Protocol）用于向Agent提供工具能力，例如文件系统、数据库、浏览器自动化等。通过MCP，Agent可以安全地扩展对本地或远程资源的操作。
          </span>

          <span>
            2. 支持stdio与streamable_http两种连接方式。配置完成后系统会自动发现该MCP提供的工具。stdio适用于本地子进程，streamable_http适用于远程服务或跨网络调用。
          </span>

          <span>
            3. 启用 MCP 后，Agent在执行任务时可自动调用其中的工具。请确保服务稳定可访问。建议先通过测试工具验证连接，再应用于实际任务。
          </span>

          <span>
            4. 为防止提示词与工具集污染，不建议在使用MCP的同时开启内置工具权限。建议有使用MCP的需求时，关闭除子代理以外的内置工具权限，仅通过MCP提供工具能力。
          </span>
        </div>
      </div>

      <transition-group
        v-if="filteredMcpList.length"
        name="mcp-fade"
        tag="div"
        class="mcp-grid"
      >
        <McpCard
          v-for="(mcp, index) in filteredMcpList"
          :key="mcp.mcp_id"
          :client_id="cid"
          :mcp_id="mcp.mcp_id"
          :name="mcp.name"
          :description="mcp.description"
          :transport="mcp.transport"
          :endpoint="mcp.endpoint"
          :tool-count="mcp.tool_count"
          :enabled="mcp.enabled"
          :updated-at="mcp.created_at"
          :config="mcp.config"
          :style="{ '--stagger-index': index }"
          @update:enabled="handleMcpToggle"
          @delete="handleDeleteMcp"
          @edit="openMcpDialog"
          @getTools="handleGetTools"
        />
      </transition-group>

      <div
        v-else
        style="
          width:100%;
          text-align:center;
          color:#999;
          margin-top:40px;
          min-height:600px;
          line-height:400px;
          font-size:16px;
        "
      >
        No MCP found
      </div>

      <div style="height:60px;"></div>
    </div>
  </div>

  <McpEditDialog
    v-if="dialogVisible"
    v-model="dialogVisible"
    :mcp="editingMcp"
    @save="handleSaveMcp"
  />
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Search, Plus } from '@element-plus/icons-vue'
import McpCard from './mcpCard.vue'
import McpEditDialog from './McpEditDialog.vue'
import { useAuthStore } from '../../../store/auth'

type McpTransport = 'stdio' | 'http'

interface McpConfig {
  command?: string
  args?: string[]
  env?: Record<string, string>
  lifecycle?: string

  cwd?: string
  encoding?: string

  url?: string

  headers?: Record<string, string>

  session_kwargs?: Record<string, any>
  terminate_on_close?: boolean
}

interface McpItem {
  mcp_id: string
  name: string
  description: string
  transport: McpTransport
  endpoint: string
  tool_count: number
  enabled: boolean
  created_at: string
  config: McpConfig
}

const authStore = useAuthStore()
const cid = ref('')

const searchKeyword = ref('')
const mcpList = ref<McpItem[]>([])

onMounted(async () => {
  try {
    await authStore.restore()
    cid.value = authStore.user.user_uid
    mcpList.value = await getMcps()
  } catch (err) {
    console.error(err)
  }
})

const filteredMcpList = computed(() => {
  const keyword = searchKeyword.value.trim().toLowerCase()
  if (!keyword) return mcpList.value

  return mcpList.value.filter(mcp =>
    mcp.name.toLowerCase().includes(keyword) ||
    mcp.endpoint.toLowerCase().includes(keyword) ||
    mcp.description.toLowerCase().includes(keyword)
  )
})

async function getMcps(): Promise<McpItem[]> {
  try {
    const rawMcpList = await window.api?.getMcpServers(cid.value)
    if (Array.isArray(rawMcpList)) {
      return rawMcpList.map((mcp: any) => ({
        mcp_id: mcp.mcp_id,
        name: mcp.mcp_name,
        description: mcp.description,
        transport: mcp.transport,
        endpoint: mcp.endpoint,
        tool_count: mcp.tool_count || 0,
        enabled: Boolean(mcp.enabled) || false,
        created_at: formatTime(mcp.created_at),
        config: mcp.config || {},
      }))
    } else {
      console.warn('getMcpServers returned non-array:', rawMcpList)
      return []
    }
  } catch (err) {
    console.error(err)
    ElMessage({
      type: 'error',
      message: '获取 MCP 列表失败',
      plain: true,
    })
    return []
  }
}

async function handleMcpToggle({ id, enabled }: { id: string; enabled: boolean }) {
  const current = mcpList.value.find(m => m.mcp_id === id)
  if (!current) return

  try {
    if (enabled) {
      const sameNameEnabledMcps = mcpList.value.filter(
        m =>
          m.mcp_id !== id &&
          m.name === current.name &&
          m.enabled
      )

      for (const mcp of sameNameEnabledMcps) {
        mcp.enabled = false
      }

      await Promise.all(
        sameNameEnabledMcps.map(mcp =>
          window.api.updateMcpServer(
            mcp.mcp_id,
            cid.value,
            { enabled: false }
          )
        )
      )
    }

    current.enabled = enabled

    await window.api.updateMcpServer(
      id,
      cid.value,
      { enabled }
    )

  } catch (err) {

    console.warn(
      '[handleMcpToggle] window.api.updateMcpServer failed:',
      err
    )

    current.enabled = !enabled

    ElMessage({
      type: 'error',
      message: 'MCP 状态更新失败',
      plain: true,
    })
  }
}

async function handleDeleteMcp(mcpId: string) {
  try {
    await window.api.updateMcpServer(mcpId, cid.value, { is_deleted: true })

    mcpList.value = mcpList.value.filter(m => m.mcp_id !== mcpId)

    ElMessage({
      type: 'success',
      message: '删除成功',
      plain: true,
    })
  } catch (err) {
    console.error(err)
    ElMessage({
      type: 'error',
      message: '删除失败',
      plain: true,
    })
  }
}

function handleGetTools(id: string, toolCount: number) {
  const item = mcpList.value.find(m => m.mcp_id === id)
  if (item) {
    item.tool_count = toolCount
  }
}

const dialogVisible = ref(false)
const editingMcp = ref<McpItem | null>(null)

function openMcpDialog(mcpId: string) {
  editingMcp.value = mcpList.value.find(m => m.mcp_id === mcpId) || null
  dialogVisible.value = true
}

function createMcp() {
  editingMcp.value = null
  dialogVisible.value = true
}

async function handleSaveMcp(payload: {
  is_editing: boolean
  mcp_id?: string
  name: string
  description: string
  transport: McpTransport
  config: McpConfig
}) {
  const endpoint = payload.transport === 'stdio'
    ? ((payload.config.command + ' ' + payload.config.args?.join(' ')) || '')
    : (payload.config.url || '')

  try {

    const mcpMeta = JSON.parse(JSON.stringify({
      mcp_name: payload.name,
      transport: payload.transport,
      endpoint: endpoint,
      config: payload.config,
      description: payload.description,
    }))

    let mcp_id = payload.mcp_id

    if (!payload.is_editing) {

      const res = await window.api.createMcpServer(
        cid.value,
        mcpMeta
      )

      mcp_id = res.mcp_id

    } else {

      if (!mcp_id) throw new Error('mcp_id missing')

      await window.api.updateMcpServer(
        mcp_id,
        cid.value,
        mcpMeta
      )
    }

    mcpList.value = await getMcps(cid.value)

    ElMessage({
      type: 'success',
      message: '保存成功',
      plain: true,
    })

  } catch (err) {

    console.error('saveMcp failed:', err)

    ElMessage({
      type: 'error',
      message: '保存失败: ' + String(err),
      plain: true,
    })

  }

}

function formatTime(time: string) {
  return time?.replace?.('T', ' ').replace('Z', '') || ''
}
</script>

<style scoped>
.mcp-page-wrapper {
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

.mcp-grid {
  border-top: 4px solid var(--apix-secondary-light-color);
  margin-top: 20px;
  padding-top: 32px;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
  margin-bottom: 20px;
}

.mcp-fade-enter-active {
  transition:
    opacity 0.5s cubic-bezier(0.215, 0.61, 0.355, 1),
    transform 0.5s cubic-bezier(0.215, 0.61, 0.355, 1);
  transition-delay: calc(var(--stagger-index, 0) * 60ms);
}

.mcp-fade-enter-from {
  opacity: 0;
  transform: translateY(20px) scale(0.9);
}

.mcp-fade-enter-to {
  opacity: 1;
  transform: translateY(0) scale(1);
}

.mcp-fade-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
  position: absolute;
}

.mcp-fade-leave-to {
  opacity: 0;
  transform: scale(0.9);
}

.mcp-fade-move {
  transition: transform 0.4s cubic-bezier(0.215, 0.61, 0.355, 1);
}
</style>
