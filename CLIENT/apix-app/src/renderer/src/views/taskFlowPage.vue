<template>
  <el-container>
    <el-aside class="aside-area">
      <HomePage />
    </el-aside>

    <el-main
      ref="page"
      class="main-area"
    >
      <div class="app-layout" style="height: 100%;">

        <FilePanel
          ref="filePanelRef"
          :workspace="[dirDict]"
          @change-workspace="changeWorkspace"
          @close="closeWorkspace"
          @expand-dir="expandDir"
          @collapse-dir="collapseDir"
          @create="reallyCreate"
          @delete="deletePath"
          @create-new-path="createNewPath"
          @hide-all-input="hideNewFileInput"
          @open-file="openFile"
        />

        <!-- 右边标签页（case列表）窗口 -->
        <div class="right-panel">
          <div class="editor-tabs-root">
            <!-- Tabs -->
            <div
              ref="tabsHeaderRef"
              class="editor-tabs-header"
            >
              <TabHeaderCard
                v-for="(tab, index) in tabs"
                :key="tab.tabKey"
                :tab="tab"
                :active="activeTab === tab.tabKey"
                @change-tab="changeTab"
                @middle-click="handleMiddleClick"
                @drag-start="handleDragStart(index)"
                @drop="handleDrop(index)"
                @close-tab="closeTab"
                @copy-path="(type, tab) => handleCopyPath(type, tab.tabKey, tab.title)"
                @open-in-local="(tab) => handleOpenInLocal(tab.tabKey, tab.title)"
                @close-item="handleCloseItem"
                @pin-tab="handlePinTab"
              />
            </div>

            <!-- Content -->
            <div class="editor-tabs-content">
              <div
                v-for="tab in tabs"
                :key="tab.tabKey"
                v-show="activeTab === tab.tabKey"
                class="editor-tab-pane"
              >
                <TabCardList
                  v-if="tab.content_mime === 'aflow'"
                  :items="tab.content ?? []"
                  :tab_key="tab.tabKey"
                  @update:content-change="handleContentChange(tab.tabKey)"
                />

                <CodeEditor
                  v-else-if="tab.content_mime === 'md' || tab.content_mime === 'py' || tab.content_mime === 'js' || tab.content_mime === 'txt' "
                  :ref="el => { if (el) { editorRefs[tab.tabKey] = el } else { delete editorRefs[tab.tabKey] } }"
                  v-model="tab.content"
                  :theme="store.config.dark_theme ? 'dark' : 'light'"
                  :lang="tab.content_mime"
                  @change:model-value="handleContentChange(tab.tabKey)"
                />
              </div>
            </div>
          </div>
        </div>

        <!-- 左边拖拽面板 -->
        <div class="left-panel" :class="{is_hide: (activatedTabMeta.mime !== 'aflow' && activatedTabMeta.mime !== 'agraph')}">
          <div class="left-panel-title-wrapper">
            <div class="left-panel-title">任务卡</div>
          </div>

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

        <div class="agent-panel" v-if="isAgentPanelShow" :class="{agent_panel_hide: activatedTabMeta.mime === 'aflow'}">
          <MiniChatPanel
            :page_id="'taskFlowPage'"
            :workspace="store.getWorkspace()"
            :active_file="'/workspace'+activeTab.substring(store.getWorkspace().length)"
            @quote-file="saveTabContent()"
          />
        </div>
      </div>
    </el-main>
  </el-container>

  <div class="bottom-btn-wrap">
    <button
      v-if="activatedTabMeta.mime === 'aflow'"
      class="commom-btn"
      @click="unfoldAllCards()"
    >
      全部展开
    </button>

    <button
      v-if="activatedTabMeta.mime === 'aflow'"
      class="commom-btn"
      @click="foldAllCards()"
    >
      全部折叠
    </button>

    <button
      v-if="activatedTabMeta.mime === 'md' || activatedTabMeta.mime === 'py' || activatedTabMeta.mime === 'js' || activatedTabMeta.mime === 'txt' "
      class="submit-btn agent-btn"
      :class="{panel_actived: isAgentPanelShow}"
      @click="showMiniAgentPanel"
    >
      <svg t="1779034242459" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="5513" width="20" height="20"><path class="path" d="M741.632 663.296a8.533333 8.533333 0 0 1 15.616 0l23.04 52.266667a42.666667 42.666667 0 0 0 18.602667 20.224l40.746666 22.272a8.533333 8.533333 0 0 1 0 14.933333l-40.746666 22.272a42.666667 42.666667 0 0 0-18.602667 20.224l-23.04 52.266667a8.533333 8.533333 0 0 1-15.616 0l-23.04-52.309334a42.709333 42.709333 0 0 0-18.474667-20.181333l-40.533333-22.272a8.533333 8.533333 0 0 1 0-14.933333l40.533333-22.272a42.666667 42.666667 0 0 0 18.474667-20.181334l23.04-52.309333zM411.136 238.72a21.333333 21.333333 0 0 1 40.106667 0l59.349333 162.986667a85.333333 85.333333 0 0 0 46.122667 49.066666l132.693333 57.728a21.333333 21.333333 0 0 1 0 39.125334l-132.693333 57.728a85.376 85.376 0 0 0-46.08 49.066666l-59.392 163.029334a21.333333 21.333333 0 0 1-40.106667 0l-59.306667-162.986667a85.376 85.376 0 0 0-46.165333-49.066667l-132.693333-57.770666a21.333333 21.333333 0 0 1 0-39.125334l132.693333-57.728a85.333333 85.333333 0 0 0 46.122667-49.066666l59.349333-162.986667zM741.632 188.373333a8.533333 8.533333 0 0 1 15.616 0l23.04 52.309334a42.666667 42.666667 0 0 0 18.602667 20.181333l40.746666 22.272a8.533333 8.533333 0 0 1 0 14.976l-40.746666 22.272a42.666667 42.666667 0 0 0-18.602667 20.181333l-23.04 52.309334a8.533333 8.533333 0 0 1-15.616 0l-23.04-52.352a42.666667 42.666667 0 0 0-18.474667-20.181334l-40.533333-22.186666a8.533333 8.533333 0 0 1 0-14.976l40.533333-22.272a42.666667 42.666667 0 0 0 18.474667-20.181334l23.04-52.352z" fill="currentColor" p-id="5514"></path></svg>
      智能体
    </button>

    <button
      class="submit-btn save-btn"
      :class="{save_all_btn: optionKeyPress}"
      @click="saveTabContent()"
    >
      <svg t="1779034751905" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="6501" width="14" height="14"><path d="M833.466 64H94.779L64 94.779v834.443L94.779 960h834.443L960 929.221V190.534l-10.26-20.519-95.755-99.175L833.466 64z m-577.955 61.557v256.489h448V125.557h116.275l78.656 78.656v690.809H128.977V125.557h126.534z m386.443 0v194.931H512V125.557h129.954z" fill="currentColor" p-id="6502"></path></svg>
      {{ optionKeyPress ? '全部保存' : '保存' }}
    </button>

    <button
      v-if="activatedTabMeta.mime === 'md' || activatedTabMeta.mime === 'aflow'"
      class="submit-btn"
      @click="submitCase()"
    >
      <svg t="1778959728742" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="6501" width="14" height="14"><path d="M748.083 484.116v59.486L119.768 960l-52.05-29.743V93.743L119.768 64l628.315 420.116z m-81.793 29.743L134.639 160.664v706.39L666.29 513.859zM346.556 867.054L874.49 513.859 346.556 160.664v-85.51l609.726 408.963v59.486L346.556 948.846v-81.792z" fill="currentColor" p-id="6502"></path></svg>
      {{ activatedTabMeta.mime !== 'md' ? '提交' : '预览' }}
    </button>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onBeforeUnmount, computed, shallowRef, toRaw, nextTick } from 'vue';
import { ElMessage } from 'element-plus'
import HomePage from './homePage.vue'
import TabCardList from './component/tab_card/TabCardList.vue'
import TabHeaderCard from './component/tab_card/comp/TabHeaderCard.vue'
import CodeEditor from './component/code_edit/code_editor.vue'
import MiniChatPanel from './component/mini_chat/MiniChatPanel.vue'
import { type CodeEditorExpose } from './component/code_edit/code_editor.vue'
import FilePanel from './component/file_panel/file_explorer.vue'
import { type NodeBase } from './component/file_panel/file_tree_node.vue'
import { useAppCacheData } from '../store/app.js'
import { useAuthStore } from '../store/auth.js'
import { ConfirmDialog } from './component/comp/confirmDialog.js'
import { mdDisplayer } from './component/comp/mdDisplayer.js'
import { globalCardDragState } from '../store/globalData.js'


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
  uid: string
  expanded: boolean
}

type BasicTaskCard = TabCardBase & {
  type: 'task'
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
  | BasicTaskCard
  | ScriptCard
  | NoteCard
  | FolderCard

type PresetCard = CardBase

type TabItem = {
  tabKey: string // File path
  title: string // File name
  content: TabCardItem[] | string
  content_mime: string
  version: number
  saved?: Boolean
  status?: 'outdated' | 'deleted' | 'default'
  pinned?: Boolean
}

// ------------------------
// 数据初始化
// ------------------------
const authStore = useAuthStore()
const store = useAppCacheData()
const cid = ref('')

const cards = reactive(store.cards as PresetCard[])
const tabs = reactive(store.tabs as TabItem[])

const activeTab = computed({
  get() {
    return store.activedTabKey || tabs[0]?.tabKey
  },
  set(value: string) {
    const idx = tabs.findIndex(t => t.tabKey === value)
    const tab = tabs[idx]
    if (!tab) return
    activatedTabMeta.value = {
      mime: tab.content_mime,
      name: tab.title,
      saved: tab.saved
    }
    store.activedTabKey = value
  }
})

// ------------------------
// 拖拽逻辑
// ------------------------
function onLeftDragStart(card: PresetCard) {
  globalCardDragState.sourceUid = null
  globalCardDragState.cardUid = card.id
  globalCardDragState.cardType = 'preset'
}

// ------------------------
// 删除左侧卡片
// ------------------------
async function removeLeftCard(id: String) {
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
    await store.saveCards()
    ElMessage({ type: 'success', message: '已删除', plain: true })
  } catch (err: any) {
    console.error('[removeLeftCard error]:', err?.message)
  }
}

// ------------------------
// 标签页增删、拖拽排序
// ------------------------
const tabsHeaderRef = ref<HTMLElement>()

const scrollTabIntoView = async (key: string) => {
  await nextTick()

  const container = tabsHeaderRef.value
  if (!container) return

  const tabEl =
    container.querySelector(
      `[data-tab-key="${CSS.escape(key)}"]`
    ) as HTMLElement | null

  if (!tabEl) return

  const containerRect = container.getBoundingClientRect()
  const tabRect = tabEl.getBoundingClientRect()

  const isLeftOverflow =
    tabRect.left < containerRect.left

  const isRightOverflow =
    tabRect.right > containerRect.right

  // Already fully visible
  if (!isLeftOverflow && !isRightOverflow) {
    return
  }

  tabEl.scrollIntoView({
    behavior: 'smooth',
    inline: 'nearest',
    block: 'nearest'
  })
}

const addTab = async (key, name, content, content_mime) => {
  const existingTab = tabs.find(tab => tab.tabKey === key)

  // Already opened
  if (existingTab) {
    activeTab.value = key

    await nextTick()
    await scrollTabIntoView(key)

    return
  }

  const newTab = {
    tabKey: key,
    title: name,
    content: content,
    content_mime: content_mime,
    saved: true,
    version: 0,
    status: 'default'
  }

  // Insert after current active tab
  const activeIndex =
    tabs.findIndex(
      tab => tab.tabKey === activeTab.value
    )

  // No active tab
  if (activeIndex === -1) {
    tabs.push(newTab)
  }
  else {
    tabs.splice(activeIndex + 1, 0, newTab)
  }

  activeTab.value = key

  await nextTick()
  await scrollTabIntoView(key)

  await store.saveTabs()
}

async function closeTab(tab: TabItem) {
  try {
    const tabKey = tab.tabKey
    const idx = tabs.findIndex(t => t.tabKey === tabKey)
    if (idx !== -1) {
      if (!tab.saved)
        await ConfirmDialog.confirm(
          `此标签页还没有被保存，未保存的内容将会丢失。`,
          `确定要关闭${tab.title}？`,
          {
            confirmButtonText: '确定',
            cancelButtonText: '取消',
            type: 'warning',
          }
        )

      tabs.splice(idx, 1)

      if (activeTab.value === tabKey && tabs.length > 0) {
        activeTab.value = tabs[0].tabKey
      }

      await store.saveTabs()
    }
  } catch {}
}

async function closeAllTab() {
  try {
    tabs.splice(0, tabs.length)
    await store.saveTabs()
  } catch {}
}

async function changeTab(tab: TabItem) {
  // Reload outdated file
  if (tab.status === 'outdated') {
    try {
      const result = await window.api.reReadFile(tab.tabKey, tab.version, tab.content)

      // File changed
      if (result.changed) {
        // Same base version -> apply patch
        if (result.version === tab.version) {
          // aflow / agraph
          if (isApixFileMime(tab.tabKey)) {
            // Not replace anything
          }
          // Markdown patch
          else {
            applyEditorPatch(tab.tabKey, result.patch)
          }
        }
        // External version newer
        else {
          // Direct replace
          if (Array.isArray(tab.content) && Array.isArray(result.content)) {
            tab.content.splice(0, tab.content.length, ...result.content)
          } else {
            tab.content = result.content
          }
          tab.version = result.version
        }
      }

      tab.status = 'default'
    } catch (err) {
      console.error('[changeTab reread outdated] error:', err)
      ElMessage({
        type: 'error',
        message: '文件重新同步失败',
        plain: true
      })
    }
  }

  activeTab.value = tab.tabKey
}

async function handleMiddleClick(e, tab: TabItem) {
  if (e.button === 1) await closeTab(tab)
}

const draggingTabIndex = ref<number | null>(null)

function handleDragStart(index: number) {
  draggingTabIndex.value = index
}

function handleDrop(targetIndex: number) {
  const sourceIndex = draggingTabIndex.value

  if (sourceIndex === null || sourceIndex === targetIndex) return

  const movedTab = tabs[sourceIndex]
  tabs.splice(sourceIndex, 1)
  tabs.splice(targetIndex, 0, movedTab)
  draggingTabIndex.value = null

  store.saveTabs()
}

const handleCopyPath = async (type: string, tabKey: string, title: string) => {
  console.log(".....", type, tabKey, title)
  if (type === 'name') {
    await window.api.copyToClipboard({ type: 'text', data: title })
  }
  else if (type === 'absolute') {
    await window.api.copyToClipboard({ type: 'text', data: tabKey })
  }
  else if (type === 'relative') {
    const root = store.getWorkspace()
    await window.api.copyToClipboard({ type: 'text', data: tabKey.substring(root.length) })
  }
}

const handleOpenInLocal = async (tabKey: string, title: string) => {
  await window.api.openDir(tabKey,  title)
}

const handleCloseItem = async (type: string, tab: TabItem) => {
  const currentIndex =
    tabs.findIndex(
      t => t.tabKey === tab.tabKey
    )

  if (currentIndex === -1) {
    return
  }

  // Close self
  if (type === 'self') {
    await closeTab(tab)
    return
  }

  let targetTabs: TabItem[] = []

  // Close others
  if (type === 'others') {
    targetTabs =
      tabs.filter(
        t => t.tabKey !== tab.tabKey
      )
  }

  // Close left
  else if (type === 'left') {
    targetTabs =
      tabs.slice(
        0,
        currentIndex
      )
  }

  // Close right
  else if (type === 'right') {
    targetTabs =
      tabs.slice(
        currentIndex + 1
      )
  }

  // Close saved
  else if (type === 'saved') {
    targetTabs =
      tabs.filter(
        t => t.saved === true
      )
  }

  // Ignore pinned tabs
  targetTabs =
    targetTabs.filter(
      t => !t.pinned
    )

  // Sequential close
  for (const item of [...targetTabs]) {
    const exists =
      tabs.find(
        t => t.tabKey === item.tabKey
      )

    if (!exists) {
      continue
    }

    await closeTab(exists)
  }
}

const handlePinTab = async (tab: TabItem) => {
  tab.pinned = !tab.pinned
  
  // Pinned tabs first
  tabs.sort((a, b) => {
    // Both same pinned state
    if (!!a.pinned === !!b.pinned) {
      return 0
    }

    return a.pinned ? -1 : 1
  })

  await store.saveTabs()
}

// ------------------------
// 文件目录
// ------------------------
const dirDict = ref(null)
const filePanelRef = ref<InstanceType<typeof FilePanel>>()

const eventTypesNeedRefreshWorkspaceTreeNode = new Set([
  'add',
  'unlink',
  'addDir',
  'unlinkDir'
])

const eventTypesNeedUpdateFileStatus = new Set([
  'change',
])

// Change workspace
const changeWorkspace = async (path) => {
  try {
    dirDict.value = await window.api.getDirectoryTree(path)
    store.setWorkspace(path)
    console.log('New workspace structure:', dirDict.value)
  } catch (error) {
    console.error('[changeWorkspace] error:', error)
  }
}

// Close workspace
const closeWorkspace = async () => {
  await closeAllTab()
  dirDict.value = null
  store.setWorkspace('')
  console.log('Clear workspace structure.')
}

// Find node by path
const findNodeByPath = (node, targetPath) => {
  if (!node) return null
  if (node.path === targetPath) return node
  if (node.type !== 'directory' || !Array.isArray(node.children)) return null
  for (const child of node.children) {
    const result = findNodeByPath(child, targetPath)
    if (result) return result
  }
  return null
}

// Remove node by path
const removeNodeByPath = (node, targetPath) => {
  if (!node || !Array.isArray(node.children)) return false
  const index = node.children.findIndex(child => child.path === targetPath)
  // Remove directly
  if (index !== -1) {
    node.children.splice(index, 1)
    return true
  }
  // Recursive search
  for (const child of node.children) {
    if (child.type === 'directory') {
      const removed = removeNodeByPath(child, targetPath)
      if (removed) return true
    }
  }
  return false
}

// Sort children
const sortChildren = (children) => {
  children.sort((a, b) => {
    // Directory first
    if (a.type !== b.type) {
      return a.type === 'directory' ? -1 : 1
    }
    return a.name.localeCompare(b.name)
  })
}

// Expand directory
const expandDir = async (path) => {
  try {
    const pathNode = await window.api.getDirectoryTree(path)
    if (!pathNode) return
    console.log("Get pathNode: ", pathNode)
    const currentNode = findNodeByPath(dirDict.value, path)
    if (!currentNode || currentNode.expanded) return
    currentNode.children = pathNode.children || []
    sortChildren(currentNode.children)
    currentNode.expanded = true
    console.log('Expand dir:', path)
  } catch (error) {
    console.error('[expandDir] error:', error)
  }
}

// Collapse directory
const collapseDir = async (path) => {
  try {
    const currentNode = findNodeByPath(dirDict.value, path)
    if (!currentNode) return

    // Whether opened tabs exist inside this directory
    const hasOpenedFile = tabs.some(tab =>
      tab.tabKey.startsWith(path + '/')
    )

    // Stop watcher only when no opened file exists
    if (!hasOpenedFile) {
      await window.api.collapseDirectoryTree(path)
    }

    // Only collapse ui
    currentNode.expanded = false

    console.log(
      'Collapse dir:',
      path,
      'keep watcher:',
      hasOpenedFile
    )

  } catch (error) {
    console.error('[collapseDir] error:', error)
  }
}

function isApixFileMime(filePath) {
  if (filePath.endsWith(".md")) return false
  else if (filePath.endsWith(".aflow") || filePath.endsWith(".agraph")) return true
  else return false
}

const isContntChangeWarningShow = ref(false)
// Merge fs events into dir tree
const watchWorkspace = async (events) => {
  for (const e of events) {
    if (eventTypesNeedRefreshWorkspaceTreeNode.has(e.type)) {
      // Find parent directory
      const parentNode = findNodeByPath(dirDict.value, e.parent)
      if (!parentNode) continue
      // Ensure children exists
      if (!Array.isArray(parentNode.children)) {
        parentNode.children = []
      }
      // Directory add
      if (e.type === 'addDir') {
        // Avoid duplicate
        const exists = parentNode.children.some(child => child.path === e.path)
        if (exists) continue
        parentNode.children.push({
          name: e.path.split('/').pop(),
          path: e.path,
          type: 'directory',
          children: []
        })
        sortChildren(parentNode.children)
      }
      // File add
      else if (e.type === 'add') {
        const exists = parentNode.children.some(child => child.path === e.path)
        if (exists) continue
        parentNode.children.push({
          name: e.path.split('/').pop(),
          path: e.path,
          type: 'file'
        })
        sortChildren(parentNode.children)
      }
      // Remove directory/file
      else if (e.type === 'unlink' || e.type === 'unlinkDir') {
        removeNodeByPath(dirDict.value, e.path)

        // Deleted file
        if (e.type === 'unlink') {
          const openedTab = tabs.find(t => t.tabKey === e.path)
          if (openedTab) {
            openedTab.status = 'deleted'
          }
        }

        // Deleted directory
        else if (e.type === 'unlinkDir') {
          const dirPath = e.path.endsWith('/')
            ? e.path
            : `${e.path}/`

          for (const tab of tabs) {
            // Mark all opened files inside deleted directory
            if (tab.tabKey.startsWith(dirPath)) {
              tab.status = 'deleted'
            }
          }
        }
      }
    }
    else if (eventTypesNeedUpdateFileStatus.has(e.type)) {
      if (e.type === 'change') {
        if (!e.path) continue
        const openedTab = tabs.find(t => t.tabKey === e.path)
        if (!openedTab) continue
        if (isApixFileMime(e.path)) {
          const content = JSON.stringify(toRaw(openedTab.content))
          const currentVersion = openedTab.version
          const result = await window.api.reReadFile(e.path, currentVersion, content)
          // Ignore self write
          if (!result.changed) continue

          if (!isContntChangeWarningShow.value) {
            isContntChangeWarningShow.value = true
            await ConfirmDialog.confirm(
              `检测到文件【${e.path}】被外部编辑，为防止文件格式被破坏，保存时将直接覆盖。`,
              '警告',
              {
                confirmButtonText: '确定',
                cancelButtonText: '',
                type: 'warning',
              }
            )
            isContntChangeWarningShow.value = false
          }
          openedTab.status = 'outdated'
          continue
        }
        else if (activeTab.value === e.path) {
          let content = openedTab.content
          const currentVersion = openedTab.version
          const result = await window.api.reReadFile(e.path, currentVersion, content)

          // Ignore self write
          if (!result.changed) continue

          // Version unchanged
          if (result.version === openedTab.version) {
            applyEditorPatch(openedTab.tabKey, result.patch)
            openedTab.status = 'default'
            continue
          }

          // Already waiting
          if (pendingReloadTimers.has(openedTab.tabKey)) continue

          pendingReloadTimers.set(openedTab.tabKey, true)

          ;(async () => {
            const stable = await waitUntilVersionStable(openedTab)
            pendingReloadTimers.delete(openedTab.tabKey)
            if (!stable) return

            const latestTab = tabs.find(t => t.tabKey === e.path)
            if (!latestTab) return

            let latestContent = latestTab.content

            const latestResult = await window.api.reReadFile(e.path, latestTab.version, latestContent)
            if (!latestResult.changed) return

            // Stable now
            if (latestResult.version === latestTab.version) {
              applyEditorPatch(latestTab.tabKey, latestResult.patch)
              latestTab.status = 'default'
            }
          })()
        }
        else {
          openedTab.status = 'outdated'
        }
      }
    }
  }
}

const reallyCreate = async (at_path, name, type) => {
  const c_path = at_path + '/' + name
  console.log("Create to path: ", c_path)
  if (type === 'file') {
    const p = await window.api.createFile(c_path)
    console.log("Create file: ", p)
  }
  else {
    const p = await window.api.createDirectory(c_path)
    console.log("Create directory: ", p)
  }
}

const deletePath = async (path) => {
  const currentNode = findNodeByPath(dirDict.value, path)
  if (!currentNode) return
  try {
    const wariningTail = currentNode.type === 'directory' ? '及其子目录？':'？'
    await ConfirmDialog.confirm(
      `您可以从回收站还原此文件。`,
      `确定要删除“${currentNode.name}”${wariningTail}`,
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )
    if (currentNode.type === 'directory') await window.api.deleteDirectory(currentNode.path)
    else await window.api.deleteFile(currentNode.path)
  } catch (err: any) {
    
  }
}

const createNewPath = async (at_path, type) => {
  const currentNode = findNodeByPath(dirDict.value, at_path)
  if (!currentNode) return
  await expandDir(at_path)
  currentNode.is_creating = true
  currentNode.creating_type = type
}

const openFile = async (path, name) => {
  const content_dict = await window.api.readFile(path)
  const content = content_dict['content']
  const content_mime = content_dict['mime']
  addTab(path, name, content, content_mime)
}

const saveTabContent = async () => {
  if (!optionKeyPress.value) {
    const tabKey = activeTab.value
    await store.saveTabContent(tabKey)
  }
  else {
    await store.saveAllTabContent()
  }
}

// ------------------------
// Markdown
// ------------------------
const editorRefs =
  shallowRef<
    Record<
      string,
      CodeEditorExpose
    >
  >({})

const pendingReloadTimers = new Map()
const RE_READ_IDLE_DELAY = 300

function applyEditorPatch(
  tabKey: string,
  patch: {
    from: number
    to: number
    insert: string
  }[]
) {
  const editor =
    editorRefs.value[
      tabKey
    ]

  if (!editor) return

  editor.applyPatch(
    patch
  )
}

async function waitUntilVersionStable(
  tab
) {
  return new Promise<boolean>(
    resolve => {

      const check = () => {

        const version =
          tab.version

        setTimeout(() => {

          const currentTab =
            tabs.find(
              t =>
                t.tabKey ===
                tab.tabKey
            )

          // Tab closed
          if (!currentTab) {
            resolve(false)
            return
          }

          // Stable
          if (
            currentTab.version ===
            version
          ) {
            resolve(true)
            return
          }

          // Still typing
          check()

        }, RE_READ_IDLE_DELAY)
      }

      check()
    }
  )
}

function handleContentChange(tabKey: string) {
  const tab = tabs.find(t => t.tabKey === tabKey)
  if (!tab) return
  tab.saved = false
  tab.version++
  if (tabKey === activeTab.value) {
    activeTab.value = tabKey // Update activatedTabMeta
  }
}

// ------------------------
// 页面布局控制
// ------------------------
const optionKeyPress = ref(false)
const activatedTabMeta = ref({})

let removeFsEvents = null

function hideNewFileInput(nodePath) {
  if (!nodePath || nodePath === '') return
  console.log("[hideNewFileInput] find input in: ", nodePath)
  const currentNode = findNodeByPath(dirDict.value, nodePath)
  if (!currentNode) return
  console.log("[handlePageClick] find node: ", currentNode)
  currentNode.is_creating = false
}

function handlePageClick(e: MouseEvent) {
  const target = e.target as HTMLElement
  // Exact create input
  const input = document.getElementById('file-tree-node-create-input')
  // Click is not on input
  if (input && target !== input && !input.contains(target) && filePanelRef) {
    const nodePath = filePanelRef.value?.creatingPath
    hideNewFileInput(nodePath)
  }
}

const globalHandleKeydown = async (
  e: KeyboardEvent & {
    isComposing?: boolean
    keyCode?: number
  }
) => {
  // IME composing
  if (e.isComposing || e.keyCode === 229) {
    return
  }

  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 's') {
    e.preventDefault()

    const tabKey = activeTab.value
    await store.saveTabContent(tabKey)
  }
  else if (e.key === 'Alt') {
    optionKeyPress.value = true
  }
}

const globalHandleKeyup = (e: KeyboardEvent) => {
  if (e.key === 'Alt') {
    optionKeyPress.value = false
  }
}

onMounted(async () => {
  removeFsEvents =
    window.api.onFsEvents(
      events => {
        watchWorkspace(events)
        console.log(events)
      }
    )
  window.addEventListener('click', handlePageClick, true)
  window.addEventListener('keydown', globalHandleKeydown)
  window.addEventListener('keyup', globalHandleKeyup)
  await authStore.restore()
  try {
    const dir = store.getWorkspace()
    console.log("[onMounted initWorkspace] dir: ", dir)
    if (dir && dir !== '') {
      await window.api.watchWorkspace(dir)
      dirDict.value = await window.api.getDirectoryTree(dir)
    }
    console.log("[onMounted initWorkspace] dirDict: ", dirDict.value)
  } catch (error) {
    console.error("[onMounted initWorkspace] error: ", error)
  }
  cid.value = authStore.user.user_uid
})

onBeforeUnmount(() => {
  removeFsEvents?.()
  window.removeEventListener('click', handlePageClick, true)
  window.removeEventListener('keydown', globalHandleKeydown)
  window.removeEventListener('keyup', globalHandleKeyup)
})

// ------------------------
// 提交逻辑
// ------------------------
const submitCase = async () => {
  if (activatedTabMeta.value.mime !== 'md') {
    const idx = tabs.findIndex(t => t.tabKey === activeTab.value)
    if (idx === -1) {
      ElMessage({ type: 'error', message: '未找到任务流文件', plain: true })
      return
    }
    const tab = tabs[idx]
    const payload = serializeCards(tab.content)

    try {
      const res = await window.api.submitCase(cid.value, payload)
      ElMessage({ type: 'success', message: '已提交', plain: true })
      console.log('[submitCase] submit payload:', payload)
    } catch (err) {
      console.error('[submitCase] fail:', err)
      ElMessage({ type: 'error', message: '提交失败: ' + err, plain: true })
    }
  }
  else {
    const idx = tabs.findIndex(t => t.tabKey === activeTab.value)
    if (idx === -1) {
      ElMessage({ type: 'error', message: '未找到文件', plain: true })
      return
    }
    const tab = tabs[idx]
    mdDisplayer.show(tab.content)
  }
}

function serializeCards(cards: TabCardItem[]) {
  return cards.map(card => {
    if (card.type === 'task') {
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
  const idx = tabs.findIndex(t => t.tabKey === activeTab.value)
  if (idx === -1) {
    return
  }
  const tab = tabs[idx]

  function recurse(cards: TabCardItem[]) {
    for (const card of cards) {
      card.expanded = true

      if (card.type === 'folder' && Array.isArray(card.content) && card.content.length > 0) {
        recurse(card.content)
      }
    }
  }

  recurse(tab.content)
}

function foldAllCards() {
  const idx = tabs.findIndex(t => t.tabKey === activeTab.value)
  if (idx === -1) {
    return
  }
  const tab = tabs[idx]

  function recurse(cards: TabCardItem[]) {
    for (const card of cards) {
      card.expanded = false

      if (card.type === 'folder' && Array.isArray(card.content) && card.content.length > 0) {
        recurse(card.content)
      }
    }
  }

  recurse(tab.content)
}

const isAgentPanelShow = ref(false)
function showMiniAgentPanel() {
  isAgentPanelShow.value = !isAgentPanelShow.value
}
</script>

<style scoped>
.no-drag {
  -webkit-app-region: no-drag;
}

.app-layout {
  display: flex;
  max-height: calc(100vh - 36px);
  max-width: 100%;
  overflow: hidden;
  border-radius: var(--apix-border-radius-base);
  overflow: hidden;
}

/* 左边拖拽面板 */
.left-panel {
  opacity: 1;
  width: 146px;
  background-color: var(--apix-panel-layer-2-background) !important;
  padding: 0;
  margin: 0px !important;
  box-shadow: inset -1px 0 0 0 var(--apix-border-disabled); 
  transition: 
    box-shadow 0.42s var(--apix-cubic-bezier),
    width 0.42s var(--apix-cubic-bezier),
    opacity 0.42s var(--apix-cubic-bezier);
}

.left-panel.is_hide {
  opacity: 0.3;
  width: 0;
  box-shadow: none;
  overflow: hidden;
}

.left-panel-title-wrapper {
  height: 38px;

  display: flex;
  align-items: center;
  justify-content: space-between;

  padding: 0 10px;

  flex-shrink: 0;

  border-bottom: .5px solid var(--apix-border-disabled);
}

.left-panel-title {
  font-size: 13px;
  letter-spacing: 1px;
  font-weight: 700;

  color: var(--apix-default-dark-color);
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
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
  box-sizing: border-box;
}

/* 标签页 */
.editor-tabs-root {
  display: flex;
  flex-direction: column;
  height: 100%;
}

/* Tabs header */
.editor-tabs-header {
  display: flex;
  align-items: stretch;
  overflow-x: auto;
  overflow-y: hidden;
  z-index: 9999;

  height: 38px;
  min-height: 38px;

  background-color: var(--apix-default-light-color);
  border-radius: 0;
  box-shadow: var(--apix-shadow-layer-1);
  transition: box-shadow 320ms var(--apix-cubic-bezier);
  border-bottom: .5px solid var(--apix-border-disabled);
}

.editor-tabs-header:hover {
  box-shadow: var(--apix-shadow-layer-2);
}

.editor-tabs-header::-webkit-scrollbar {
  height: 0;
}

.editor-tabs-header {
  scrollbar-width: none;
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

.left-card-container {
  padding: 15px 0px;
  padding-top: 0;
  background-color: transparent;
}

.editor-tabs-content {
  height: 100%;
  overflow: scroll;
}

.right-card-container {
  position: relative;
  max-height: 100%;
  margin: 0 auto;
  border-radius:
    var(--apix-border-radius-base) var(--apix-border-radius-base) 0 0;
}

.agent-panel.agent_panel_hide {
  width: 0;
  overflow: hidden;
}

.bottom-btn-wrap {
  -webkit-app-region: no-drag;
  
  opacity: 0.65;
  position: absolute;
  top: -30px;
  right: 36px;
  margin: auto;

  height: 30px;
  padding: 3px 0;
  box-sizing: border-box;

  z-index: 2000;
  isolation: isolate;

  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 6px;

  overflow: hidden;

  transition: opacity .25s var(--apix-cubic-bezier);
}

.bottom-btn-wrap:hover {
  opacity: 1;
}

.submit-btn,
.commom-btn {
  width: 72px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px !important;
  border: none;
  font-size: 14px;
  gap: 6px;
  cursor: pointer;
  transition: transform 0.2s var(--apix-cubic-bezier),
              background 0.2s var(--apix-cubic-bezier),
              width .35s var(--apix-cubic-bezier) !important;
  box-shadow: inset 0 0 0 1px rgba(0, 0, 0, 0.08);
}

.submit-btn {
  color: var(--apix-default-button-text) !important;
  background: var(--apix-default-button-background) !important;
  box-shadow: inset 0 0 0 1px rgba(0, 0, 0, 0.08) !important;
}

.submit-btn:hover {
  color: var(--apix-common-button-text) !important;
  background: var(--apix-common-button-hover) !important;
}

.agent-btn.panel_actived,
.submit-btn:active {
  color: var(--apix-common-button-text) !important;
  background: var(--apix-common-button-active) !important;
}

.commom-btn {
  color: var(--apix-default-button-text) !important;
  background: var(--apix-default-button-background) !important;
  box-shadow: inset 0 0 0 1px rgba(0, 0, 0, 0.08) !important;
}

.commom-btn:hover {
  background: var(--apix-default-button-hover) !important;
}

.commom-btn:active {
  background: var(--apix-default-button-active) !important;
}

.save-btn {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.save-btn.save_all_btn {
  width: 100px;
}

.agent-btn {
  gap: 2px !important;
  padding: 1px 4px 1px 1px;
}
</style>