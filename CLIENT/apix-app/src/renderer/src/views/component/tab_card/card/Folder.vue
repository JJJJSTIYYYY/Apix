<template>
  <div
    class="tab-card"
    :class="{ expanded: self.expanded, dragging: globalDragHoverCard === self.uid }"
    :draggable="!self.expanded"
    @dragstart.stop="onTabCardDragStart"
    @dragenter.stop="onDragEnter"
    @dragover.prevent
    @dragleave.stop="onDragLeave"
    @drop.prevent="onDrop"
  >
    <!-- 卡片头 -->
    <div
      class="tab-card-header no-drag"
      :class="{ expanded: self.expanded }"
    >
      <div style="display: flex; flex-direction: row;">
        <div style="width: fit-content; height: 16px; align-self: center;">
          <svg
            t="1758388194426"
            class="icon"
            viewBox="0 0 1024 1024"
            version="1.1"
            xmlns="http://www.w3.org/2000/svg"
            p-id="52264"
            width="16"
            height="16"
          >
            <path
              d="M405.79 96a32 32 0 0 1 24.256 11.128l0.322 0.381L527.483 224h347.833c40.832 0 74.014 32.76 74.674 73.432l0.01 1.235v192c0 17.673-14.327 32-32 32-17.496 0-31.713-14.042-31.996-31.471l-0.004-0.53v-192c0-5.793-4.627-10.512-10.4-10.662l-0.284-0.004H512.5a32 32 0 0 1-24.256-11.128l-0.323-0.381L390.806 160H149.684c-5.808 0-10.53 4.626-10.68 10.383l-0.004 0.284v682.666c0 5.794 4.627 10.513 10.4 10.663l0.284 0.004h320.132c17.673 0 32 14.327 32 32 0 17.496-14.042 31.713-31.471 32h-320.66c-40.833 0-74.015-32.76-74.675-73.432l-0.01-1.235V170.667c0-40.828 32.775-73.998 73.45-74.657l1.234-0.01H405.79z m427.745 499.664l0.377 0.37 106.71 106.667c12.379 12.373 12.502 32.362 0.372 44.887l-0.371 0.377-106.71 106.667c-12.5 12.494-32.761 12.49-45.256-0.01-12.369-12.374-12.488-32.355-0.362-44.877l0.372-0.377 84.069-84.035-84.07-84.034c-12.374-12.37-12.501-32.351-0.38-44.878l0.371-0.377c12.37-12.374 32.351-12.502 44.878-0.38z m-170.35 0.38c12.369 12.374 12.489 32.356 0.362 44.878l-0.372 0.377-84.07 84.034 84.07 84.035c12.375 12.37 12.503 32.351 0.38 44.877l-0.37 0.378c-12.37 12.374-32.351 12.502-44.878 0.38l-0.377-0.37-106.71-106.668c-12.379-12.372-12.502-32.361-0.372-44.886l0.371-0.378 106.71-106.666c12.5-12.495 32.761-12.49 45.256 0.009z"
              p-id="52265"
            />
          </svg>
        </div>

        <input
          v-model="self.title"
          class="tab-title-input no-drag"
          placeholder="卡片夹"
          @change="onTabCardTitleChange"
          @mouseup="onMouseUpInput"
          @focusout="onMouseUpInput"
          @mousemove="onMouseUpInput"
          @mouseenter="onMouseUpInput"
        />
      </div>

      <PopMenu
        v-if="isShowMenu"
        :style="menuStyle"
        @close-menu="closePopMenu"
        @mark-card="markCard"
        @mark-content="updateMarkContent"
      />

      <el-tooltip
        v-if="isShowMarkUICtrl"
        :content="self.markMessage"
        placement="left"
        effect="light"
        raw-content
      >
        <transition name="scale-fade">
          <button
            v-if="self.marked"
            key="11"
            class="mark-btn"
            :class="{ mark_btn_right: markBtnRight }"
            @click="hideMark"
          >
            <svg
              t="1778086454896"
              class="icon"
              viewBox="0 0 1024 1024"
              version="1.1"
              xmlns="http://www.w3.org/2000/svg"
              p-id="10188"
              width="20"
              height="20"
            >
              <path
                d="M661.333333 426.666667a149.333333 149.333333 0 1 1-298.666666 0 149.333333 149.333333 0 0 1 298.666666 0z m-58.660571 0a90.672762 90.672762 0 1 0-181.345524 0 90.672762 90.672762 0 0 0 181.345524 0z"
                p-id="10189"
                fill="var(--apix-lightest-color)"
              />
              <path
                d="M853.333333 426.666667c0 231.18019-341.333333 512-341.333333 512S170.666667 657.846857 170.666667 426.666667c0-188.513524 152.81981-341.333333 341.333333-341.333334s341.333333 152.81981 341.333333 341.333334z m-58.660571 0c0-156.111238-126.537143-282.672762-282.672762-282.672762-156.111238 0-282.672762 126.537143-282.672762 282.672762 0 44.080762 16.579048 94.98819 46.201905 149.504 29.330286 53.906286 69.193143 107.203048 110.250667 154.916571A1537.926095 1537.926095 0 0 0 512 860.598857a1537.926095 1537.926095 0 0 0 126.22019-129.511619c41.057524-47.713524 80.920381-101.010286 110.250667-154.916571 29.622857-54.51581 46.201905-105.423238 46.201905-149.504z"
                p-id="10190"
                fill="var(--apix-lightest-color)"
              />
            </svg>
          </button>
        </transition>
      </el-tooltip>

      <div
        class="tab-card-btn-area"
        @mouseenter="markBtnRight = false"
        @mouseleave="markBtnRight = true"
      >
        <el-button
          ref="menuBtnRef"
          type="info"
          class="tab-card-btn-menu"
          @click="showPopMenu"
        >
          <el-icon>
            <MoreFilled />
          </el-icon>
        </el-button>

        <el-button
          class="tab-card-btn-more"
          :class="{ tabcardbtnmoreexpanded: self.expanded }"
          @click="editTabCard"
        >
          <el-icon>
            <component :is="self.expanded ? Check : Postcard" />
          </el-icon>
        </el-button>

        <el-button
          type="danger"
          class="tab-card-btn-close"
          @click="removeThisCard"
        >
          <el-icon>
            <Close />
          </el-icon>
        </el-button>
      </div>
    </div>

    <!-- Folder 卡片体 -->
    <div
      v-if="self.expanded"
      class="folder-card-body"
    >
      <div
        class="place-holder-tag"
        style="width: 152px;"
      />
      <div
        class="folder-body-wrapper"
        :style="{ height: 'auto', overflow: 'auto', scrollbarWidth: 'none' }"
      >
        <div
          class="tab-content"
          draggable="false"
          :style="{ minHeight: 'auto' }"
          @dragover.prevent
          @drop.stop="DragCardDropInCardList"
        >
          <div
            v-for="(item, index) in self.content"
            :key="item.uid"
            class="tab-card-wrapper"
            :draggable="!item.expanded"
            @drop.stop="DragCardDropOnAnotherCard(item, index)"
            @dragover.prevent
          >
            <Task
              v-if="item.type === 'task'"
              :parent_uid="self.uid"
              :self="item"
              :tab_key="tab_key"
              @update:delete-card="deleteTabCardInContent"
              @update:content-change="notifyContentChange"
            />

            <Script
              v-else-if="item.type === 'script'"
              :parent_uid="self.uid"
              :self="item"
              :tab_key="tab_key"
              @update:delete-card="deleteTabCardInContent"
              @update:content-change="notifyContentChange"
            ></Script>

            <Folder
              v-else-if="item.type === 'folder'"
              :parent_uid="self.uid"
              :self="item"
              :tab_key="tab_key"
              @update:delete-card="deleteTabCardInContent"
              @update:content-change="notifyContentChange"
            />

            <Note
              v-else-if="item.type === 'note'"
              :parent_uid="self.uid"
              :self="item"
              :tab_key="tab_key"
              @update:delete-card="deleteTabCardInContent"
              @update:content-change="notifyContentChange"
            />
          </div>

          <div
            key="bottomCard"
            class="tab-card-bottom-line"
          >
            卡片夹中 {{ self.content.length || 0 }} 枚卡片
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  MoreFilled,
  Close,
  Check,
  Postcard,
} from '@element-plus/icons-vue'

import { useAppCacheData } from '../../../../store/app.js'
import { ConfirmDialog } from '../../comp/confirmDialog.js'
import { InputDialog } from '../../comp/inputDialog.js'
import {
  globalCardDragState,
  clearGlobalDragState,
  genUUID,
  defaultCards,
  globalDragHoverCard
} from '../../../../store/globalData.js'
import Task from './Task.vue'
import Script from './Script.vue'
import Folder from './Folder.vue'
import Note from './Note.vue'
import PopMenu from '../comp/PopMenu.vue'

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

type TaskCardBase = TabCardBase & {
  type: 'task'
  address: string
  description: string
}

type ScriptCardBase = TabCardBase & {
  type: 'script'
  script: string
  description: string
}

type NoteCardBase = TabCardBase & {
  type: 'note'
  cardColor: string
  noteContent: string
}

type FolderCardBase = TabCardBase & {
  type: 'folder'
  content: TabCardItem[]
}

type TabCardItem = TaskCardBase | ScriptCardBase | NoteCardBase | FolderCardBase

const props = defineProps<{
  parent_uid?: string
  self: FolderCardBase
  tab_key: string
}>()

const emit = defineEmits<{
  (e: 'update:delete-card', card_uid: string): void
  (e: 'update:contentChange', card_uid: string): void
}>()

const store = useAppCacheData()

// ------------------------
// 初始化默认值
// ------------------------
props.self.content ??= []
props.self.marked ??= false
props.self.markMessage ??= '已标记'

// ------------------------
// 右侧标签页里卡片的拖拽逻辑
// ------------------------
function onDragEnter() {
  globalDragHoverCard.value = props.self.uid
}

function onDragLeave() {
}

function onDrop() {
  globalDragHoverCard.value = ''
}

function onTabCardDragStart() {
  globalCardDragState.sourceUid = props.parent_uid
  globalCardDragState.cardUid = props.self.uid
  globalCardDragState.cardType = 'inTab'
}

// ------------------------
// 弹出菜单
// ------------------------
const markBtnRight = ref(true)
const isShowMenu = ref(false)
const menuStyle = ref<Record<string, string>>({})
const menuBtnRef = ref<any>(null)

function showPopMenu() {
  isShowMenu.value = !isShowMenu.value

  const btnEl = menuBtnRef.value?.$el as HTMLElement | undefined

  if (!isShowMenu.value || !btnEl) {
    return
  }

  const menuWidth = 144
  const btnRect = btnEl.getBoundingClientRect()
  const parentEl = btnEl.offsetParent as HTMLElement | null

  if (!parentEl) {
    return
  }

  const parentRect = parentEl.getBoundingClientRect()

  menuStyle.value = {
    position: 'absolute',
    top: '10px',
    left: `${btnRect.left - parentRect.left - menuWidth}px`,
  }
}

function closePopMenu() {
  isShowMenu.value = false
}

// ------------------------
// 标记逻辑
// ------------------------
const isShowMarkUICtrl = ref(true)

function markCard() {
  props.self.marked = !props.self.marked
  notifyContentChange()
}

function hideMark() {
  props.self.marked = false
  notifyContentChange()

  setTimeout(() => {
    isShowMarkUICtrl.value = false
  }, 200)

  setTimeout(() => {
    isShowMarkUICtrl.value = true
  }, 220)
}

async function updateMarkContent() {
  try {
    const value = await InputDialog.open('请输入文本', '编辑标记内容', {
      placeholder: props.self.markMessage,
      defaultValue: props.self.markMessage,
    })

    props.self.markMessage = value
    props.self.marked = true
    notifyContentChange()
  }
  catch {}
}

// ------------------------
// 拖拽数据类型判断
// ------------------------
function isContainerType(item: TabCardItem) {
  return item.type === 'folder'
}

function isDescendant(target: TabCardItem, uid: string): boolean {
  if (target.type !== 'folder') {
    return false
  }

  for (const child of target.content) {
    if (child.uid === uid) {
      return true
    }
    if (isDescendant(child, uid)) {
      return true
    }
  }

  return false
}

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

function findCardFromTree(tree: TabCardItem[], uid: string, deleteFound: boolean = false): TabCardItem | null {
  if (!Array.isArray(tree)) {
    return null
  }

  for (let i = 0; i < tree.length; i++) {
    const node = tree[i]

    if (node.uid === uid) {
      if (deleteFound) tree.splice(i, 1)
      return node
    }

    if (
      node.type === 'folder'
      &&
      Array.isArray(node.content)
      &&
      node.content.length > 0
    ) {
      const found = findCardFromTree(node.content, uid, deleteFound)

      if (found) return found
    }
  }

  return null
}

function DragCardDropInCardList() {
  console.log("[DragCardDropInCardList] globalCardDragState:", globalCardDragState)
  globalDragHoverCard.value = ''
  // Append
  if (
    globalCardDragState.cardUid === "" || // Not drag a card or
    globalCardDragState.cardUid === props.self.uid // Drop in self
  ) return

  if (globalCardDragState.cardType === 'preset') {
    const newCard = createCardByID(globalCardDragState.cardUid)

    props.self.content.push(newCard)
    notifyContentChange()
    clearGlobalDragState()
    return
  }

  if (globalCardDragState.cardType === 'inTab') {
    const currentTab = store.findTab(props.tab_key)
    const virtualCard = findCardFromTree(currentTab.content, globalCardDragState.cardUid, true)
    if (!currentTab || !virtualCard) return

    props.self.content.push(virtualCard)
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

    props.self.content.splice(dropIndex, 0, newCard)
    notifyContentChange()
    clearGlobalDragState()
    return
  }

  if (globalCardDragState.cardType === 'inTab') {
    const currentTab = store.findTab(props.tab_key)
    const virtualCard = findCardFromTree(currentTab.content, globalCardDragState.cardUid, true)
    if (!currentTab || !virtualCard) return

    // After delete origin card, we should refresh dropIndex
    if (props.self.uid === globalCardDragState.sourceUid) {
      const shouldDropIndex = props.self.content.findIndex(t => t.uid === dropOn.uid)
      if (shouldDropIndex !== -1) dropIndex = shouldDropIndex
    } 

    props.self.content.splice(dropIndex, 0, virtualCard)
    notifyContentChange()
    clearGlobalDragState()
    return
  }
}

// ------------------------
// 删除逻辑
// ------------------------
function removeCardFromTree(tree: TabCardItem[], uid: string): boolean {
  if (!Array.isArray(tree)) {
    return false
  }

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

async function removeThisCard() {
  if (isContainerType(props.self)) {
    try {
      await ConfirmDialog.confirm(
        '要删除该卡片夹吗？此操作将同时删除卡片夹里所有卡片',
        '删除确认',
        {
          confirmButtonText: '确定',
          cancelButtonText: '取消',
          type: 'warning',
        }
      )

      emit('update:delete-card', props.self.uid)
    }
    catch {}
    return
  }

  emit('update:delete-card', props.self.uid)
}

function deleteTabCardInContent(card_uid: string) {
  const idx = props.self.content.findIndex(c => c.uid === card_uid)

  if (idx !== -1) {
    props.self.content.splice(idx, 1)
    notifyContentChange()
    ElMessage({ type: 'success', message: '已删除' })
  }
}

function notifyContentChange() {
  emit('update:contentChange', props.self.uid)
}

// ------------------------
// 展开 / 收起
// ------------------------
function editTabCard() {
  props.self.expanded = !props.self.expanded
  notifyContentChange()
}

// ------------------------
// 标题修改
// ------------------------
function onMouseUpInput(e: Event) {
  const el = e.target as HTMLInputElement
  const cursorEnd = el.selectionEnd ?? 0
  el.setSelectionRange(cursorEnd, cursorEnd)
}

function onTabCardTitleChange(e: Event) {
  notifyContentChange()
  ;(e.target as HTMLInputElement).blur()
}
</script>

<style scoped>
.no-drag {
  -webkit-app-region: no-drag;
}

input,
textarea {
  user-select: none;
}

.folder-card-body {
  display: grid;
  grid-template-columns: 152px 1fr;
}

.place-holder-tag {
  color: rgba(52, 67, 64, 0.656);
  border-radius: 3px 12px 12px 3px;
  background: rgba(139, 199, 190, 0.09);
  border: 1px solid rgba(255, 255, 255, 0.25);
}

.folder-body-wrapper {
  min-height: 80px;
}

.scrollbar-demo-item {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 50px;
  margin: 10px;
  text-align: center;
  border-radius: 4px;
  background: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
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

.scale-fade-enter-active {
  animation: scaleFadeIn 0.25s cubic-bezier(0.22, 1, 0.36, 1);
}

.scale-fade-leave-active {
  animation: scaleFadeOut 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

@keyframes scaleFadeIn {
  0% {
    opacity: 0;
    transform: scale(0.9) translateY(6px);
  }
  60% {
    opacity: 1;
    transform: scale(1.03) translateY(0);
  }
  100% {
    opacity: 1;
    transform: scale(1);
  }
}

@keyframes scaleFadeOut {
  0% {
    opacity: 1;
    transform: scale(1);
  }
  100% {
    opacity: 0;
    transform: scale(0.95) translateY(6px);
  }
}
</style>