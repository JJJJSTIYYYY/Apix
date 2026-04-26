<template>
  <div class="role-page-wrapper">
    <div class="ab-bar">
      <div class="ab-bar-btns">
        <el-button 
          type="primary" 
          class="upload-btn"
          @click="createRole"
        >
          新建角色卡
          <el-icon style="padding-left: 4px;"><Plus /></el-icon>
        </el-button>
      </div>
    </div>

    <div class="main-wrapper selectable">
      <h1 style="width: 100%; text-align: center; font-size: 20px;">
        模型角色卡
      </h1>

      <!-- Search -->
      <div class="search-wrapper">
        <el-input
          v-model="searchKeyword"
          placeholder="Search roles by name / definition"
          clearable
          style="max-width: 420px;"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
      </div>

      <!-- Role grid -->
      <transition-group
        v-if="filteredRoleList.length"
        name="role-fade"
        tag="div"
        class="role-grid"
      >
        <RoleCard
          v-for="(role, index) in filteredRoleList"
          :key="role.id"
          :id="role.id"
          :role-name="role.name"
          :role-definition="role.definition"
          :enabled="role.enabled"
          :style="{ '--stagger-index': index }"
          @update:enabled="handleRoleToggle"
          @edit="openRoleDialog"
          @delete="handleDeleteRole"
        />
      </transition-group>

      <!-- Empty -->
      <div
        v-else
        style="width: 100%; text-align: center; color: #999; margin-top: 40px; min-height: 600px; line-height: 400px; font-size: 16px;"
      >
        No roles found
      </div>

      <div style="width: 100%; height: 60px;"></div>

      <div class="setting-group">
        <div class="group-divider">
          <span class="group-label">角色卡设置</span>
        </div>
        <div class="setting-card">
          <div class="setting-title">提升角色卡权限等级</div>
          <div class="setting-control">
            <div class="setting-info" :class="{ danger_info: store.config.higherRolePromptPermission }">
              开启此选项将会将角色卡中的提示词提升至系统层级, 为保证您自身的设备安全, 请不要在提示词中写入危险内容。
            </div>
            <div class="mode-switch">
              <div class="slider" :class="{ right: store.config.higherRolePromptPermission }" />

              <button
                class="off-select"
                :class="{ active: !store.config.higherRolePromptPermission }"
                @click="switchMode('higherRolePromptPermission', 'off')"
              >
                Off
              </button>

              <button
                class="on-select"
                :class="{ active: store.config.higherRolePromptPermission }"
                @click="switchMode('higherRolePromptPermission', 'on')"
              >
                On
              </button>
            </div>
          </div>
        </div>

        <div class="setting-card">
          <div class="setting-title">开启测试专家模式</div>
          <div class="setting-control">
            <div class="setting-info">
              开启测试专家模式，给Agent提供更多的工具来搭建测试工作流，需要开启测试任务管理服务器。
            </div>
            <div class="mode-switch">
              <div class="slider" :class="{ right: store.config.testExpertMode }" />

              <button
                class="off-select"
                :class="{ active: !store.config.testExpertMode }"
                @click="switchMode('testExpertMode', 'off')"
              >
                Off
              </button>

              <button
                class="on-select"
                :class="{ active: store.config.testExpertMode }"
                @click="switchMode('testExpertMode', 'on')"
              >
                On
              </button>
            </div>
          </div>
        </div>
      </div>

      <div style="width: 100%; height: 60px;"></div>

      <!-- Explain -->
      <div class="explain-tag-wrapper">
        <div
          class="explain-tag"
          v-html="roleDocs"
        ></div>
      </div>

      <div style="width: 100%; height: 60px;"></div>
    </div>
  </div>

  <RoleEditDialog
    v-model="dialogVisible"
    :role="editingRole"
    @save="handleSaveRole"
  />
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import RoleCard from './roleCard.vue'
import roleDocs from '../../../assets/docs/roleDocs.html?raw'
import RoleEditDialog from './RoleEditDialog.vue'
import { useAppCacheData } from '../../../store/app'

const store = useAppCacheData()

// ----------------------------------------------------------------------
// Search
// ----------------------------------------------------------------------
const searchKeyword = ref('')

// ----------------------------------------------------------------------
// Role data structure
// ----------------------------------------------------------------------
interface RoleItem {
  id: string
  name: string
  definition: string
  enabled: boolean
}

// 单一数据源
const roleList = computed<RoleItem[]>(() =>
  store.role_prompts.map(role => ({
    id: role.id,
    name: role.roleName,
    definition: role.roleDefinition,
    enabled: role.enabled,
  }))
)

// ----------------------------------------------------------------------
// Filter
// ----------------------------------------------------------------------
const filteredRoleList = computed<RoleItem[]>(() => {
  const keyword = searchKeyword.value.trim().toLowerCase()
  if (!keyword) return roleList.value

  return roleList.value.filter(role =>
    role.name.toLowerCase().includes(keyword) ||
    role.definition.toLowerCase().includes(keyword)
  )
})

// ----------------------------------------------------------------------
// Role logic
// ----------------------------------------------------------------------

// 单选启用
const handleRoleToggle = ({ id, enabled }: { id: string; enabled: boolean }) => {
  let activeRole: { name: string; definition: string } | null = null

  store.role_prompts.forEach(role => {
    if (role.id === id) {
      role.enabled = enabled
      if (enabled) {
        activeRole = {
          name: role.roleName,
          definition: role.roleDefinition,
        }
      }
    } else {
      role.enabled = false
    }
  })

  if (activeRole) {
    store.saveAppConfig('rolePrompt', activeRole)
  } else {
    store.saveAppConfig('rolePrompt', {
      name: '',
      definition: '',
    })
  }

  store.persistRolePrompts()
}

const dialogVisible = ref(false)
const editingRole = ref<RoleItem | null>(null)

const openRoleDialog = (id: string) => {
  const role = roleList.value.find(r => r.id === id)
  if (!role) return

  editingRole.value = { ...role }
  dialogVisible.value = true
}

// 新建
const createRole = () => {
  editingRole.value = null
  dialogVisible.value = true
}

// 保存（不再手动刷新）
const handleSaveRole = (roleData: RoleItem) => {
  const index = store.role_prompts.findIndex(r => r.id === roleData.id)

  const payload = {
    id: roleData.id,
    roleName: roleData.name,
    roleDefinition: roleData.definition,
    enabled: roleData.enabled,
  }

  if (index !== -1) {
    store.role_prompts[index] = payload
  } else {
    store.role_prompts.unshift(payload)
  }

  store.persistRolePrompts()
}

// 删除
const handleDeleteRole = (id: number) => {
  const index = store.role_prompts.findIndex(r => r.id === id)
  if (index === -1) return

  const removed = store.role_prompts[index]

  store.role_prompts.splice(index, 1)

  // 如果删除的是当前启用角色
  if (removed.enabled) {
    store.saveAppConfig('rolePrompt', {
      name: '',
      definition: '',
    })
  }

  store.persistRolePrompts()
}

// ----------------------------------------------------------------------
// Settings
// ----------------------------------------------------------------------

const switchMode = (key: keyof typeof store.config, target: 'on' | 'off') => {
  const value = target === 'on'

  // Update reactive config
  store.config[key] = value as any

  // Persist to local storage / backend
  store.saveAppConfig(key as string, value)
}
</script>

<style scoped>
.role-page-wrapper {
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
  padding: 0 12px 0 10px;
  transition: all 0.13s ease, border-color 0.18s ease, box-shadow 0.18s ease;
}

.search-wrapper.is-focused :deep(.el-input__wrapper) {
  background: rgba(255, 255, 255, 0.536);
  border-color: rgba(255, 255, 255, 0.76);
  z-index: 99;
}

/* ---------- Grid layout ---------- */
.role-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
  margin-bottom: 20px;
  min-height: 600px;
}

/* ---------- Settings layout ---------- */
.setting-group {
  display: grid;
  width: 100%;
  grid-template-columns: 50% 50%;
  gap: 18px;
  width: 100%;
  padding-top: 8px;
  margin-top: 8px;
}

.group-divider {
  grid-column: 1 / -1;
  display: flex;
  align-items: center;
  margin-bottom: 4px;
}

.group-label {
  position: relative;
  width: 100%;
  font-size: 18px;
  font-weight: 600;
  color: rgb(136, 202, 197);
  text-transform: uppercase;
  letter-spacing: 0.8px;
  padding: 4px 12px;
  background: rgba(136, 202, 197, 0.1);
  border-radius: 6px;
  border: 1px solid rgba(136, 202, 197, 0.2);
}

.setting-card {
  position: relative;
  padding: 16px 18px;
  border-radius: 12px;
  height: 64px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  background: rgba(255, 255, 255, 0.55);
  box-shadow:
    inset 0 0 0 1px rgba(0, 0, 0, 0.04),
    0 2px 8px rgba(0, 0, 0, 0.06);
  transition: all 0.2s ease;
}

.setting-card:hover {
  position: relative;
  transform: translateY(-1px);
  box-shadow:
    inset 0 0 0 1px rgba(0, 0, 0, 0.06),
    0 6px 18px rgba(0, 0, 0, 0.12);
}

.setting-title {
  font-size: 14px;
  font-weight: 600;
  color: #2f3a3a;
  position: relative;
}

.setting-control {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 16px;
  width: calc(100% - 78px);
}

.setting-info {
  font-size: 12px;
  color: #5a6a6a;
  position: relative;
  -webkit-transition: all 0.25s cubic-bezier(0.215, 0.61, 0.355, 1);
  transition: all 0.25s cubic-bezier(0.215, 0.61, 0.355, 1);
}

.danger_info {
  color: #ff2f28ca;
  -webkit-transition: all 0.25s cubic-bezier(0.215, 0.61, 0.355, 1);
  transition: all 0.25s cubic-bezier(0.215, 0.61, 0.355, 1);
}

.mode-switch {
  position: absolute;
  right: 14px;
  display: flex;
  background: rgba(226, 226, 226, 0.32);
  border-radius: 999px;
  border: 1px solid rgba(213, 213, 213, 0.318);
  box-shadow: inset 1px -1px 16px rgba(117, 187, 248, 0.083);
}

.mode-switch button {
  flex: 1;
  height: 24px;
  border: none;
  background-color: transparent;
  cursor: pointer;
  z-index: 1;
  font-size: 12px;
  color: #4040409A;
  transition: color 0.25s ease;
}

.mode-switch button.active {
  color: #0000009A;
}

/* Slider */
.slider {
  position: absolute;
  width: calc(50% + 4px);
  height: calc(100% + 2px);
  margin-top: -1px;
  margin-left: -1px;
  border-radius: 32px;
  transition: all 0.3s cubic-bezier(0.215, 0.61, 0.355, 1);
  box-shadow:
    0 8px 24px rgba(62, 67, 66, 0.12),
    0 0 0 2px rgba(136, 202, 196, 0.471);
  background-color: #ffffff2c;
}

.slider.right {
  transform: translateX(82%);
}

.mode-switch:active:deep(.slider) {
  z-index: 999;
  box-shadow:
    0 8px 24px rgba(62, 67, 66, 0.12),
    0 0 0 2px color-mix(in srgb, rgba(136, 202, 196, 0.567) 25%, transparent);
  -webkit-backdrop-filter: saturate(180%) blur(16px);
  backdrop-filter: saturate(180%) blur(3px);
  -webkit-transition: all 0.3s cubic-bezier(0.215, 0.61, 0.355, 1);
  transition: all 0.3s cubic-bezier(0.215, 0.61, 0.355, 1);
  background-color: color-mix(in srgb, #ebebeb83 1%, transparent);
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
.role-fade-enter-active {
  transition: 
    opacity 0.5s cubic-bezier(0.215, 0.61, 0.355, 1),
    transform 0.5s cubic-bezier(0.215, 0.61, 0.355, 1);
  transition-delay: calc(var(--stagger-index, 0) * 60ms);
}

.role-fade-enter-from {
  opacity: 0;
  transform: translateY(20px) scale(0.9);
}

.role-fade-enter-to {
  opacity: 1;
  transform: translateY(0) scale(1);
}

/* Leave animation - quick fade out */
.role-fade-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
  position: absolute;
}

.role-fade-leave-to {
  opacity: 0;
  transform: scale(0.9);
}

/* Move animation for reordering */
.role-fade-move {
  transition: transform 0.4s cubic-bezier(0.215, 0.61, 0.355, 1);
}
</style>