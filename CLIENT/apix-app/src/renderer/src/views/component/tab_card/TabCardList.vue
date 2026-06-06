<template>
  <div
    class="tab-content"
    draggable="false"
    @dragover.prevent
    @drop.stop="DragCardDropInCardList()"
  >
    <div
      v-for="(item, index) in items"
      :key="item.uid"
      class="tab-card-wrapper"
      @drop.stop="DragCardDropOnAnotherCard(item, index, $event)"
      @dragover.prevent
      :draggable="!item.expanded"
    >
      <Task
        v-if="item.type === 'task'"
        :self="item"
        :tab_key="tab_key"
        :parent_uid="null"
        @update:delete-card="removeTabCard"
        @update:content-change="notifyContentChange"
      />

      <Script
        v-else-if="item.type === 'script'"
        :self="item"
        :tab_key="tab_key"
        :parent_uid="null"
        @update:delete-card="removeTabCard"
        @update:content-change="notifyContentChange"
      ></Script>

      <Folder
        v-else-if="item.type === 'folder'"
        :self="item"
        :tab_key="tab_key"
        :parent_uid="null"
        @update:delete-card="removeTabCard"
        @update:content-change="notifyContentChange"
      />

      <Note
        v-else-if="item.type === 'note'"
        :self="item"
        :tab_key="tab_key"
        :parent_uid="null"
        @update:delete-card="removeTabCard"
        @update:content-change="notifyContentChange"
      />
    </div>

    <div
      class="tab-card-bottom-line"
      :key="'bottomCard'"
    >
      <div>已放置 {{ items.length || 0 }} 枚卡片</div> 
    </div>
    <div :key="'bottomArea'" class="bottom-area" :style="{ height: 450 + 'px' }"></div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useAppCacheData } from '../../../store/app.js'
import Task from './card/Task.vue'
import Script from './card/Script.vue'
import Folder from './card/Folder.vue'
import Note from './card/Note.vue'
import {
  globalCardDragState,
  genUUID,
  defaultCards,
  clearGlobalDragState,
  globalDragHoverCard
} from '../../../store/globalData.js'

type CardBase = {
  id: string
  title: string
  type: string
  level: string
}

type TabCardBase = CardBase & {
  uid: string
  expanded: boolean
  marked?: boolean
  markMessage?: string
}

type taskCardBase = TabCardBase & {
  type: 'task'
  address: string
  description: string
}

type scriptCardBase = TabCardBase & {
  type: 'script'
  script: string
  description: string
}

type noteCardBase = TabCardBase & {
  type: 'note'
  cardColor: string
  noteContent: string
}

type folderCardBase = TabCardBase & {
  type: 'folder'
  content: TabCardItem[]
}

type TabCardItem =
  | taskCardBase
  | scriptCardBase
  | noteCardBase
  | folderCardBase

const props = defineProps<{
  items: TabCardItem[]
  tab_key: string
}>()

const emit = defineEmits<{
  (e: 'update:TabCardList', tab_tabKey: string, items: TabCardItem[]): void
  (e: 'update:contentChange'): void
}>()

const store = useAppCacheData()

function createCardByID(cardID: string): TabCardItem {
  const virtualCard = defaultCards.find(item => item.id === cardID)
  console.log("[createCardByID] Create virtualCard:", virtualCard)

  const base: TabCardItem = {
    id: virtualCard.id,
    title: virtualCard.title,
    type: virtualCard.type,
    level: virtualCard.level,
    uid: genUUID(),
    expanded: false,
    marked: false,
    markMessage: '已标记',
  }

  switch (virtualCard.type) {
    case 'task':
      return {
        ...base,
        address: '',
        description: '',
      }

    case 'script':
      return {
        ...base,
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
        cardColor: '',
        noteContent: '',
      }

    default:
      return null
  }
}

// function findCardFromTree(tree: TabCardItem[], uid: string, deleteFound: boolean = false, expandPath: boolean = false): TabCardItem | null {
//   if (!Array.isArray(tree)) {
//     return null
//   }

//   let nodePath = []

//   for (let i = 0; i < tree.length; i++) {
//     const node = tree[i]

//     if (node.uid === uid) {
//       if (deleteFound) tree.splice(i, 1)
//       return node
//     }

//     if (
//       node.type === 'folder'
//       &&
//       Array.isArray(node.content)
//       &&
//       node.content.length > 0
//     ) {
//       const found = findCardFromTree(node.content, uid, deleteFound)

//       if (found) return found
//     }
//   }

//   return null
// }

function findCardFromTree(
  tree: TabCardItem[],
  uid: string,
  deleteFound: boolean = false,
  expandPath: boolean = false,
  nodePath: TabCardItem[] = [],
): TabCardItem | null {
  if (!Array.isArray(tree)) {
    return null
  }

  for (let i = 0; i < tree.length; i++) {
    const node = tree[i]

    if (node.uid === uid) {
      if (expandPath) {
        for (const parent of nodePath) {
          parent.expanded = true
        }
      }

      if (deleteFound) {
        tree.splice(i, 1)
      }

      return node
    }

    if (
      node.type === 'folder'
      && Array.isArray(node.content)
      && node.content.length > 0
    ) {
      nodePath.push(node)

      const found = findCardFromTree(
        node.content,
        uid,
        deleteFound,
        expandPath,
        nodePath,
      )

      nodePath.pop()

      if (found) {
        return found
      }
    }
  }

  return null
}

function DragCardDropInCardList() {
  console.log("[DragCardDropInCardList] globalCardDragState:", globalCardDragState)
  globalDragHoverCard.value = ''
  // Append
  if (
    globalCardDragState.cardUid === "" // Not drag a card
  ) return

  if (globalCardDragState.cardType === 'preset') {
    const newCard = createCardByID(globalCardDragState.cardUid)

    props.items.push(newCard)
    notifyContentChange()
    clearGlobalDragState()
    return
  }

  if (globalCardDragState.cardType === 'inTab') {
    const currentTab = store.findTab(props.tab_key)
    const virtualCard = findCardFromTree(currentTab.content, globalCardDragState.cardUid, true)
    if (!currentTab || !virtualCard) return

    props.items.push(virtualCard)
    notifyContentChange()
    clearGlobalDragState()
    return
  }
}

function DragCardDropOnAnotherCard(dropOn: TabCardItem, dropIndex: number) {
  console.log("[DragCardDropOnAnotherCard] globalCardDragState:", globalCardDragState)
  globalDragHoverCard.value = ''
  // Insert
  if (globalCardDragState.cardUid === "") return

  if (globalCardDragState.cardType === 'preset') {
    const newCard = createCardByID(globalCardDragState.cardUid)

    props.items.splice(dropIndex, 0, newCard)
    notifyContentChange()
    clearGlobalDragState()
    return
  }

  if (globalCardDragState.cardType === 'inTab') {
    const currentTab = store.findTab(props.tab_key)
    const virtualCard = findCardFromTree(currentTab.content, globalCardDragState.cardUid, true)
    if (!currentTab || !virtualCard) return

    // After delete origin card, we should refresh dropIndex
    if (globalCardDragState.sourceUid === null) {
      const shouldDropIndex = props.items.findIndex(t => t.uid === dropOn.uid)
      if (shouldDropIndex !== -1) dropIndex = shouldDropIndex
    } 

    props.items.splice(dropIndex, 0, virtualCard)
    notifyContentChange()
    clearGlobalDragState()
    return
  }
}

function removeCardFromTree(tree: TabCardItem[], uid: string): boolean {
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

function removeTabCard(cardUid: string) {
  console.log('TabCardList: removeTabCard: ' + cardUid)
  const idx = props.items.findIndex(c => c.uid === cardUid)

  if (idx !== -1) {
    props.items.splice(idx, 1)
    ElMessage({ type: 'success', message: '已删除' })
    notifyContentChange()
  }
}

function notifyContentChange() {
  emit('update:contentChange')
}
</script>

<style scoped>
.no-drag {
  -webkit-app-region: no-drag;
}

.tab-content {
  position: relative;
  background: transparent;
  display: flex;
  flex-direction: column;
  flex-wrap: wrap;
  gap: 6px;
  padding: 12px 12px 0 12px;
}

.tab-card-wrapper {
  height: auto;
  position: relative;
  border-radius: var(--apix-border-radius-base);
}
</style>