<template>
  <el-container>
    <el-aside style="width: auto;">
      <HomePage />
    </el-aside>

    <keep-alive>
      <transition name="fade" mode="out-in">
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
            <div
              class="left-panel"
              :style="{
                height: '100%',
                width: '20%',
                padding: '0px',
                color: '#666666'
              }"
            >
              <h3 style="display: table; margin: 0 auto; opacity: 0.65;">任务卡</h3>

              <el-scrollbar
                class="left-card-container"
                :max-height="pageHeight"
                :style="{
                  height: '100%',
                  minWidth: '80%',
                  maxWidth: '80%',
                  display: 'block',
                  margin: '0 auto',
                }"
              >
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
                    <el-icon><Delete /></el-icon>
                  </button>
                </div>
              </el-scrollbar>
            </div>

            <!-- 右边标签页（case列表）窗口 -->
            <div
              class="right-panel"
              :style="{ height: '100%', maxWidth: '100%', minWidth: '140px', width: '100%' }"
            >
              <n-tabs
                v-model:value="activeTab"
                type="card"
                size="small"
                class="ntabs"
                closable
                addable
                scrollable
                tab-style="min-width: 40px;"
                :style="{ height: '100%' }"
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
                  :style="{ height: pageHeight - 100 + 'px' }"
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

                  <div class="bottom-btn-wrap">
                    <el-button
                      type="primary"
                      round
                      class="submit-btn fixed-submit"
                      @click="submitCase(tab)"
                    >
                      提交
                    </el-button>

                    <el-button
                      type="primary"
                      text
                      class="commom-btn"
                      @click="unfoldAllCards(tab)"
                    >
                      全部展开
                    </el-button>

                    <el-button
                      type="primary"
                      text
                      class="commom-btn"
                      @click="foldAllCards(tab)"
                    >
                      全部折叠
                    </el-button>
                  </div>
                </n-tab-pane>
              </n-tabs>
            </div>
          </div>
        </el-main>
      </transition>
    </keep-alive>
  </el-container>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onBeforeUnmount, computed } from 'vue'
import { NTabPane, NTabs } from 'naive-ui'
import { ElMessage } from 'element-plus'
import { Delete } from '@element-plus/icons-vue'
import HomePage from './homePage.vue'
import TabCardList from './component/TabCardList.vue'
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
const submitCase = async (tab: TabItem) => {
  console.log('Submitted! Cases in Tab ' + activeTab.value)

  const payload = serializeCards(tab.items)

  try {
    const res = await window.api.submitCase(cid.value, payload)
    ElMessage({ type: 'success', message: '已提交', plain: true })
    console.log('submit payload:', payload)
  } catch (err) {
    console.error('提交失败:', err)
    ElMessage({ type: 'error', message: '提交失败', plain: true })
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
function unfoldAllCards(tab: TabItem) {
  console.log('unfoldAllCards! Cases in Tab ' + activeTab.value)

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

function foldAllCards(tab: TabItem) {
  console.log('foldAllCards! Cases in Tab ' + activeTab.value)

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
.app-layout {
  display: flex;
  height: 100%;
  gap: 12px;
  padding: 12px;
  box-sizing: border-box;
}

/* 左边拖拽面板 */
.left-panel {
  background: rgba(255, 255, 255, 0.887);
  border-radius: 12px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  box-sizing: border-box;
  /* box-shadow: 0 2px 6px rgba(97, 133, 124, 0.1); */
  max-width: 170px;
}

/* 右边标签页窗口 */
.right-panel {
  position: relative;
  background: rgba(255, 255, 255, 0.887);
  border-radius: 12px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  box-sizing: border-box;
  /* box-shadow: 0 2px 6px rgba(97, 133, 124, 0.243); */
}

.no-drag {
  -webkit-app-region: no-drag;
}

.fixed-left-card-delete {
  border: none;
  width: 16px;
  height: 16px;
  color: #888888;
  background-color: transparent;
  opacity: 0;
  position: absolute;
  top: 5px;
  right: 8px;
  z-index: 2000;
  transition: all 0.25s ease;
}

.draggable-card:hover .fixed-left-card-delete {
  opacity: 1;
}

.draggable-card {
  position: relative;
  border-radius: 8px;
  margin-bottom: 6px;
  min-width: 80px;
  margin: 8px;
  padding: 8px;
  cursor: grab;
  color: rgba(50, 114, 109, 0.761);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  text-align: center;
  transition:
    background-color 320ms cubic-bezier(0.2, 0.8, 0.2, 1),
    transform 320ms cubic-bezier(0.2, 0.8, 0.2, 1),
    box-shadow 320ms cubic-bezier(0.2, 0.8, 0.2, 1);

  background: rgba(255, 255, 255, 0.592);
  border: 1px solid rgba(129, 192, 179, 0.518);
  box-shadow:
    0 3px 10px rgba(31, 102, 135, 0.084);
}

.draggable-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}

.draggable-card::after {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: inherit;
  z-index: 1;

  box-shadow:
    inset 0 1px 1px rgba(255, 255, 255, 0.5),
    inset 0 -1px 1px rgba(255, 255, 255, 0.3),
    inset 1px 0 2px rgba(255, 255, 255, 0.15),
    inset -1px 0 2px rgba(255, 255, 255, 0.15);

  pointer-events: none;
}

.draggable-card::before {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: inherit;
  z-index: -1;

  background: inherit;
  backdrop-filter: blur(6px) saturate(130%);
  -webkit-backdrop-filter: blur(6px) saturate(130%);

  mask: radial-gradient(circle at center,
        rgba(0, 0, 0, 0) 40%,
        rgba(0, 0, 0, 1) 100%);
  -webkit-mask: radial-gradient(circle at center,
        rgba(0, 0, 0, 0) 40%,
        rgba(0, 0, 0, 1) 100%);
}

.main-area {
  padding: 0px;
  position: relative;
}

.fade-enter-from {
  opacity: 0;
  transform: scale(0.99);
}

.fade-enter-to {
  opacity: 1;
  transform: scale(1);
}

.fade-leave-from {
  opacity: 1;
  transform: scale(1);
}

.fade-leave-to {
  opacity: 0;
  transform: scale(0.99);
}

.fade-enter-active,
.fade-leave-active {
  transition:
    opacity 0.5s cubic-bezier(0.4, 0, 0.2, 1),
    transform 0.5s cubic-bezier(0.4, 0, 0.2, 1);
}

.left-card-container {
  padding: 15px;
  background-color: transparent;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}

.NTabSpane {
  position: relative;
}

.right-card-container {
  position: relative;
  width: 95%;
  margin: 0 auto;
  padding: 8px;
}

.bottom-btn-wrap {
  position: absolute;
  right: 6px;
  bottom: 0;
  left: 50%;
  transform: translateX(-50%);
  margin: auto 10px 6px 10px;

  width: 80%;
  max-width: 670px;
  height: 60px;

  border-radius: 1rem;
  z-index: 2000;
  isolation: isolate;

  box-shadow:
    0 10px 26px rgba(0, 0, 0, 0.166),
    0 2px 6px rgba(0, 0, 0, 0.05);

  overflow: hidden;
  border: 1px solid color-mix(in srgb, #fff 10%, transparent);
  -webkit-backdrop-filter: saturate(180%) blur(16px);
  backdrop-filter: saturate(180%) blur(16px);
  -webkit-transition: all 0.3s cubic-bezier(0.215, 0.61, 0.355, 1);
  transition: all 0.3s cubic-bezier(0.215, 0.61, 0.355, 1);
  border-color: transparent;
  background-color: color-mix(in srgb, #ebebeb 30%, transparent);
}

.bottom-btn-wrap::after {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: inherit;
  z-index: 1;

  box-shadow:
    inset 0 1px 2px rgba(255, 255, 255, 0.8),
    inset 0 -1px 2px rgba(255, 255, 255, 0.6),
    inset 2px 0 3px rgba(255, 255, 255, 0.25),
    inset -2px 0 3px rgba(255, 255, 255, 0.25);

  pointer-events: none;
}

.bottom-btn-wrap::before {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: inherit;
  z-index: -1;

  background: inherit;
  background-color: rgb(255, 255, 255);
  backdrop-filter: blur(12px) saturate(160%);
  -webkit-backdrop-filter: blur(12px) saturate(160%);

  mask: radial-gradient(circle at center,
        rgba(0, 0, 0, 0) 0%,
        rgba(0, 0, 0, 1) 100%);
  -webkit-mask: radial-gradient(circle at center,
        rgba(0, 0, 0, 0) 0%,
        rgba(0, 0, 0, 1) 100%);
}

.fixed-submit {
  position: absolute;
  right: 12px;
  top: 10px;
  height: calc(100% - 20px);
  width: 16%;
  z-index: 2000;
}

.fixed-commom {
  position: absolute;
  z-index: 2000;
}

.submit-btn {
  color: #003328d2;
  border: none;
  border-radius: 8px;
  overflow: hidden;
  background: rgba(62, 255, 191, 0.406);
  backdrop-filter: blur(6px) saturate(180%);
  -webkit-backdrop-filter: blur(6px) saturate(180%);
  border: 1px solid rgba(255, 255, 255, 0.6);
  box-shadow:
    0 8px 24px rgba(6, 130, 101, 0.216),
    inset 0 4px 16px rgba(255, 255, 255, 0.25);
  transition:
    transform 200ms cubic-bezier(0.2, 0.8, 0.2, 1),
    box-shadow 200ms cubic-bezier(0.2, 0.8, 0.2, 1),
    color 200ms cubic-bezier(0.2, 0.8, 0.2, 1);
}

.submit-btn::after {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: inherit;
  background: rgba(0, 255, 0, 0.08);
  backdrop-filter: blur(2px);
  -webkit-backdrop-filter: blur(2px);

  box-shadow:
    inset -8px -6px 0px -8px rgba(100, 255, 100, 0.9),
    inset 0px -8px 0px -6px rgba(100, 255, 100, 0.9);

  opacity: 0.55;
  z-index: -1;
  filter: blur(1px) brightness(115%);
}

.submit-btn:hover {
  transform: scale(1.05);
  color: #003320db;
  box-shadow: 0 8px 28px rgba(94, 249, 223, 0.49);
}

.submit-btn:active {
  transform: scale(0.95);
  color: #003320ae;
  box-shadow: 0 6px 20px rgba(70, 210, 100, 0.3);
}

.commom-btn {
  border: none;
  border-radius: 8px;
  margin-top: 10px;
  height: calc(100% - 20px);
  width: 16%;
  overflow: hidden;
  color: rgba(38, 101, 97, 0.686);

  background: rgba(211, 211, 211, 0.15);
  backdrop-filter: blur(6px) saturate(180%);
  -webkit-backdrop-filter: blur(6px) saturate(180%);

  border: 1px solid rgba(255, 255, 255, 0.6);
  box-shadow:
    0 8px 24px rgba(31, 99, 135, 0.15),
    inset 0 4px 16px rgba(255, 255, 255, 0.25);

  transition:
    transform 200ms cubic-bezier(0.2, 0.8, 0.2, 1),
    box-shadow 200ms cubic-bezier(0.2, 0.8, 0.2, 1);
}

.commom-btn::after {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: inherit;
  background: rgba(165, 165, 165, 0.08);
  backdrop-filter: blur(2px);
  -webkit-backdrop-filter: blur(2px);

  box-shadow:
    inset -8px -6px 0px -8px rgba(255, 255, 255, 0.9),
    inset 0px -8px 0px -6px rgba(255, 255, 255, 0.9);

  opacity: 0.55;
  z-index: -1;
  filter: blur(1px) brightness(115%);
}

.commom-btn:hover {
  transform: scale(1.05);
  box-shadow: 0 8px 28px rgba(235, 236, 246, 0.496);
}

.commom-btn:active {
  transform: scale(0.95);
  box-shadow: 0 6px 20px rgba(200, 200, 180, 0.3);
}

.ntabs {
  transition: transform 260ms cubic-bezier(0.2, 0.8, 0.2, 1);
}
</style>