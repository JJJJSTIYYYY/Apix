<template>
  <div class="role-page-wrapper">

    <div class="main-wrapper">

      <div class="page-title-wrapper">
        <div class="title-wrapper">
          <h1 class="data-page-title">
            模型角色卡
          </h1>

          <div class="btn-wrapper">
            <el-button 
              type="primary" 
              class="upload-btn"
              @click="createRole"
            >
              新建角色卡
              <el-icon style="padding-left: 4px;"><Plus /></el-icon>
            </el-button>
          </div>

          <!-- Search -->
          <div class="search-wrapper">
            <el-input
              v-model="searchKeyword"
              placeholder="通过角色名称、角色定义搜索角色卡"
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
<span>1. 角色卡是什么: 角色卡是为 Agent 预先设定的身份与行为风格模板，用于定义其在对话中的角色定位、语言风格及响应方式。</span>

<span>2. 如何创建: 点击页新建角色卡，输入角色名称及定义后保存即可。可通过下方设置中的`提升角色卡权限等级`将提示词加入系统提示词中，否则将作为用户提示词加入消息列表头部。提升角色卡权限时，请确保角色卡中无危险指令！</span>

<span>3. 使用建议与注意事项: 建议根据当前对话场景选择合适的角色卡，同一时刻只允许开启一张角色卡。创建角色卡时请不要输入危险指令。</span>
        </div>
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
          <div class="setting-title">允许Agent访问任务流</div>
          <div class="setting-control">
            <div class="setting-info">
              允许Agent访问任务流，需要先提交任务流文件至服务器。
            </div>
            <div class="mode-switch">
              <div class="slider" :class="{ right: store.config.enableTaskFlow }" />

              <button
                class="off-select"
                :class="{ active: !store.config.enableTaskFlow }"
                @click="switchMode('enableTaskFlow', 'off')"
              >
                Off
              </button>

              <button
                class="on-select"
                :class="{ active: store.config.enableTaskFlow }"
                @click="switchMode('enableTaskFlow', 'on')"
              >
                On
              </button>
            </div>
          </div>
        </div>
      </div>

      <div style="width: 100%; height: 60px;"></div>

      <!-- Explain -->
      <!-- <div class="explain-tag-wrapper">
        <div
          class="explain-tag"
          v-html="roleDocs"
        ></div>
      </div>

      <div style="width: 100%; height: 60px;"></div> -->
    </div>
  </div>

  <RoleEditDialog
    v-if="dialogVisible"
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
      else {
        activeRole = {
          name: '',
          definition: '',
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

  store.persistState('role_prompts')
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

  store.persistState('role_prompts')
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

  store.persistState('role_prompts')
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

/* ---------- Grid layout ---------- */
.role-grid {
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

<style scoped>
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
  gap: 6px
}

.group-label {
  position: relative;
  width: 100%;
  height: 30px;
  font-size: 18px;
  font-weight: 600;
  color: var(--apix-primary-color);
  text-transform: uppercase;
  letter-spacing: 0.8px;
  padding: 0 12px;
  border-left: 3px solid var(--apix-primary-color);
}

.setting-card {
  position: relative;
  padding: 16px 18px;
  border-radius: var(--apix-border-radius-base);
  height: 64px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  background: var(--apix-panel-layer-3-background);
  box-shadow: var(--apix-shadow-layer-1);
  transition: transform 0.2s var(--apix-cubic-bezier),
    box-shadow 0.2s var(--apix-cubic-bezier);
}

.setting-card:hover {
  position: relative;
  transform: translateY(-2px);
  box-shadow: var(--apix-shadow-layer-3);
}

.setting-label {
  margin-right: 6px;
  padding: 2px 6px;
  color: #059669;
  border: 1px solid rgba(5, 150, 105, 0.1);
  background: rgba(5, 150, 105, 0.05);
  border-radius: 16px;
  font-size: 10px;
}

.danger-label {
  margin-right: 6px;
  padding: 2px 6px;
  color: #960505;
  border: 1px solid rgba(150, 22, 5, 0.1);
  background: rgba(150, 22, 5, 0.05);
  border-radius: 16px;
  font-size: 10px;
}

.setting-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--apix-darkest-color);
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
  color: var(--apix-secondary-dark-color);
  position: relative;
  transition: color 0.25s var(--apix-cubic-bezier);
}

.danger_info {
  color: var(--apix-danger-color);
  transition: color 0.25s var(--apix-cubic-bezier);
}

/* ---------------------------------- */
.mode-switch {
  position: absolute;
  right: 14px;
  display: flex;
  background: color-mix(in srgb, var(--apix-default-light-color) 32%, transparent);
  border-radius: 999px;
  border: 1px solid color-mix(in srgb, var(--apix-border-light) 31.8%, transparent);
  box-shadow: inset 1px -1px 16px color-mix(in srgb, var(--apix-primary-color) 8.3%, transparent);
}

.mode-switch button {
  flex: 1;
  height: 24px;
  border: none;
  background-color: transparent;
  cursor: pointer;
  z-index: 1;
  font-size: 12px;
  color: var(--apix-secondary-dark-color);
  transition: color 0.25s ease;
}

.mode-switch button.active {
  color: var(--apix-darkest-color);
}

/* 共用 active 时的光晕与背景效果（original used color-mix） */
.mode-switch:active .slider,
.mode-switch:active:deep(.slider) {
  z-index: 999;
  box-shadow:
    var(--apix-shadow-lg),
    0 0 0 2px color-mix(in srgb, var(--apix-primary-color) 14%, transparent);
  backdrop-filter: saturate(180%) blur(3px);
  transition: all 0.3s var(--apix-cubic-bezier);
  background-color: color-mix(in srgb, var(--apix-default-light-color) 1%, transparent);
}

.highlight-select {
  color: var(--apix-secondary-dark-color);
  transition: color 0.25s ease;
}

.highlight-select.right {
  color: var(--apix-darkest-color);
  transition: color 0.25s ease;
}

/* Slider */
.slider {
  position: absolute;
  width: calc(50% + 4px);
  height: calc(100% + 2px);
  margin-top: -1px;
  margin-left: -1px;
  border-radius: 32px;
  transition: all 0.3s var(--apix-cubic-bezier);
  box-shadow:
    var(--apix-shadow-md),
    0 0 0 2px color-mix(in srgb, var(--apix-primary-color) 47.1%, transparent);
  background-color: var(--apix-lightest-color);
}

.slider.right {
  transform: translateX(87%);
}
/* ---------------------------------- */
</style>