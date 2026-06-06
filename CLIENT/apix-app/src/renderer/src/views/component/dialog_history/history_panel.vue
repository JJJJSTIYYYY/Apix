<template>
  <div 
    class="chat-history q" 
    :class="{ 'is-hide': isHide }"
  >
    <div ctrl-area-wrapper class="ctrl-area-wrapper" :class="{ 'is-history-hide': isHide }">
      <div class="ctrl-line q-search" :class="{ 'is-focused': isSearchFocused, 'is-history-hide': isHide }">
        <button
          class="q-primary-btn melt-btn"
          :class="{ 'is-history-hide': isHide }"
          type="primary"
          size="small"
          @click="hidePanel"
        >
          <svg class="icon" width="16" height="16" viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg"><path d="M9.67272 0.522841C10.8339 0.522841 11.76 0.522714 12.4963 0.602493C13.2453 0.683657 13.8789 0.854248 14.4264 1.25197C14.7504 1.48739 15.0355 1.77247 15.2709 2.0965C15.6686 2.64394 15.8392 3.27758 15.9204 4.02655C16.0002 4.7629 16 5.68895 16 6.85014V9.14986C16 10.3111 16.0002 11.2371 15.9204 11.9735C15.8392 12.7224 15.6686 13.3561 15.2709 13.9035C15.0355 14.2275 14.7504 14.5126 14.4264 14.748C13.8789 15.1458 13.2453 15.3163 12.4963 15.3975C11.76 15.4773 10.8339 15.4772 9.67272 15.4772H6.3273C5.16611 15.4772 4.24006 15.4773 3.50371 15.3975C2.75474 15.3163 2.1211 15.1458 1.57366 14.748C1.24963 14.5126 0.964549 14.2275 0.729131 13.9035C0.331407 13.3561 0.160817 12.7224 0.0796529 11.9735C-0.000126137 11.2371 1.25338e-09 10.3111 1.25338e-09 9.14986V6.85014C1.25329e-09 5.68895 -0.000126137 4.7629 0.0796529 4.02655C0.160817 3.27758 0.331407 2.64394 0.729131 2.0965C0.964549 1.77247 1.24963 1.48739 1.57366 1.25197C2.1211 0.854248 2.75474 0.683657 3.50371 0.602493C4.24006 0.522714 5.16611 0.522841 6.3273 0.522841H9.67272ZM5.54303 1.88715V14.1118C5.78636 14.1128 6.04709 14.1169 6.3273 14.1169H9.67272C10.8639 14.1169 11.7032 14.1164 12.3493 14.0465C12.9824 13.9779 13.3497 13.8494 13.6268 13.6482C13.8354 13.4966 14.0195 13.3125 14.1711 13.1039C14.3723 12.8268 14.5007 12.4595 14.5693 11.8264C14.6393 11.1803 14.6398 10.341 14.6398 9.14986V6.85014C14.6398 5.65896 14.6393 4.81967 14.5693 4.1736C14.5007 3.54048 14.3723 3.17318 14.1711 2.89609C14.0195 2.68747 13.8354 2.50337 13.6268 2.35179C13.3497 2.1506 12.9824 2.02212 12.3493 1.95353C11.7032 1.88358 10.8639 1.88307 9.67272 1.88307H6.3273C6.04709 1.88307 5.78636 1.8862 5.54303 1.88715ZM4.1828 1.91166C3.99125 1.9216 3.8148 1.93577 3.65076 1.95353C3.01764 2.02212 2.65034 2.1506 2.37325 2.35179C2.16463 2.50337 1.98052 2.68747 1.82895 2.89609C1.62776 3.17318 1.49928 3.54048 1.43069 4.1736C1.36074 4.81967 1.36023 5.65896 1.36023 6.85014V9.14986C1.36023 10.341 1.36074 11.1803 1.43069 11.8264C1.49928 12.4595 1.62776 12.8268 1.82895 13.1039C1.98052 13.3125 2.16463 13.4966 2.37325 13.6482C2.65034 13.8494 3.01764 13.9779 3.65076 14.0465C3.81478 14.0642 3.99127 14.0774 4.1828 14.0873V1.91166Z"></path></svg>
        </button>

        <div class="search-wrapper" v-if="!isHide" style="width: 100%;">
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
      </div>


      <div class="ctrl-line q-create" :class="{ 'is-history-hide': isHide }">
        <button
          class="create-btn"
          :class="{ 'is-history-hide': isHide }"
          type="primary"
          size="small"
          @click="createNewChat"
          
        >
          <svg t="1777805499661" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="13418" width="18" height="18"><path d="M479.8464 111.7184c44.7744 0 87.9616 6.8864 128.6144 19.6096v81.792a350.7712 350.7712 0 0 0-128.6144-24.2944c-192.896 0-350.72 156.16-350.72 347.0336v250.624c0 53.9904 42.88 96.4096 97.4336 96.4096h253.2864c192.896 0 350.72-156.16 350.72-347.0336 0-36.9408-5.888-72.576-16.8448-106.0352h81.152c8.8832 33.92 13.6192 69.4528 13.6192 106.0352 0 233.2672-192.896 424.1408-428.6464 424.1408H226.56C129.1264 960 51.2 882.8928 51.2 786.4832v-250.624C51.2 302.592 244.096 111.7184 479.8464 111.7184z m19.4816 491.6224c21.4528 0 38.9632 17.3568 38.9632 38.5536s-17.5104 38.5536-38.9632 38.5536h-175.36a38.8864 38.8864 0 0 1-38.9632-38.5536c0-21.1968 17.536-38.5536 38.9632-38.5536h175.36z m136.3968-173.5168c21.4272 0 38.9632 17.3568 38.9632 38.5536 0 21.2224-17.536 38.5536-38.9632 38.5536H323.968a38.8864 38.8864 0 0 1-38.9632-38.5536c0-21.1968 17.536-38.5536 38.9632-38.5536h311.7568zM822.784 64c20.7104 0 37.504 16.7936 37.504 37.504l-0.0256 73.8304h75.4176a37.12 37.12 0 0 1 0 74.24l-75.4176-0.0256v73.856a37.504 37.504 0 0 1-75.008 0V249.5488h-75.392a37.12 37.12 0 1 1 0-74.2144h75.392V101.504c0-20.7104 16.7936-37.504 37.5296-37.504z" p-id="13419"></path></svg>
          <div style="width: 6px;" v-if="!isHide"></div>
          <div v-if="!isHide" class="create-btn-text">开启新对话</div>
        </button>
      </div>
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
                :class="{ 'is-missing': !isActiveInFiltered }"
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
import { ref, computed, onMounted, onBeforeUnmount, onActivated, watch, nextTick } from 'vue'
import type { ElScrollbar } from 'element-plus'
import { ElMessage } from 'element-plus'
import HistoryCard, { type ChatHistory } from './history_card.vue'
import { ConfirmDialog } from '../comp/confirmDialog.js'
import { useAuthStore } from '../../../store/auth.js'

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
      date: '已收藏',
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
  '已收藏': true,
  '今天': true,
  '昨天': true,
  '这周内': true,
  '更早以前': false,
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
  window.addEventListener('keydown', panelHandleKeydown)
  await authStore.restore()
  cid.value = authStore.user.user_uid

  filteredHistories.value = props.histories ? [...props.histories] : []

  if (props.activeId !== undefined && props.activeId !== null) {
    activeHistoryId.value = String(props.activeId)
  }

  await syncSlider(false)
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', panelHandleKeydown)
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
const hidePanel = async () => {
  isSearchFocused.value = false
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
    console.error("[handleRenameHistory error]:" + err)
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
    console.error("[handleDeleteHistory error]:" + err)
    ElMessage({ type: 'error', message: '删除失败', plain: true })
  }
}

const panelHandleKeydown = (
  e: KeyboardEvent & {
    isComposing?: boolean
    keyCode?: number
  }
) => {
  if (e.isComposing || e.keyCode === 229) {
    return
  }

  // Ctrl/Cmd + B
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'b') {
    e.preventDefault()
    hidePanel()
    return
  }

  // Ctrl/Cmd + N
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'n') {
    e.preventDefault()
    createNewChat()
  }
}
</script>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.28s var(--apix-cubic-bezier);
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* Layout */
.chat-history.q {
  z-index: 99;
  height: calc(100vh - 36px);
  display: flex;
  flex-direction: column;
  background: transparent;
  width: 100%;
  max-width: 240px;

  border-radius: var(--apix-border-radius-base) 0 0 var(--apix-border-radius-base);
}
.chat-history.is-hide {
  width: 40px;
}
.ctrl-area-wrapper {
  margin-top: 8px;
  display: flex;
  flex-direction: column;
  border-radius: var(--apix-default-border-radius);
  transition: 
    box-shadow 0.3s var(--apix-cubic-bezier),
    background 0.3s var(--apix-cubic-bezier);
}

.ctrl-area-wrapper.is-history-hide {
  background-color: var(--apix-panel-layer-3-background);
  width: 48px;
  box-shadow: var(--apix-shadow-layer-2);
}

.ctrl-line {
  padding: 5px;
  display: flex;
  align-items: center;
  gap: 6px;
  transition: width 0.22s ease;
}

.ctrl-line.is-history-hide {
  width: 40px;
}

.melt-btn {
  /* Layout */
  flex: 0 0 auto;
  width: 38px;
  height: 38px;
  padding: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;

  /* Appearance */
  border: none;
  border-radius: var(--apix-border-radius-base);
  background-color: var(--apix-panel-layer-4-background);
  box-shadow: var(--apix-shadow-layer-1);

  /* Transform & Animation */
  transform-origin: center center;
  transform: scale(1);
  transition: transform 0.22s var(--apix-cubic-bezier),
              background-color 0.22s var(--apix-cubic-bezier),
              opacity 0.22s var(--apix-cubic-bezier),
              width 0.22s var(--apix-cubic-bezier),
              filter 0.22s var(--apix-cubic-bezier);
}

.melt-btn:hover {
  background-color: var(--apix-primary-color);
  transform: scale(1.05);
}

.melt-btn:active {
  transform: scale(0.92);
}

/* Collapsed State */
.melt-btn.is-history-hide {
  box-shadow: none;
}

.melt-btn .icon {
  fill: var(--apix-secondary-dark-color);
  min-width: 18px;
}

.melt-btn:hover .icon {
  fill: var(--apix-lightest-color);
}

.q-search.is-focused {
  gap: 0;
}

/* Hide melt-btn when search is focused */
.q-search.is-focused .melt-btn {
  opacity: 0;
  width: 0;
  padding: 0;
  margin: 0;
  border-width: 0;
  transform: translateX(15px);
  filter: blur(6px);
  pointer-events: none;
  overflow: hidden;
}

.search-wrapper {
  width: 100%;
  display: flex;
  gap: 12px;
}

.search-wrapper :deep(.el-input) {
  flex: 1;
  min-width: 0;
  height: 38px !important;
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

.create-btn {
  /* Layout */
  flex: 0 0 auto;
  width: 100%;
  height: 38px;
  padding: 0 10px;
  display: inline-flex;
  align-items: center;

  /* Appearance */
  border: none;
  border-radius: var(--apix-border-radius-base);
  background-color: var(--apix-panel-layer-4-background);
  box-shadow: var(--apix-shadow-layer-1);
  color: var(--apix-secondary-dark-color);

  /* Transform & Animation */
  transition: width 0.22s var(--apix-cubic-bezier),
              box-shadow 0.22s var(--apix-cubic-bezier),
              transform 0.22s var(--apix-cubic-bezier),
              color 0.22s var(--apix-cubic-bezier),
              background-color 0.22s var(--apix-cubic-bezier);
}

.create-btn.is-history-hide {
  box-shadow: none;
  width: 38px;
}

.create-btn:not(.is-history-hide):hover {
  color: var(--apix-lightest-color);
  background-color: var(--apix-primary-color);
  transform: scale(1.02);
}

.create-btn.is-history-hide:hover {
  color: var(--apix-lightest-color);
  background-color: var(--apix-primary-color);
  transform: scale(1.05);
}

.create-btn:not(.is-history-hide):active {
  transform: scale(0.99);
}

.create-btn.is-history-hide:active {
  transform: scale(0.92);
}

.create-btn .icon {
  fill: var(--apix-secondary-dark-color);
  min-width: 18px;
}

.create-btn:hover .icon {
  fill: var(--apix-lightest-color);
}

.create-btn-text {
  max-height: 18px; 
  overflow: hidden; 
  padding-left: 12px;
}

/* Scroll */
.q-scroll {
  flex: 1;
  overflow: hidden;
  background: transparent;
  border: none;
  transition: transform 0.22s var(--apix-cubic-bezier);
  scrollbar-width: none;
}
.q-scroll :deep(.el-scrollbar__bar) {
  display: none !important;
}
.q-scroll :deep(.el-scrollbar__wrap) {
  max-height: 100% !important;
}

.q-menu {
  position: relative;
  border: none;
  background: transparent;
  padding: 0 !important;
  padding-bottom: 10px !important;
}
.q-menu :deep(.el-menu-item.q-cell) {
  position: relative;
  z-index: 1;

  height: auto;
  min-height: 36px;
  padding: 3px 3px;
  margin: 0;
  background: transparent;
}

.q-slider {
  position: absolute;
  left: 3px;
  right: 3px;
  top: 0;
  height: 36px !important;
  opacity: 0;
  border-radius: 14px;
  pointer-events: none;
  z-index: 0;

  background: var(--apix-panel-layer-5-background);
  box-shadow: var(--apix-shadow-layer-2);

  transform: translateY(var(--slider-y, 0px)) scale(var(--slider-scale, 1));

  transition:
    transform 0.48s var(--apix-cubic-bezier),
    opacity 0.15s var(--apix-cubic-bezier);
}

.q-slider.is-missing {
  transition:
    transform 0.28s var(--apix-cubic-bezier),
    opacity 0.18s var(--apix-cubic-bezier);
}

/* Menu / Section */
.q-section {
  background: transparent;
  overflow: hidden;
}
.q-section-title {
  margin: 8px 6px 6px 6px;
  padding: 1px 6px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.4px;
  color: var(--apix-tertiary-dark-color);
  border: none;
  border-left: 2px solid var(--apix-primary-color);
  background-color: transparent;
}
.q-section-title:hover {
  color: var(--apix-primary-hover);
}

/* Empty */
.q-empty {
  padding: 46px 12px;
  text-align: center;
  color: var(--apix-tertiary-dark-color);
  align-items: center;
  justify-content: center;
}

.q-empty:deep(*) {
  color: var(--apix-tertiary-dark-color);
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
