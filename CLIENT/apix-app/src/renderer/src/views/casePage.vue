<template>
  <el-container>
    <el-aside class="aside-area">
      <HomePage />
    </el-aside>

    <el-main
      v-if="showPage"
      ref="page"
      class="main-area"
      :style="{
        height: pageHeight + 'px',
      }"
    >
      <div class="app-layout" style="height: 100%;">
        <!-- 左边拖拽面板 -->
        <div class="left-panel">
          <h3 class="left-panel-title">任务卡</h3>

          <el-scrollbar class="left-card-container">
            <div
              v-for="card in cards"
              :key="card.id"
              class="draggable-card"
              draggable="true"
              @dragstart="onLeftDragStart(card)"
            >
              {{ card.title }}

              <button
                type="primary"
                class="no-drag fixed-left-card-delete"
                @click="removeLeftCard(card.id)"
                @mousedown.stop
                @dragstart.stop
              >
                <svg t="1776755725116" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="8731" width="20" height="20"><path d="M328.777143 377.904762l31.719619 449.657905h310.662095l31.695238-449.657905h73.264762L744.106667 832.707048a73.142857 73.142857 0 0 1-72.94781 67.998476H360.496762a73.142857 73.142857 0 0 1-72.94781-68.022857L255.488 377.904762h73.289143z m159.207619 22.649905v341.333333h-73.142857v-341.333333h73.142857z m133.729524 0v341.333333h-73.142857v-341.333333h73.142857zM146.285714 256h731.428572v73.142857H146.285714v-73.142857z m518.265905-121.904762v73.142857h-292.571429v-73.142857h292.571429z" p-id="8732" fill="var(--apix-tertiary-dark-color)"></path></svg>
              </button>
            </div>
          </el-scrollbar>
        </div>

        <!-- 右边标签页（case列表）窗口 -->
        <div class="right-panel">
          <n-tabs
            v-model:value="activeTab"
            type="card"
            size="small"
            class="ntabs"
            closable
            scrollable
            @close="closeTab"
            @add="addTab"
            @update:value="changeTab"
          >
            <n-tab-pane
              v-for="tab in tabs"
              :key="tab.tabKey"
              class="NTabSpane"
              :name="tab.tabKey"
              :tab="tab.title"
            >
              <el-scrollbar
                class="right-card-container"
                :style="{ overflow: 'auto' }"
              >
                <TabCardList
                  :items="tab.items ?? []"
                  :tab_key="tab.tabKey"
                />
              </el-scrollbar>
            </n-tab-pane>
          </n-tabs>

          <div class="bottom-btn-wrap">
            <div class="ctrl-btn-area">
              <el-button
                type="primary"
                text
                class="commom-btn"
                @click="unfoldAllCards()"
              >
                全部展开
              </el-button>

              <el-button
                type="primary"
                text
                class="commom-btn"
                @click="foldAllCards()"
              >
                全部折叠
              </el-button>
            </div>

            <el-button
              type="primary"
              round
              class="submit-btn"
              @click="submitCase()"
            >
              提交
            </el-button>
          </div>
        </div>
      </div>
    </el-main>
  </el-container>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onBeforeUnmount, computed } from 'vue'
import { NTabPane, NTabs } from 'naive-ui'
import { ElMessage } from 'element-plus'
import HomePage from './homePage.vue'
import TabCardList from './component/tab_card/TabCardList.vue'
import { useAppCacheData } from '../store/app.js'
import { useAuthStore } from '../store/auth'
import { ConfirmDialog } from './component/comp/confirmDialog.js'
import { defaultCards, globalState } from '../store/globalData.js'

// ------------------------
// 类型定义
// ------------------------
type CardBase = {
  id: string
  title: string
  type: string
  level: string
}

type TabCardBase = CardBase & {
  uid: number
  showCardBody: boolean
  expanded: boolean
  btnType: string
  btnIcon: string
}

type InterfaceCard = TabCardBase & {
  type: 'interface'
  address: string
  description: string
}

type DatabaseCard = TabCardBase & {
  type: 'database'
  address: string
  description: string
}

type ScriptCard = TabCardBase & {
  type: 'script'
  script: string
  description: string
}

type NoteCard = TabCardBase & {
  type: 'note'
  description?: string
}

type FolderCard = TabCardBase & {
  type: 'folder'
  content: TabCardItem[]
}

type TabCardItem =
  | InterfaceCard
  | DatabaseCard
  | ScriptCard
  | NoteCard
  | FolderCard

type PresetCard = CardBase

type TabItem = {
  tabKey: string
  title: string
  items: TabCardItem[]
}

// ------------------------
// 数据初始化
// ------------------------
const authStore = useAuthStore()
const store = useAppCacheData()
const cid = ref('')

if (!store.cards || store.cards.length === 0) {
  store.cards = defaultCards()
  store.saveCards()
}

const cards = reactive(store.cards as PresetCard[])
const tabs = reactive(store.tabs as TabItem[])

const activeTab = computed({
  get() {
    return store.activedTabName || tabs[0]?.tabKey
  },
  set(value: string) {
    store.activedTabName = value
  }
})

// ------------------------
// 拖拽逻辑
// ------------------------
function onLeftDragStart(card: PresetCard) {
  globalState.draggedStartCardUid_parent = 0
  globalState.draggedStartCardUid = 0
  globalState.draggedTabCard = ''
  globalState.draggedCard = JSON.stringify(card)
  console.log('onLeftDragStart: globalState.draggedCard: ' + globalState.draggedCard)
}

// ------------------------
// 删除左侧卡片
// ------------------------
async function removeLeftCard(id: string) {
  try {
    await ConfirmDialog.confirm(
      '要删除此卡片吗？删除后不可撤销',
      '删除确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )

    const idx = cards.findIndex(c => c.id === id)
    if (idx === -1) {
      ElMessage({ type: 'warning', message: '未找到要删除的卡片', plain: true })
      return
    }

    const card = cards[idx]
    if (card.level === 'system') {
      await ConfirmDialog.confirm(
        '此卡片为系统级卡片，删除后只能通过 设置 > 重载预设卡片 进行恢复',
        '警告',
        {
          confirmButtonText: '确定',
          cancelButtonText: '取消',
          type: 'warning',
        }
      )
    }

    cards.splice(idx, 1)
    store.saveCards()
    ElMessage({ type: 'success', message: '已删除', plain: true })
  } catch (err: any) {
    console.log('删除卡片被取消或出错:', err?.message)
  }
}

// ------------------------
// 标签页增删
// ------------------------
function addTab() {
  const id = new Date().toISOString().replace(/[-:.TZ]/g, '') + String(Math.random())
  const tabKey = `${id}`

  tabs.push({
    tabKey,
    title: `任务流 ${tabs.length + 1}`,
    items: [] as TabCardItem[],
  })

  activeTab.value = tabKey
  store.activedTabName = tabKey
  store.saveTabs()
}

async function closeTab(tabKey: string) {
  try {
    await ConfirmDialog.confirm(
      '要删除该标签页吗？此操作将同时删除标签页里所有卡片',
      '关闭确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )

    const idx = tabs.findIndex(t => t.tabKey === tabKey)
    if (idx !== -1) {
      tabs.splice(idx, 1)

      if (activeTab.value === tabKey && tabs.length > 0) {
        activeTab.value = tabs[0].tabKey
        store.activedTabName = tabs[0].tabKey
      }

      store.saveTabs()
      ElMessage({ type: 'success', message: '已关闭', plain: true })
    }
  } catch {}
}

function changeTab(value: string) {
  console.log('Changed Tab value:' + value)
  store.activedTabName = value
  console.log('Changed store.activedTabName value:' + activeTab.value)
}

// ------------------------
// 页面布局控制
// ------------------------
const page = ref<HTMLElement | null>(null)
const showPage = ref(false)

const pageHeight = ref(window.innerHeight - 30)
const tabsWidth = ref(window.innerWidth - 36)

const updateSessionPageHeight = () => {
  pageHeight.value = window.innerHeight - 30
  tabsWidth.value = window.innerWidth - 36
}

onMounted(async () => {
  window.addEventListener('resize', updateSessionPageHeight)
  await authStore.restore()
  cid.value = authStore.user.user_uid
  showPage.value = true
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', updateSessionPageHeight)
})

// ------------------------
// 提交逻辑
// ------------------------
const submitCase = async () => {
  console.log('Submitted! Cases in Tab ' + activeTab.value)
  const idx = tabs.findIndex(t => t.tabKey === activeTab.value)
  if (idx === -1) {
    ElMessage({ type: 'error', message: '提交失败: 未找到待提交的任务', plain: true })
    return
  }
  const tab = tabs[idx]
  const payload = serializeCards(tab.items)

  try {
    const res = await window.api.submitCase(cid.value, payload)
    ElMessage({ type: 'success', message: '已提交', plain: true })
    console.log('[submitCase] submit payload:', payload)
  } catch (err) {
    console.error('[submitCase] fail:', err)
    ElMessage({ type: 'error', message: '提交失败: ' + err, plain: true })
  }
}

function serializeCards(cards: TabCardItem[]) {
  return cards.map(card => {
    if (card.type === 'interface') {
      return {
        type: card.type,
        id: card.id,
        title: card.title,
        address: card.address,
        description: card.description,
      }
    }

    if (card.type === 'database') {
      return {
        type: card.type,
        id: card.id,
        title: card.title,
        address: card.address,
        description: card.description,
      }
    }

    if (card.type === 'script') {
      return {
        type: card.type,
        id: card.id,
        title: card.title,
        script: card.script,
        description: card.description,
      }
    }

    if (card.type === 'note') {
      return {
        type: card.type,
        id: card.id,
        title: card.title,
        description: card.description ?? '',
      }
    }

    if (card.type === 'folder') {
      return {
        type: card.type,
        id: card.id,
        title: card.title,
        content: serializeCards(card.content),
      }
    }

    return card
  })
}

// ------------------------
// 卡片折叠与展开
// ------------------------
function unfoldAllCards() {
  console.log('unfoldAllCards! Cases in Tab ' + activeTab.value)
  const idx = tabs.findIndex(t => t.tabKey === activeTab.value)
  if (idx === -1) {
    return
  }
  const tab = tabs[idx]

  function recurse(cards: TabCardItem[]) {
    for (const card of cards) {
      card.btnType = 'success'
      card.btnIcon = 'Check'
      card.expanded = true
      card.showCardBody = true

      if (card.type === 'folder' && Array.isArray(card.content) && card.content.length > 0) {
        recurse(card.content)
      }
    }
  }

  recurse(tab.items)
  store.saveAllTabs()
}

function foldAllCards() {
  console.log('foldAllCards! Cases in Tab ' + activeTab.value)
  const idx = tabs.findIndex(t => t.tabKey === activeTab.value)
  if (idx === -1) {
    return
  }
  const tab = tabs[idx]

  function recurse(cards: TabCardItem[]) {
    for (const card of cards) {
      card.btnType = 'primary'
      card.btnIcon = 'Postcard'
      card.expanded = false
      card.showCardBody = false

      if (card.type === 'folder' && Array.isArray(card.content) && card.content.length > 0) {
        recurse(card.content)
      }
    }
  }

  recurse(tab.items)
  store.saveAllTabs()
}
</script>

<style scoped>
.no-drag {
  -webkit-app-region: no-drag;
}

.app-layout {
  display: flex;
  max-height: calc(100vh - 36px);
  overflow: hidden;
}

/* 左边拖拽面板 */
.left-panel {
  background-color: var(--apix-panel-layer-2-background) !important;
  padding: 0;
  margin: 0px !important;
  box-shadow: inset -1px 0 0 0 var(--apix-border-disabled); 
}

.left-panel-title {
  display: table; 
  margin: 0 auto; 
  color: var(--apix-secondary-dark-color);
  padding: 12px 0 0 0;
}

:deep(.left-panel .el-scrollbar__view) {
  padding: 0 6px;
}

/* 右边标签页窗口 */
.right-panel {
  position: relative;
  max-width: 100%; 
  min-width: 140px; 
  width: 100%;
  padding: 12px 24px 0 24px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  box-sizing: border-box;
  border-radius: 24px;
}

.fixed-left-card-delete {
  border: none;
  width: 16px;
  height: 16px;
  background-color: transparent;
  opacity: 0;
  position: absolute;
  top: 3px;
  right: 9px;
  z-index: 2000;
}

.fixed-left-card-delete:deep(.icon) {
  width: 16px;
  height: 16px;
}

.draggable-card:hover .fixed-left-card-delete {
  opacity: 1;
}

.draggable-card {
  position: relative;
  border-radius: var(--apix-border-radius-base);
  min-width: 100px;
  max-width: 100px;
  margin: 8px;
  padding: 8px;
  cursor: grab;
  color: var(--apix-primary-dark);
  box-shadow: var(--apix-shadow-layer-1);
  text-align: center;
  transition:
    background-color 320ms var(--apix-cubic-bezier),
    transform 320ms var(--apix-cubic-bezier),
    box-shadow 320ms var(--apix-cubic-bezier);

  background: var(--apix-panel-layer-5-background);
  border: 1px solid var(--apix-default-light-color);
}

.draggable-card:hover {
  transform: translateY(-1px);
  box-shadow: var(--apix-shadow-layer-3);
}

.main-area {
  padding: 0px;
  position: relative;
}

.left-card-container {
  padding: 15px 0px;
  padding-top: 0;
  background-color: transparent;
}

.right-card-container {
  position: relative;
  margin: 0 auto;
}

.bottom-btn-wrap {
  position: absolute;
  bottom: 30px;
  left: 50%;
  transform: translateX(-50%);
  margin: auto;

  width: 80%;
  max-width: 840px;
  height: fit-content;
  padding: 16px;
  box-sizing: border-box;

  z-index: 2000;
  isolation: isolate;

  display: flex;
  flex-direction: row;
  justify-content: space-between;
  align-items: center;

  overflow: hidden;
  border-radius: var(--apix-panel-border-radius);
  backdrop-filter: saturate(300%) blur(16px);
  background: color-mix(in oklch, var(--apix-panel-layer-3-background) 70%, transparent);
  box-shadow: var(--apix-shadow-md);
}

.ctrl-btn-area {
  display: flex;
  height: fit-content;
}

.submit-btn,
.commom-btn {
  width: 80px;
  height: 32px;
  padding: 6px 16px;
  border-radius: var(--apix-button-border-radius) !important;
  border: none;
  font-size: 14px;
  cursor: pointer;
  transition: transform 0.2s var(--apix-cubic-bezier),
              background 0.2s var(--apix-cubic-bezier) !important;
  box-shadow: inset 0 0 0 1px rgba(0, 0, 0, 0.08);
}

.submit-btn:hover,
.commom-btn:hover {
  transform: scale(1.03);
}

.submit-btn:active,
.commom-btn:active {
  transform: scale(1.01);
}

.submit-btn {
  color: var(--apix-success-button-text) !important;
  background: var(--apix-success-button-background) !important;
  box-shadow: inset 0 0 0 1px rgba(0, 0, 0, 0.08) !important;
}

.submit-btn:hover {
  background: var(--apix-success-button-hover) !important;
}

.submit-btn:active {
  background: var(--apix-success-button-active) !important;
}

.commom-btn {
  color: var(--apix-default-button-text) !important;
  background: var(--apix-default-button-background) !important;
}

.commom-btn:hover {
  background: var(--apix-default-button-hover) !important;
}

.commom-btn:active {
  background: var(--apix-default-button-active) !important;
}

.NTabSpane {
  position: relative;
  padding-top: 0 !important;
  max-height: calc(100vh - 82px);
  padding: 0 !important;
}

.ntabs {
  transition: transform 260ms cubic-bezier(0.2, 0.8, 0.2, 1);
}
</style>

<style scoped>
:deep(.n-tabs .n-tabs-nav) {
  background-color: var(--apix-default-light-color);
  border-radius: var(--apix-border-radius-base) !important;
  box-shadow: var(--apix-shadow-layer-1);
  transition: box-shadow 320ms var(--apix-cubic-bezier);
}
:deep(.n-tabs .n-tabs-nav:hover) {
  box-shadow: var(--apix-shadow-layer-2);
}

:deep(.n-tabs .n-tabs-nav.n-tabs-nav--top.n-tabs-nav--card-type .n-tabs-tab-pad),
:deep(.n-tabs .n-tabs-nav.n-tabs-nav--top.n-tabs-nav--card-type .n-tabs-pad) {
  border: 0;
}

:deep(.n-tabs.n-tabs--top > .n-tabs-nav .n-tabs-nav-scroll-wrapper.n-tabs-nav-scroll-wrapper--shadow-start::before, .n-tabs.n-tabs--bottom > .n-tabs-nav .n-tabs-nav-scroll-wrapper.n-tabs-nav-scroll-wrapper--shadow-start::before) {
  box-shadow: inset 10px 0 8px -8px rgba(0, 0, 0, .03);
}

:deep(.n-tabs.n-tabs--top > .n-tabs-nav .n-tabs-nav-scroll-wrapper.n-tabs-nav-scroll-wrapper--shadow-end::after, .n-tabs.n-tabs--bottom > .n-tabs-nav .n-tabs-nav-scroll-wrapper.n-tabs-nav-scroll-wrapper--shadow-end::after) {
  box-shadow: inset -10px 0 8px -8px rgba(0, 0, 0, .03);
}

:deep(.n-tabs .n-tabs-nav-scroll-wrapper) {
  border-radius: var(--apix-border-radius-base) !important;
}

:deep(.n-tabs .n-tabs-nav.n-tabs-nav--top.n-tabs-nav--card-type .n-tabs-tab.n-tabs-tab--addable .n-base-icon) {
  color: var(--apix-tertiary-dark-color);
}

:deep(.n-tabs .n-tabs-nav.n-tabs-nav--top.n-tabs-nav--card-type .n-tabs-tab.n-tabs-tab--addable .n-base-icon:hover) {
  color: var(--apix-default-dark-color);
}

:deep(.n-tabs-tab-wrapper) {
  transform-origin: left;
  background-color: transparent !important;
  animation: scaleFade-n-tabs-tab-wrapper 0.4s var(--apix-cubic-bezier);
}

:deep(.n-tabs-tab-pad) {
  background-color: transparent !important;
  width: 0;
}

@keyframes scaleFade-n-tabs-tab-wrapper {
  0% {
    opacity: 0;
    width: 0;
  }
  100% {
    opacity: 1;
    width: 100px;
  }
}

:deep(.n-tabs .n-tabs-nav.n-tabs-nav--top.n-tabs-nav--card-type .n-tabs-tab) {
  border-radius: 0 !important;
  overflow: hidden;
  background-color: var(--apix-panel-layer-2-background);
  border: none;
  border-right: 1px solid var(--apix-default-light-color);
  color: var(--apix-secondary-dark-color);
  height: 32px;
  min-width: 100px !important;
  transition: none;
}

:deep(.n-tabs .n-tabs-nav.n-tabs-nav--top.n-tabs-nav--card-type .n-tabs-tab.n-tabs-tab--active) {
  background-color: var(--apix-panel-layer-5-background);
  color: var(--apix-primary-active);
}

:deep(.n-tabs-wrapper .n-tabs-tab-wrapper:nth-last-child(2) .n-tabs-tab) {
  width: 40px;
  border: none !important;
}

:deep(.n-tabs-wrapper .n-tabs-tab-wrapper .n-tabs-tab .n-base-icon) {
  color: var(--apix-secondary-dark-color);
}

:deep(.n-tabs .n-tabs-tab .n-tabs-tab__close) {
  transition: none;
}

:deep(.n-tabs .n-tabs-tab .n-tabs-tab__close:hover) {
  background-color: var(--apix-lightest-color);
}

:deep(.n-tabs .n-tab-pane) {
  border: 0;
}
</style>