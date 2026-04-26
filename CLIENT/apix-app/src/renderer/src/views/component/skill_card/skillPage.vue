<template>
  <div class="skill-page-wrapper">
    <div class="ab-bar">
      <div class="ab-bar-btns">
        <el-button
          type="primary"
          class="upload-btn"
          @click="uploadSkill"
        >
          上传技能包
          <el-icon class="el-icon--right"><Upload /></el-icon>
        </el-button>
      </div>
    </div>

    <div class="main-wrapper selectable">

      <h1 style="width: 100%; text-align: center; font-size: 20px;">
        Agent 技能包
      </h1>

      <!-- Search -->
      <div class="search-wrapper">
        <el-input
          v-model="searchKeyword"
          placeholder="Search skills by name / description"
          clearable
          style="max-width: 420px;"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
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
      <div class="explain-tag-wrapper">
        <div
          class="explain-tag"
          v-html="skillDocs"
        ></div>
      </div>

      <div style="width: 100%; height: 60px;"></div>

    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
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
    console.error('初始化失败', err)
  }
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

    if (result.canceled || result.filePaths.length === 0) {
      return
    }

    isUploading.value = true

    const uploadTasks = result.filePaths.map((path: string) => {

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

        if (Array.isArray(messages)) {
          mergeSkills(messages)
        }

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
.skill-grid {
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