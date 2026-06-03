<template>
  <div class="mcp-card selectable">
    <!-- Header -->
    <div class="mcp-header">
      <el-switch
        v-model="localEnabled"
        size="small"
        @change="handleToggle"
      />

      <div class="mcp-actions">
        <button
          class="icon-btn delete-btn"
          title="Delete MCP"
          @click="handleDelete"
        >
          <el-icon><Delete /></el-icon>
        </button>

        <button
          class="icon-btn"
          title="Edit MCP"
          @click="handleEdit"
        >
          <el-icon><Setting /></el-icon>
        </button>
      </div>
    </div>

    <!-- Content -->
    <div class="mcp-content">
      <div class="mcp-title-wrapper">
        <div class="mcp-icon">
          <svg t="1780298416658" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="9869" width="20" height="20"><path d="M601.813333 299.904c35.84 0 75.52 9.386667 98.901334 22.784v72.448c-32-14.592-62.08-21.632-89.813334-21.632-66.389333 0-111.317333 47.36-111.317333 143.786667 0 25.685333 5.248 48.469333 15.274667 67.754666 20.565333 39.722667 55.424 61.952 93.653333 64.853334l10.538667 0.64c29.141333 0 59.221333-11.178667 81.664-28.117334v80.682667c-27.221333 15.786667-56.874667 20.992-96.512 20.992-113.237333 0-187.306667-81.194667-187.306667-206.848 0-44.970667 7.68-84.096 23.466667-116.821333 31.018667-64.853333 89.344-100.522667 161.450666-100.522667zM189.866667 600.277333l0.938666 5.845334 0.938667-5.845334 45.397333-292.736H374.186667v409.002667h-75.946667V379.989333h-3.84l-57.301333 336.554667H144.469333L87.594667 379.989333h-4.266667v336.554667H7.296V307.541333h137.130667l45.354666 292.693334z" p-id="9870" fill="currentColor"></path><path d="M903.466667 307.541333c70.186667 0 113.194667 47.914667 113.194666 132.608 0 84.138667-42.965333 132.053333-113.194666 132.096H822.186667v144.298667h-78.805334V307.541333h160.085334z m-81.28 187.562667h74.112c32 0 49.664-23.978667 49.664-54.954667 0-32.128-17.664-55.466667-49.664-55.466666H822.186667v110.421333z" p-id="9871" fill="currentColor"></path></svg>
        </div>

        <div class="mcp-title" :title="name">
          {{ name }}
        </div>
      </div>

      <div class="mcp-description-wrapper">
        <div class="mcp-description" :title="description">
          {{ description }}
        </div>
      </div>

      <div
        class="footer-tag endpoint-tag"
        :title="endpoint"
      >
        <el-icon><Link /></el-icon>
        <span class="tag-text">
          {{ endpoint }}
        </span>
      </div>
    </div>

    <!-- Footer -->
    <div class="mcp-footer">
      <div class="footer-tag transport-tag">
        <el-icon><Connection /></el-icon>
        <span>{{ transport }}</span>
      </div>

      <div
        class="footer-tag tools-tag"
        :class="{ loading: loadingTools }"
        @click="!loadingTools && handleGetTools()"
        style="cursor: pointer;"
      >
        <el-icon class="tools-icon">
          <Tools />
        </el-icon>

        <span>
          {{ loadingTools ? 'Loading...' : `${toolCount} tools` }}
        </span>
      </div>

      <div
        class="footer-tag time-tag"
        :title="updatedAt"
      >
        <el-icon><Clock /></el-icon>
        <span>{{ updatedAt }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, toRaw, watch } from 'vue'
import { ConfirmDialog } from '../comp/confirmDialog.js'
import {
  Delete,
  Setting,
  Connection,
  Link,
  Clock,
  Tools,
} from '@element-plus/icons-vue'

/* ---------------- Props ---------------- */

const props = defineProps({
  client_id: { type: String, required: true, },
  mcp_id: { type: String, required: true, },
  name: { type: String, required: true, },
  description: { type: String, default: '', },
  transport: { type: String, required: true, },
  endpoint: { type: String, default: '', },
  toolCount: { type: Number, default: 0, },
  enabled: { type: Boolean, default: false, },
  updatedAt: { type: String, required: true, },
  config: { type: Object, required: true, },
})

/* ---------------- Emits ---------------- */

const emit = defineEmits([
  'edit',
  'delete',
  'update:enabled',
  'getTools',
])

/* ---------------- Local state ---------------- */

const localEnabled = ref(props.enabled)

watch(
  () => props.enabled,
  (val) => {
    localEnabled.value = val
  }
)

/* ---------------- Methods ---------------- */

const handleToggle = (val: boolean) => {
  emit('update:enabled', {
    id: props.mcp_id,
    enabled: val,
  })
}

const handleDelete = async () => {
  try {
    await ConfirmDialog.confirm(
      `确定要删除 MCP "${props.name}" 吗？`,
      '删除确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )

    emit('delete', props.mcp_id)
  } catch {
    return
  }
}

const handleEdit = () => {
  emit('edit', props.mcp_id)
}

const loadingTools = ref(false)
const handleGetTools = async () => {
  if (loadingTools.value) return
  loadingTools.value = true

  try {
    const tools = await window.api.getMcpTools(props.mcp_id, props.client_id, {
      mcp_name: props.name,
      transport: props.transport,
      config: toRaw(props.config),
    })

    if (!tools || tools.length === 0) {
      ElMessage({
        type: 'info',
        message: '该MCP没有绑定任何工具',
        plain: true,
      })
      return
    }

    try {
      await ConfirmDialog.confirm(
        `本次更新 ${tools.length} 个工具：<br><br>` +
        `${tools.join('、')}<br>`,
        `${props.name} 已更新`,
        {
          confirmButtonText: '确定',
          cancelButtonText: '',
          type: 'info',
        }
      )
    } catch (err) {
      return
    }

    emit('getTools', props.mcp_id, tools.length)
  } catch (err) {
    console.warn('[handleGetTools] Failed to get tools:', err)
  } finally {
    loadingTools.value = false
  }
}
</script>

<style scoped>
.mcp-card {
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

.mcp-card:hover {
  border: 1px solid var(--apix-primary-color);
}

.mcp-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  flex-shrink: 0;
}

.mcp-actions {
  display: flex;
  gap: 4px;
}

.mcp-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 12px;
}

.mcp-title-wrapper {
  display: grid;
  grid-template-columns: 30px auto;
  align-items: center;
  gap: 8px;
}

.mcp-icon {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  background: linear-gradient(135deg, #0ea5e9 0%, #38bdf8 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 14px;
}

.mcp-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--apix-default-dark-color);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mcp-description-wrapper {
  flex: 1;
  overflow: hidden;
}

.mcp-description {
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

.mcp-footer {
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

.footer-tag .el-icon {
  flex-shrink: 0;
}

.tag-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}

.endpoint-tag {
  color: #2563eb;
  background: rgba(37, 99, 235, 0.1);
}

.transport-tag {
  color: #7c3aed;
  background: rgba(124, 58, 237, 0.1);
}

.tools-tag {
  color: #d97706;
  background: rgba(217, 119, 6, 0.1);
}

.tools-icon {
  display: flex;
}

.tools-tag.loading .tools-icon {
  animation: tools-spin 1s linear infinite;
}

@keyframes tools-spin {
  from {
    transform: rotate(0deg);
  }

  to {
    transform: rotate(360deg);
  }
}

.time-tag {
  color: #64748b;
  grid-column: 1 / -1;
}

.enabled-tag {
  color: #15803d;
  background: rgba(34, 197, 94, 0.12);
}

.disabled-tag {
  color: #dc2626;
  background: rgba(239, 68, 68, 0.12);
}

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
