<template>
  <div class="chat-history q" :class="{ 'is-hide': isHide }">
    <!-- Search -->
    <div class="q-search" :class="{ 'is-focused': isSearchFocused, 'is-history-hide': isHide }">
      <el-button
        class="q-primary-btn melt-btn"
        type="primary"
        size="small"
        @click="hidePannel"
      >
        <el-icon v-if="!isHide"><ArrowLeft /></el-icon>
        <el-icon v-else><Expand /></el-icon>
      </el-button>

      <transition name="fade">
        <div v-if="!isHide" style="width: 100%;">
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
      </transition>
    </div>


    <div class="q-create" :class="{ 'is-history-hide': isHide }">
        <el-button
          class="create-btn"
          :class="{ 'is-history-hide': isHide }"
          type="primary"
          size="small"
          @click="createNewChat"
          
        >
          <el-icon style="font-size: 15px;"><ChatLineRound /></el-icon>
          <div style="width: 6px;" v-if="!isHide"></div>
          <div v-if="!isHide">开启新对话</div>
        </el-button>
    </div>

    <!-- List -->
    <transition name="fade">
      <div v-if="!isHide" style="flex: 1; min-height: 0; display: flex;">
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
                <button class="q-section-title" @click="switchFold(group.date)">{{ group.date }}</button>

                <el-menu-item
                  v-for="h in group.items"
                  v-if="foldStatus[group.date]"
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
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onActivated, watch, nextTick } from 'vue'
import type { ElScrollbar } from 'element-plus'
import { ElMessage } from 'element-plus'

import HistoryCard, { type ChatHistory } from './history_card.vue'
import { ConfirmDialog } from '../comp/confirmDialog.js'
import { useAuthStore } from '../../../store/auth'

const props = defineProps<{
  histories?: ChatHistory[]
  activeId?: number | string
}>()

const emit = defineEmits<{
  select: [id: number | string]
  create: []
  hide: [toHide: boolean]
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

const isSearchFocused = ref(false)
const isHide = ref(true)

// scrollbar / menu ref
const scrollbarRef = ref<InstanceType<typeof ElScrollbar> | null>(null)
const menuRef = ref<any>(null)

// store menu item DOM
const itemElMap = new Map<string, HTMLElement>()

// slider style
const sliderStyle = ref<Record<string, string>>({
  '--slider-y': '0px',
  '--slider-scale': '1',
  height: '0px',
  opacity: '0',
})

// active item check
const isActiveInFiltered = computed(() => {
  if (!activeHistoryId.value) return false
  return filteredHistories.value.some((h) => String(h.id) === activeHistoryId.value)
})

// grouped list
const groupedHistories = computed(() => {
  const starred: ChatHistory[] = []
  const normalGroups: Record<string, ChatHistory[]> = {}

  for (const item of filteredHistories.value) {
    if (item.star) {
      starred.push(item)
    } else {
      ;(normalGroups[item.date] ||= []).push(item)
    }
  }

  const result: { date: string; items: ChatHistory[] }[] = []

  if (starred.length > 0) {
    result.push({
      date: 'Pinned',
      items: [...starred].sort((a, b) => b.createTime - a.createTime),
    })
  }

  const normalGroupList = Object.entries(normalGroups)
    .map(([date, items]) => ({
      date,
      items: [...items].sort((a, b) => b.createTime - a.createTime),
    }))
    .sort(
      (a, b) =>
        (b.items[0]?.createTime ?? 0) - (a.items[0]?.createTime ?? 0)
    )

  result.push(...normalGroupList)

  return result
})

// fold 状态
const foldStatus = ref<Record<string, boolean>>({
  'Pinned': false,
  'Today': true,
  'Yesterday': true,
  'In this Week': true,
  'Further more': true,
})

// 当前 active 所在 group
const activeGroupDate = computed(() => {
  if (!activeHistoryId.value) return null

  for (const group of groupedHistories.value) {
    if (group.items.some(h => String(h.id) === activeHistoryId.value)) {
      return group.date
    }
  }
  return null
})

// 当前 active group 是否展开
const isActiveGroupVisible = computed(() => {
  if (!activeGroupDate.value) return false
  return !!foldStatus.value[activeGroupDate.value]
})

// hide slider but keep position
const hideSliderMissing = () => {
  sliderStyle.value = {
    ...sliderStyle.value,
    opacity: '0',
    '--slider-scale': '1.12',
  }
}

// bind item DOM
const setItemRef = (id: number | string, el: any) => {
  const key = String(id)
  const dom = el?.$el as HTMLElement | undefined
  if (!dom) return
  itemElMap.set(key, dom)
}

const getWrapEl = () => {
  return (scrollbarRef.value as any)?.wrapRef as HTMLElement | undefined
}

// core: update slider position
const updateSliderTo = async (index: string, alsoScroll = true) => {
  await nextTick()
  await nextTick()

  const wrapEl = getWrapEl()
  const itemEl = itemElMap.get(index)

  if (!wrapEl || !itemEl || !itemEl.isConnected) {
    hideSliderMissing()
    return
  }

  const wrapRect = wrapEl.getBoundingClientRect()
  const itemRect = itemEl.getBoundingClientRect()

  const top = itemRect.top - wrapRect.top + wrapEl.scrollTop
  const height = itemRect.height

  sliderStyle.value = {
    '--slider-y': `${top}px`,
    '--slider-scale': '1',
    height: `${height}px`,
    opacity: '1',
  }

  if (alsoScroll) {
    const targetTop = Math.max(0, top - (wrapEl.clientHeight - height) / 2)
    wrapEl.scrollTo({ top: targetTop, behavior: 'smooth' })
  }
}

// unified sync entry
const syncSlider = async (alsoScroll = false) => {
  if (!activeHistoryId.value) return

  if (!isActiveInFiltered.value || !isActiveGroupVisible.value) {
    hideSliderMissing()
    return
  }

  await updateSliderTo(activeHistoryId.value, alsoScroll)
}

// lifecycle
onMounted(async () => {
  await authStore.restore()
  cid.value = authStore.user.user_uid

  filteredHistories.value = props.histories ? [...props.histories] : []

  if (props.activeId !== undefined && props.activeId !== null) {
    activeHistoryId.value = String(props.activeId)
  }

  await syncSlider(false)
})

onActivated(async () => {
  await syncSlider(false)
})

// props watchers
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
      await syncSlider(true)
    }
  }
)

// panel show
watch(
  isHide,
  async (hidden) => {
    if (!hidden) {
      await syncSlider(false)
    }
  },
  { flush: 'post' }
)

// ✅ fold 变化监听（核心新增）
watch(
  () => foldStatus.value,
  async () => {
    if (!activeHistoryId.value) return

    if (!isActiveGroupVisible.value) {
      hideSliderMissing()
      return
    }

    await syncSlider(false)
  },
  { deep: true, flush: 'post' }
)

// list change
watch(
  () => groupedHistories.value,
  async () => {
    if (!activeHistoryId.value) return

    if (!isActiveInFiltered.value || !isActiveGroupVisible.value) {
      hideSliderMissing()
      return
    }

    await syncSlider(false)
  },
  { deep: true, flush: 'post' }
)

// search
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

// toggle panel
const hidePannel = async () => {
  isHide.value = !isHide.value
  emit('hide', isHide.value)

  if (!isHide.value) {
    await syncSlider(false)
  }
}

// select
const handleSelect = (index: string) => {
  activeHistoryId.value = index
  emit('select', isNaN(Number(index)) ? index : Number(index))
  updateSliderTo(index, true)
}

// ✅ fold toggle（增强版）
const switchFold = async (date: string) => {
  foldStatus.value[date] = !foldStatus.value[date]

  await nextTick()

  if (!activeHistoryId.value) return

  if (!isActiveGroupVisible.value) {
    hideSliderMissing()
  } else {
    await syncSlider(false)
  }
}

const createNewChat = () => emit('create')

// rename / delete
const handleRenameHistory = async (history_id: string, new_title: string) => {
  try {
    await window.api.updateConversation(
      cid.value,
      "",
      history_id,
      { title: new_title }
    )
    ElMessage({ type: 'success', message: '已更新', plain: true })
  } catch (err) {
    console.log("对话删除失败：" + err)
    ElMessage({ type: 'error', message: '更新失败', plain: true })
  }
  emit('rename', history_id, new_title)
}

const handleDeleteHistory = async (history_id: string) => {
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
  } catch (err) {
    return
  }

  try {
    await window.api.updateConversation(
      cid.value,
      "",
      history_id,
      { deleted: true }
    )
    ElMessage({ type: 'success', message: '已删除', plain: true })
    emit('delete', history_id)
  } catch (err) {
    console.log("对话删除失败：" + err)
    ElMessage({ type: 'error', message: '删除失败', plain: true })
  }
}
</script>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.28s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* Layout */
.chat-history.q {
  z-index: 99;
  height: calc(100vh - 54px);
  display: flex;
  flex-direction: column;
  background: transparent;
  width: 100%;
  max-width: 240px;
}
.chat-history.is-hide {
  width: 40px;
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

  background: rgb(248, 248, 248);
  border: 1px solid rgba(255, 255, 255, 0.618);
  box-shadow:
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
  color: rgb(255, 255, 255);
  background-color: #81ddd0;
  box-shadow: 0 6px 20px rgba(156, 221, 211, 0.6);
  transform: scale(1.02);
}
:deep(.q-primary-btn.el-button:active) {
  transform: translateZ(0) scale(0.92);
}

/* Search */
.q-search {
  margin-top: 8px;
  padding: 10px 10px;
  display: flex;
  align-items: center;
  gap: 6px;
  transition: gap 0.22s ease;
}

.q-search.is-focused {
  gap: 0;
}

.q-search.is-history-hide {
  width: 40px;
}



.q-search :deep(.el-input) {
  flex: 1;
  min-width: 0;
  transform-origin: center;
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
  background: rgb(248, 248, 248);
  border: 1px solid rgba(255, 255, 255, 0.618);
  box-shadow:
    0 2px 6px rgba(0, 0, 0, 0.05);
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

.q-create {
  padding: 5px 10px 20px;
}

.q-create.is-history-hide {
  width: 40px;
}

.create-btn {
  /* 基础样式 */
  border-radius: 20px;
  font-weight: 500;
  font-size: 12px;
  letter-spacing: 1px;
  width: 100%;
  height: 32px;
  transition: all 0.24s cubic-bezier(0.23, 1, 0.32, 1);

  background: rgb(248, 248, 248);
  border: 1px solid rgba(255, 255, 255, 0.618);
  box-shadow:
    0 2px 6px rgba(0, 0, 0, 0.05);
    
  color: #00000065;
}

.create-btn.is-history-hide {
  width: 34px;
  height: 34px;
  padding: 0 0 1.5px 0;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;

  background: rgb(248, 248, 248);
  border: 1px solid rgba(255, 255, 255, 0.618);
  box-shadow:
    0 2px 6px rgba(0, 0, 0, 0.05);

  color: rgba(0, 0, 0, 0.78);
  transform: translateZ(0) scale(1);
  transition:
    transform 0.22s cubic-bezier(0.34, 1.56, 0.64, 1),
    background 0.18s ease,
    box-shadow 0.18s ease,
    border-color 0.18s ease;
}

/* 悬停效果 */
.create-btn:hover {
  color: rgb(255, 255, 255);
  background-color: #81ddd0;
  box-shadow: 0 6px 20px rgba(156, 221, 211, 0.6);
  transform: scale(1.02);
}

/* 点击效果 */
.create-btn:active {
  transform: translateY(0);
  box-shadow: 0 2px 8px rgba(156, 221, 211, 0.4);
}

/* 禁用状态 */
.create-btn.is-disabled {
  background-color: #c5e8e2;
  border-color: #c5e8e2;
  color: #7f8c8d;
  box-shadow: none;
}

/* 内部 div 样式 */
.create-btn > div {
  display: flex;
  align-items: center;
  gap: 6px;
}

/* Scroll */
.q-scroll {
  flex: 1;
  overflow: hidden;
  border-radius: 20px;

  background: rgb(248, 248, 248);
  border: 1px solid rgba(255, 255, 255, 0.618);
  box-shadow:
    0 2px 6px rgba(0, 0, 0, 0.05);
    
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
  left: 3px;
  right: 3px;
  top: 0;
  height: 38px !important;
  opacity: 0;
  border-radius: 16px;
  pointer-events: none;
  z-index: 0;

  background: rgb(253, 253, 253);
  box-shadow:
    0 2px 6px rgba(0, 0, 0, 0.106);

  transform: translateY(var(--slider-y, 0px)) scale(var(--slider-scale, 1));

  transition:
    transform 0.48s cubic-bezier(0.23, 1, 0.32, 1),
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
  padding: 6px 6px;
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
.q-section-title:hover {
  color: rgba(5, 164, 140, 0.46);
}

.q-menu :deep(.el-menu-item.q-cell) {
  position: relative;
  z-index: 1;

  height: auto;
  min-height: 36px;
  padding: 3px 3px;
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
