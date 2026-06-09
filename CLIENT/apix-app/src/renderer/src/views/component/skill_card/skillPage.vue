<template>
  <div class="skill-page-wrapper">
    <div class="main-wrapper">

      <div class="page-title-wrapper">
        <div class="title-wrapper">
          <h1 class="data-page-title">
            Agent 技能包
          </h1>

          <div class="btn-wrapper">
            <el-button
              type="primary"
              class="upload-btn"
              @click="uploadSkill"
            >
              上传技能包
              <el-icon class="el-icon--right"><Upload /></el-icon>
            </el-button>
          </div>

          <!-- Search -->
          <div class="search-wrapper">
            <el-input
              v-model="searchKeyword"
              placeholder="通过技能名称、技能描述搜索技能包"
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
<span>1. 技能包是什么: 技能包是为 Agent 预先封装好的功能模块，用于执行特定任务。所有代码均在本地运行，请不要上传任何恶意代码。</span>

<span>2. 如何正确上传: 上传 ZIP 格式的文件，根目录下必须包含 SKILL.md，并符合相关协议要求。请避免上传同名的技能包，系统会默认保留最新上传的版本。</span>

<span>3. 使用建议与常见问题: 建议一次只开启与当前任务相关的技能包。若上传或加载失败，请检查是否存在以下情况：缺少 SKILL.md 文件、SKILL.md 中缺少 YAML 格式的元数据，或解压后的文件夹名称与技能名不一致。</span>
        </div>
      </div>

      <!-- Skill grid -->
      <transition-group
        v-if="filteredSkillList.length"
        name="skill-fade"
        tag="div"
        class="skill-grid"
      >
        <SkillPackageCard
          v-for="(skill, index) in filteredSkillList"
          :key="skill.skill_id"
          :skill-id="skill.skill_id"
          :skill-name="skill.skill_name"
          :skill-description="skill.skill_description"
          :skill-version="skill.skill_version"
          :package-size="skill.package_size"
          :upload-at="skill.upload_at"
          :enabled="skill.enabled"
          :style="{ '--stagger-index': index }"
          @update:enabled="handleSkillToggle"
          @delete="handleDeleteSkill"
        />
      </transition-group>

      <!-- Empty -->
      <div
        v-else
        style="width: 100%; text-align: center; color: #999; margin-top: 40px; min-height: 600px; line-height: 400px; font-size: 16px;"
      >
        No skills found
      </div>

      <div style="width: 100%; height: 60px;"></div>

      <!-- Explain -->
      <!-- <div class="explain-tag-wrapper">
        <div
          class="explain-tag"
          v-html="skillDocs"
        ></div>
      </div>

      <div style="width: 100%; height: 60px;"></div> -->

    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onActivated } from 'vue'
import { ElMessage } from 'element-plus'
import SkillPackageCard from './skillCard.vue'
import skillDocs from '../../../assets/docs/skillDocs.html?raw'
import { useAuthStore } from '../../../store/auth'

const authStore = useAuthStore()
const cid = ref('')

onMounted(async () => {
  try {
    await authStore.restore()
    cid.value = authStore.user.user_uid
    skillList.value = await getAvailableSkills(cid.value)
  } catch (err) {
    console.error('[Skill page onMounted error]:', err)
  }
})

onActivated(async () => {
  if (cid.value === '') return
  skillList.value = await getAvailableSkills(cid.value)
})

// ----------------------------------------------------------------------
// Search
// ----------------------------------------------------------------------

const searchKeyword = ref('')

// ----------------------------------------------------------------------
// Skill structure
// ----------------------------------------------------------------------

interface SkillItem {
  skill_id: string
  skill_name: string
  skill_description: string
  skill_version: string
  package_size: string
  upload_at: string
  enabled: boolean
}

// ----------------------------------------------------------------------
// Mock data (未来替换为后端 API)
// ----------------------------------------------------------------------

const skillList = ref<SkillItem[]>([])

// ----------------------------------------------------------------------
// Filter
// ----------------------------------------------------------------------

const filteredSkillList = computed(() => {
  const keyword = searchKeyword.value.trim().toLowerCase()

  if (!keyword) return skillList.value

  return skillList.value.filter(skill =>
    skill.skill_name.toLowerCase().includes(keyword) ||
    skill.skill_description.toLowerCase().includes(keyword)
  )
})

// ----------------------------------------------------------------------
// Skill logic
// ----------------------------------------------------------------------
// 获取
const getAvailableSkills = async (cid: string): Promise<SkillItem[]> => {

  try {

    const res = await window.api.getAvailableSkills(cid, 999)

    if (!Array.isArray(res)) {
      throw new Error('invalid skill list')
    }

    const skills: SkillItem[] = res.map((s: any) => ({
      skill_id: s.skill_id,
      skill_name: s.skill_name,
      skill_description: s.skill_description,
      skill_version: s.skill_version,
      package_size: s.package_size,
      upload_at: formatTime(s.upload_at),
      enabled: Boolean(s.is_active),
    }))

    return skills

  } catch (err) {

    console.error('getAvailableSkills failed:', err)

    ElMessage({
      type: 'error',
      message: '获取技能列表失败',
      plain: true,
    })

    return []

  }

}

// 启用
const handleSkillToggle = async ({
  skill_id,
  enabled,
}: {
  skill_id: string
  enabled: boolean
}) => {
  const skill = skillList.value.find(s => s.skill_id === skill_id)
  if (!skill) return
  try {
    await window.api.updateSkillStatus(cid.value, skill_id, enabled)
    skill.enabled = enabled
  }
  catch (err) {
    console.error('uploadSkill failed:', err)

    ElMessage({
      type: 'error',
      message: '技能包更新失败: ' + String(err),
      plain: true,
    })

  }
}

// 删除
const handleDeleteSkill = async (skillId: string) => {
  const index = skillList.value.findIndex(s => s.skill_id === skillId)
  if (index === -1) return
  try {
    await window.api.deleteSkill(cid.value, skillId)
    skillList.value.splice(index, 1)
  }
  catch (err) {
    console.error('uploadSkill failed:', err)

    ElMessage({
      type: 'error',
      message: '技能包删除失败: ' + String(err),
      plain: true,
    })

  }
}

// 上传
const isUploading = ref(false)

const uploadSkill = async () => {
  if (isUploading.value) return

  try {
    const result = await window.api.openFileDialog('file', ['zip'])

    if (result.canceled || result.filePaths.length === 0) return

    isUploading.value = true

    const uploadTasks = result.filePaths.map((path) => {
      const plainFile = {
        name: path.split('/').pop(),
        path,
      }
      return window.api.uploadSkillFiles(cid.value, [plainFile])
    })

    const results = await Promise.allSettled(uploadTasks)

    let success = 0
    let failed = 0

    for (const r of results) {
      if (r.status === 'fulfilled' && r.value?.success) {
        success++
        const messages = r.value.messages
        if (Array.isArray(messages)) mergeSkills(messages)
      } else {
        failed++
      }
    }

    if (failed === 0) {
      ElMessage({
        type: 'success',
        message: `技能包上传成功 (${success})`,
        plain: true,
      })
    } else {
      ElMessage({
        type: 'warning',
        message: `上传完成：成功 ${success} / 失败 ${failed}`,
        plain: true,
      })
    }
  } catch (err) {
    console.error('uploadSkill failed:', err)
    ElMessage({
      type: 'error',
      message: '技能包上传失败: ' + String(err),
      plain: true,
    })
  } finally {
    isUploading.value = false
  }
}

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

function formatTime(time: string) {
  return time.replace('T', ' ')
}

function mergeSkills(messages: any[]) {
  for (const m of messages) {
    const skill: SkillItem = {
      skill_id: m.skill_id,
      skill_name: m.skill_name,
      skill_description: m.skill_description,
      skill_version: m.skill_version,
      package_size: m.package_size,
      upload_at: formatTime(m.upload_at),
      enabled: Boolean(m.is_active),
    }

    const index = skillList.value.findIndex(
      s => s.skill_id === skill.skill_id
    )

    if (index !== -1) {
      // 覆盖旧版本
      skillList.value[index] = skill
    } else {
      // 新技能插到最前
      skillList.value.unshift(skill)
    }
  }
}
</script>


<style scoped>
.skill-page-wrapper {
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
  height: calc(100vh - 36px) !important;
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
  transition: opacity 0.2s var(--apix-cubic-bezier),
    color 0.2s var(--apix-cubic-bezier),
    background-color 0.2s var(--apix-cubic-bezier);
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
  display: flex; 
  margin: 8px 0;
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
.skill-grid {
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
  background: color-mix(in oklch, #fbfbfb 40%, transparent);
  width: 80%;
  border-radius: 16px;
  text-align: center;
  align-self: center;
  background-color: rgba(255, 255, 255, 0.5);
}

/* File card animation with CSS stagger */
.skill-fade-enter-active {
  transition: 
    opacity 0.5s cubic-bezier(0.215, 0.61, 0.355, 1),
    transform 0.5s cubic-bezier(0.215, 0.61, 0.355, 1);
  transition-delay: calc(var(--stagger-index, 0) * 60ms);
}

.skill-fade-enter-from {
  opacity: 0;
  transform: translateY(20px) scale(0.9);
}

.skill-fade-enter-to {
  opacity: 1;
  transform: translateY(0) scale(1);
}

/* Leave animation - quick fade out */
.skill-fade-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
  position: absolute;
}

.skill-fade-leave-to {
  opacity: 0;
  transform: scale(0.9);
}

/* Move animation for reordering */
.skill-fade-move {
  transition: transform 0.4s cubic-bezier(0.215, 0.61, 0.355, 1);
}
</style>