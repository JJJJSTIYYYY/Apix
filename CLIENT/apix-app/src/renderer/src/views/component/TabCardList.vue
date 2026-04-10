<template>
  <div
    class="tab-content"
    draggable="false"
    @dragover.prevent
    @drop.stop="DragCardDropInCardList()"
    :style="{ minHeight: pageHeight + 'px' }"
  >
    <div
      v-for="(item, index) in items"
      :key="item.uid"
      class="tab-card-wrapper"
      @drop.stop="DragCardDropInCardList_insert(item, index, $event)"
      @dragover.prevent
      :draggable="!item.expanded"
    >
      <Interface
        v-if="item.type === 'interface'"
        :self="item"
        :tab_key="tab_key"
        :father_uid="null"
        @update:delete-card="removeTabCard"
      />

      <Database
        v-else-if="item.type === 'database'"
        :self="item"
        :tab_key="tab_key"
        :father_uid="null"
        @update:delete-card="removeTabCard"
      />

      <Script
        v-else-if="item.type === 'script'"
        :self="item"
        :tab_key="tab_key"
        :father_uid="null"
        @update:delete-card="removeTabCard"
      />

      <Folder
        v-else-if="item.type === 'folder'"
        :self="item"
        :tab_key="tab_key"
        :father_uid="null"
        @update:delete-card="removeTabCard"
      />

      <Note
        v-else-if="item.type === 'note'"
        :self="item"
        :tab_key="tab_key"
        :father_uid="null"
        @update:delete-card="removeTabCard"
      />
    </div>

    <!-- 底部提示 -->
    <div
      class="tab-card-bottom-line"
      :key="'bottomCard'"
      style="height: 40px; color: rgba(0,0,0,0.5); background-color: rgba(255,255,255,0.3);"
    >
      - 这是底线
    </div>
    <div :key="'bottomArea'" class="bottom-area" :style="{ height: 450 + 'px' }"></div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useAppCacheData } from '../../store/app'
import Interface from './tab_card_body/Interface.vue'
import Database from './tab_card_body/Database.vue'
import Script from './tab_card_body/Script.vue'
import Folder from './tab_card_body/Folder.vue'
import Note from './tab_card_body/Note.vue'
import { globalState } from '../../store/globalData.js'

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

const props = defineProps<{
  items: TabCardItem[]
  tab_key: string
}>()

const emit = defineEmits<{
  (e: 'update:TabCardList', tab_tabKey: string, items: TabCardItem[]): void
}>()

const store = useAppCacheData()

function createCardByType(virtualCard: CardBase): TabCardItem {
  const base = {
    id: virtualCard.id,
    title: virtualCard.title,
    type: virtualCard.type,
    level: virtualCard.level,
    uid: Date.now() + Math.random(),
    showCardBody: false,
    expanded: false,
    btnType: 'primary',
    btnIcon: 'Postcard',
  }

  switch (virtualCard.type) {
    case 'interface':
      return {
        ...base,
        type: 'interface',
        address: '',
        description: '',
      }

    case 'database':
      return {
        ...base,
        type: 'database',
        address: '',
        description: '',
      }

    case 'script':
      return {
        ...base,
        type: 'script',
        script: '',
        description: '',
      }

    case 'folder':
      return {
        ...base,
        type: 'folder',
        content: [],
      }

    case 'note':
      return {
        ...base,
        type: 'note',
        description: '',
      }

    default:
      return {
        ...base,
        type: 'note',
        description: '',
      }
  }
}

// ------------------------
// 左侧来的卡片放置最底下时使用
// ------------------------
function DragCardDropInCardList() {
  if (
    (globalState.draggedStartCardUid === 0 && globalState.draggedCard === '')
  ) {
    return
  }

  if (globalState.draggedCard) {
    const virtualCard = JSON.parse(globalState.draggedCard)
    const newCard = createCardByType(virtualCard)
    props.items.push(newCard)
    store.saveTab(props.tab_key)
  } else if (globalState.draggedTabCard) {
    const virtualCard = JSON.parse(globalState.draggedTabCard) as TabCardItem

    const currentTab = store.tabs.find(t => t.tabKey === props.tab_key)
    if (!currentTab) {
      console.warn('未找到 tab:', props.tab_key)
      return
    }

    removeCardFromTree(currentTab.items, virtualCard.uid)
    props.items.push(virtualCard)
    store.saveTab(props.tab_key)
  }

  globalState.draggedStartCardUid_parent = 0
  globalState.draggedStartCardUid = 0
  globalState.draggedCard = ''
  globalState.draggedTabCard = ''
}

// ------------------------
// 卡片放置在其他卡片上时使用
// ------------------------
function DragCardDropInCardList_insert(item: TabCardItem, dropIndex: number, event: DragEvent) {
  console.log('DragCardDropInCardList_insert: dropIndex is ' + dropIndex)

  if (globalState.draggedTabCard) {
    const virtualCard = JSON.parse(globalState.draggedTabCard) as TabCardItem
    const currentIndex = props.items.findIndex(c => c.uid === virtualCard.uid)

    if (currentIndex !== -1) {
      props.items.splice(currentIndex, 1)
      props.items.splice(dropIndex, 0, virtualCard)
    } else {
      const currentTab = store.tabs.find(t => t.tabKey === props.tab_key)
      if (!currentTab) {
        console.warn('未找到 tab:', props.tab_key)
        return
      }

      removeCardFromTree(currentTab.items, virtualCard.uid)
      props.items.splice(dropIndex, 0, virtualCard)
    }

    store.saveTab(props.tab_key)
  } else if (globalState.draggedCard) {
    const virtualCard = JSON.parse(globalState.draggedCard)
    const newCard = createCardByType(virtualCard)
    props.items.splice(dropIndex, 0, newCard)
    store.saveTab(props.tab_key)
  }

  globalState.draggedStartCardUid_parent = 0
  globalState.draggedStartCardUid = 0
  globalState.draggedCard = ''
  globalState.draggedTabCard = ''
}

// ------------------------
// 删除右侧卡片
// ------------------------
function removeCardFromTree(tree: TabCardItem[], uid: number): boolean {
  if (!Array.isArray(tree)) return false

  for (let i = 0; i < tree.length; i++) {
    const node = tree[i]

    if (node.uid === uid) {
      tree.splice(i, 1)
      return true
    }

    if (node.type === 'folder' && Array.isArray(node.content) && node.content.length > 0) {
      if (removeCardFromTree(node.content, uid)) {
        return true
      }
    }
  }

  return false
}

function removeTabCard(cardUid: number) {
  console.log('TabCardList: removeTabCard: ' + cardUid)
  const idx = props.items.findIndex(c => c.uid === cardUid)

  if (idx !== -1) {
    props.items.splice(idx, 1)
    ElMessage({ type: 'success', message: '已删除' })
    store.saveTab(props.tab_key)
  }
}

// ------------------------
// 页面布局控制
// ------------------------
const pageHeight = ref(window.innerHeight)

const updateTabContentHeight = () => {
  pageHeight.value = window.innerHeight
}

onMounted(() => {
  window.addEventListener('resize', updateTabContentHeight)
})

// ------------------------
// 页面动画控制
// ------------------------
const DURATION = 100
const EASE = 'linear'

function beforeLeave(el: HTMLElement) {
  el.style.boxSizing = 'border-box'
  el.style.height = el.offsetHeight + 'px'
  el.style.transition = `height ${DURATION}ms ${EASE}, margin ${DURATION}ms ${EASE}, padding ${DURATION}ms ${EASE}, opacity ${DURATION}ms ${EASE}`
}

function leave(el: HTMLElement, done: () => void) {
  requestAnimationFrame(() => {
    el.style.height = '0px'
    el.style.opacity = '0'
    el.style.paddingTop = '0px'
    el.style.paddingBottom = '0px'
    el.style.marginBottom = '0px'
  })

  setTimeout(() => {
    done()
  }, DURATION + 10)
}

function afterLeave(el: HTMLElement) {
  el.style.transition = ''
  el.style.height = ''
  el.style.opacity = ''
  el.style.paddingTop = ''
  el.style.paddingBottom = ''
  el.style.marginBottom = ''
}
</script>

<style scoped>
.no-drag {
  -webkit-app-region: no-drag;
}

.tab-content {
  position: relative;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.192);
  padding: 8px 12px;
  display: flex;
  flex-direction: column;
  flex-wrap: wrap;
  gap: 6px;
}

.tab-card-wrapper {
  height: auto;
  position: relative;
}

.tab-card-bottom-line {
  box-sizing: border-box;
  background: rgba(255, 255, 255, 0.92);
  border-radius: 8px;
  padding: 8px 12px;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.1);
  height: 30px;
}
</style>