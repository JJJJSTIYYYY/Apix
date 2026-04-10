<template>
  <div class="chat-history q">
    <!-- Search -->
    <div class="q-search" :class="{ 'is-focused': isSearchFocused }">
      <el-button
        class="q-primary-btn melt-btn"
        type="primary"
        size="small"
        @click="createNewChat"
      >
        <el-icon><Plus /></el-icon>
      </el-button>

      <el-input
        v-model="searchKeyword"
        placeholder="搜索"
        size="small"
        clearable
        @input="handleSearch"
        @focus="isSearchFocused = true"
        @blur="isSearchFocused = false"
      >
        <template #prefix>
          <el-icon><Search /></el-icon>
        </template>
      </el-input>
    </div>

    <!-- List -->
    <el-scrollbar ref="scrollbarRef" class="q-scroll" max-height="100%">
      <div class="q-scroll-inner" ref="scrollInnerRef">
        <el-menu
          ref="menuRef"
          :default-active="activeHistoryId"
          class="q-menu"
          @select="handleSelect"
        >
          <div
            class="q-slider"
            :class="{ 'is-missing': !isActiveInFiltered && !isActiveInHistories }"
            :style="sliderStyle"

          />

          <div v-for="group in groupedHistories" :key="group.date" class="q-section">
            <div class="q-section-title">{{ group.date }}</div>

            <el-menu-item
              v-for="h in group.items"
              :key="h.id"
              :index="String(h.id)"
              class="q-cell"
              :ref="(el) => setItemRef(h.id, el)"
            >
              <HistoryCard 
                :history="h" 
                @rename-history="handleRenameHistory"
                @delete-history="handleDeleteHistory"
              />
            </el-menu-item>
          </div>

          <div v-if="filteredHistories.length === 0" class="q-empty">
            <el-icon class="shadow-icon" style="font-size: 48px;"><Search /></el-icon>
            <div style="margin-top: 8px;">暂无对话历史</div>
          </div>
        </el-menu>
      </div>
    </el-scrollbar>

    <!-- Rename dialog -->
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { Search, Plus } from '@element-plus/icons-vue'
import type { ElScrollbar } from 'element-plus'
import { ElMessage } from 'element-plus'

import HistoryCard, { type ChatHistory } from './history_card.vue'
import { useOverscrollBounce } from '../../../../src/components/useOverscrollBounce.js'
import { ConfirmDialog } from '../comp/confirmDialog.js'
import { useAuthStore } from '../../../store/auth'

const props = defineProps<{
  histories?: ChatHistory[]
  activeId?: number | string
}>()

const emit = defineEmits<{
  select: [id: number | string]
  create: []
  rename: [id: number | string, newTitle: string]
  delete: [id: number | string]
  clear: []
  connect: [path: string]
}>()

const searchKeyword = ref('')
const filteredHistories = ref<ChatHistory[]>([])
const activeHistoryId = ref('')

const authStore = useAuthStore()
const cid = ref("")

const renameDialogVisible = ref(false)
const renameForm = ref<{ id: number | string | null; title: string }>({
  id: null,
  title: '',
})

const isSearchFocused = ref(false)

// ✅ scrollbar / menu ref
const scrollbarRef = ref<InstanceType<typeof ElScrollbar> | null>(null)
const menuRef = ref<any>(null)

// ✅ 存每个菜单项 DOM
const itemElMap = new Map<string, HTMLElement>()

// ✅ 滑动窗口样式
const sliderStyle = ref<Record<string, string>>({
  '--slider-y': '0px',
  '--slider-scale': '1',
  height: '0px',
  opacity: '0',
})

// ✅ 当前选中项是否仍在搜索结果里
const isActiveInFiltered = computed(() => {
  if (!activeHistoryId.value) return false
  return filteredHistories.value.some((h) => String(h.id) === activeHistoryId.value)
})

// ✅ 检查当前选中项是否在 histories 中
const isActiveInHistories = computed(() => {
  if (!activeHistoryId.value || !props.histories) return false
  return props.histories.some((h) => String(h.id) === activeHistoryId.value)
})

const hideSliderMissing = () => {
  // 保留当前位置/高度，只做“放大 + 渐隐”
  sliderStyle.value = {
    ...sliderStyle.value,
    opacity: '0',
    '--slider-scale': '1.12',
  }
}

// ✅ 绑定每个 item 的 DOM（el-menu-item 是组件，需要取 $el）
const setItemRef = (id: number | string, el: any) => {
  const key = String(id)
  const dom = el?.$el as HTMLElement | undefined
  if (!dom) return
  itemElMap.set(key, dom)
}

const getWrapEl = () => {
  // element-plus ElScrollbar 暴露 wrapRef
  return (scrollbarRef.value as any)?.wrapRef as HTMLElement | undefined
}

const updateSliderTo = async (index: string, alsoScroll = true) => {
  await nextTick()

  const wrapEl = getWrapEl()
  const itemEl = itemElMap.get(index)

  // ✅ 选中项不在当前渲染列表（比如搜索过滤掉了）：放大渐隐消失
  if (!wrapEl || !itemEl) {
    hideSliderMissing()
    return
  }

  const wrapRect = wrapEl.getBoundingClientRect()
  const itemRect = itemEl.getBoundingClientRect()

  // item 在 wrap 内容中的“绝对”top（包含当前 scrollTop）
  const top = itemRect.top - wrapRect.top + wrapEl.scrollTop
  const height = itemRect.height

  sliderStyle.value = {
    '--slider-y': `${top}px`,
    '--slider-scale': '1',
    height: `${height}px`,
    opacity: '1',
  }

  if (alsoScroll) {
    // 让选中项尽量居中
    const targetTop = Math.max(0, top - (wrapEl.clientHeight - height) / 2)
    wrapEl.scrollTo({ top: targetTop, behavior: 'smooth' })
  }
}

onMounted(async () => {
  await authStore.restore()
  cid.value = authStore.user.user_uid
  filteredHistories.value = props.histories ? [...props.histories] : []
  if (props.activeId !== undefined && props.activeId !== null) {
    activeHistoryId.value = String(props.activeId)
  }
  // ✅ 初次定位 slider（不强制滚动）
  await updateSliderTo(activeHistoryId.value, false)
})

watch(
  () => props.histories,
  (list) => {
    filteredHistories.value = list ? [...list] : []
    handleSearch()
  },
  { deep: true }
)

watch(
  () => props.activeId,
  async (id) => {
    if (id !== undefined && id !== null) {
      activeHistoryId.value = String(id)
      await updateSliderTo(activeHistoryId.value, true)
    }
  }
)

const groupedHistories = computed(() => {
  const starred: ChatHistory[] = []
  const normalGroups: Record<string, ChatHistory[]> = {}

  // 1. Split starred / normal
  for (const item of filteredHistories.value) {
    if (item.star) {
      starred.push(item)
    } else {
      ;(normalGroups[item.date] ||= []).push(item)
    }
  }

  const result: { date: string; items: ChatHistory[] }[] = []

  // 2. Star group (always on top)
  if (starred.length > 0) {
    result.push({
      date: 'Pinned',
      // Group internal sort: newest first
      items: [...starred].sort((a, b) => b.createTime - a.createTime),
    })
  }

  // 3. Normal date groups
  const normalGroupList = Object.entries(normalGroups)
    .map(([date, items]) => ({
      date,
      // Group internal sort: newest first
      items: [...items].sort((a, b) => b.createTime - a.createTime),
    }))
    // Group sort: compare by newest item in each group
    .sort(
      (a, b) =>
        (b.items[0]?.createTime ?? 0) - (a.items[0]?.createTime ?? 0)
    )

  result.push(...normalGroupList)

  return result
})


// ✅ 列表变更（搜索/重新分组）后重新对齐 slider
watch(
  () => groupedHistories.value,
  async () => {
    if (!activeHistoryId.value) return

    // ✅ 搜索结果不包含当前选中
    if (!isActiveInFiltered.value) {
      hideSliderMissing()
      return
    }

    // ✅ 仍包含：正常对齐
    await updateSliderTo(activeHistoryId.value, false)
  },
  { deep: true }
)

const handleSearch = () => {
  const list = props.histories ? [...props.histories] : []
  const kw = searchKeyword.value.trim().toLowerCase()

  if (!kw) {
    filteredHistories.value = list
    return
  }

  filteredHistories.value = list.filter((h) =>
    (h.preview || '').toLowerCase().includes(kw)
  )
}

const handleSelect = (index: string) => {
  activeHistoryId.value = index
  emit('select', isNaN(Number(index)) ? index : Number(index))

  // ✅ 选中后滑动窗口移动 + 滚动到目标
  updateSliderTo(index, true)
}

const createNewChat = () => emit('create')

const handleStarHistory = (history_id: string) => {
  
}

const handleRenameHistory = async (history_id: string, new_title: string) => {
  try {
    await window.api.updateConversation(
      cid.value,
      "",
      history_id,
      { title: new_title }
    )
    ElMessage({ type: 'success', message: '已更新', plain: true, })
  } catch (err) {
    console.log("对话删除失败："+err)
    ElMessage({ type: 'error', message: '更新失败', plain: true, })
  }
  emit('rename', history_id, new_title)
}

const handleDeleteHistory = async (history_id: string) => {
  // Find target history
  const index = props.histories.findIndex(c => String(c.id) === history_id)
  if (index === -1) return

  const history = props.histories[index]

  try {
    await ConfirmDialog.confirm(
      `确定要删除对话 "${history.preview.slice(0, 8)}..." 吗？`,
      '删除确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )
    try {
      await window.api.updateConversation(
        cid.value,
        "",
        history_id,
        { deleted: true }
      )
      ElMessage({ type: 'success', message: '已删除', plain: true, })
    } catch (err) {
      console.log("对话删除失败："+err)
      ElMessage({ type: 'error', message: '删除失败', plain: true, })
    }

    // User confirmed
    emit('delete', history_id)
  } catch (err) {
    console.error("pannel: handleDeleteHistory error:", err)
    ElMessage({ type: 'error', message: '删除失败', plain: true, })
  }
}

// 以下是列表滚动至边界的回弹
const scrollInnerRef = ref(null)

useOverscrollBounce(
  () => getWrapEl(),   // el-scrollbar wrap
  scrollInnerRef,
  {
    maxBounce: 30,
    damping: 0.35,
    springK: 400,
    springC: 20,
    idleMs: 40,
  }
)
// 以上是列表滚动至边界的回弹
</script>

<style scoped>
/* Layout */
.chat-history.q {
  z-index: 99;
  height: calc(100vh - 60px);
  display: flex;
  flex-direction: column;
  padding: 0 6px;
  padding-right: 16px;
  background: transparent;
  min-width: 180px;
  width: 100%;
  max-width: 240px;
}

/* Primary Button */
:deep(.q-primary-btn.el-button) {
  width: 34px;
  height: 34px;
  padding: 0;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;

  background: rgba(232, 238, 237, 0.304);
  border: 1px solid rgba(255, 255, 255, 0.495);
  box-shadow:
    0 10px 26px rgba(0, 0, 0, 0.123),
    0 2px 6px rgba(0, 0, 0, 0.05);

  color: rgba(0, 0, 0, 0.78);
  transform: translateZ(0) scale(1);
  transition:
    transform 0.22s cubic-bezier(0.34, 1.56, 0.64, 1),
    background 0.18s ease,
    box-shadow 0.18s ease,
    border-color 0.18s ease;
}
:deep(.q-primary-btn.el-button:hover) {
  background: rgba(255, 255, 255, 0.387);
}
:deep(.q-primary-btn.el-button:active) {
  transform: translateZ(0) scale(0.92);
}

/* Search */
.q-search {
  margin-top: 8px;
  padding: 10px 10px 14px;
  display: flex;
  align-items: center;
  gap: 6px;
  transition: gap 0.22s ease;
}

.q-search.is-focused {
  gap: 0;
}

.q-search :deep(.el-input) {
  flex: 1;
  min-width: 0;
  transform-origin: left center;
  transform: scale(1);
  transition: transform 0.22s cubic-bezier(0.34, 3.5, 0.64, 1);
}
.q-search.is-focused :deep(.el-input) {
  transform: scale(0.97);
}
.q-search :deep(.el-input:hover) {
  transform: scale(1.02);
  transition: transform 0.22s ease;
}

.q-search :deep(.el-input__wrapper) {
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
.q-search.is-focused :deep(.el-input__wrapper) {
  background: rgba(255, 255, 255, 0.536);
  border-color: rgba(255, 255, 255, 0.76);
  z-index: 99;
}

/* Melt Button */
.melt-btn {
  flex: 0 0 auto;
  transform-origin: right center;
  transition:
    opacity 0.18s ease,
    transform 0.22s ease,
    filter 0.22s ease,
    width 0.22s ease,
    margin 0.22s ease,
    padding 0.22s ease,
    border-width 0.22s ease;
}
.q-search.is-focused .melt-btn {
  opacity: 0;
  transform: translateX(15px) scale(0.8);
  filter: blur(6px);
  width: 0;
  padding: 0;
  margin: 0;
  border-width: 0;
  pointer-events: none;
  overflow: hidden;
}

/* Scroll */
.q-scroll {
  flex: 1;
  overflow: hidden;
  border-radius: 20px;
  background: rgba(245, 247, 247, 0.768);
  border: 1px solid rgba(255, 255, 255, 0.28);
  box-shadow:
    0 10px 26px rgba(4, 52, 42, 0.166),
    0 2px 6px rgba(0, 0, 0, 0.05),
    inset 0 1px 0 rgba(255, 255, 255, 0.55),
    inset 0 -3px 1px rgba(255, 242, 247, 0.635);
  transition: transform 0.22s cubic-bezier(0.34, 1.56, 0.64, 1);
  scrollbar-width: none;
}
.q-scroll :deep(.el-scrollbar__bar) {
  display: none !important;
}
.q-scroll :deep(.el-scrollbar__wrap) {
  max-height: 100% !important;
}

/* ✅ 让 slider 绝对定位相对 q-menu */
.q-menu {
  position: relative;
  border: none;
  background: transparent;
  padding: 0 !important;
  padding-bottom: 10px !important;
}

/* ✅ 滑动窗口（高亮块） */
.q-slider {
  position: absolute;
  left: 6px;
  right: 6px;
  top: 0;
  height: 72px !important;
  opacity: 0;
  border-radius: 16px;
  pointer-events: none;
  z-index: 0;

  background: rgba(255, 255, 255, 0.249);
  border: 1px solid rgba(255, 255, 255, 0.45);
  box-shadow:
    0 10px 26px rgba(0, 0, 0, 0.10),
    inset 0 1px 0 rgba(255, 255, 255, 0.55);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);

  transform: translateY(var(--slider-y, 0px)) scale(var(--slider-scale, 1));

  transition:
    transform 0.3s cubic-bezier(0.34, 1.3, 0.64, 1),
    height 0.3s cubic-bezier(0.34, 1.3, 0.64, 1),
    opacity 0.15s ease;
}

/* （可选）缺失时更柔和的过渡 */
.q-slider.is-missing {
  transition:
    transform 0.28s cubic-bezier(0.22, 1.2, 0.36, 1),
    opacity 0.18s ease;
}

/* Menu / Section */
.q-section {
  background: transparent;
  overflow: hidden;
}
.q-section-title {
  margin: 3px;
  padding: 10px 14px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.4px;
  color: rgba(60, 67, 66, 0.46);
  /* border-bottom: 2px solid transparent; */
  /* border-top: 2px solid transparent; */
  border-image: linear-gradient(
    to right,
    transparent,
    rgba(255, 255, 255, 0.658),
    transparent
  ) 1;
  border-radius: 16px;
  background-color: rgba(255, 255, 255, 0);
}

.q-menu :deep(.el-menu-item.q-cell) {
  position: relative;
  z-index: 1;

  height: auto;
  min-height: 74px;
  padding: 12px 14px;
  margin: 0;
  background: transparent;
  border-radius: 12px;
  /* border-bottom: 2px solid transparent; */
  border-image: linear-gradient(
    to right,
    transparent,
    rgba(255, 255, 255, 0.658),
    transparent
  ) 1;
  color: rgba(0, 0, 0, 0.92);
}
.q-menu :deep(.el-menu-item.q-cell.is-active) {
  color: rgba(0, 0, 0, 0.92);
}
.q-menu :deep(.el-menu-item.q-cell:not(.is-active):hover) {
  background: rgba(0, 0, 0, 0.032);
}

/* Empty */
.q-empty {
  padding: 46px 12px;
  text-align: center;
  color: rgba(60, 60, 67, 0.7);
  align-items: center;
  justify-content: center;
}

/* Mobile */
@media (max-width: 768px) {
  .q-menu :deep(.el-menu-item.q-cell) .q-cell-actions {
    opacity: 1;
  }
  .chat-history.q {
    min-width: 240px;
  }
}
</style>
