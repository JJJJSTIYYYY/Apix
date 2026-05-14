<template>
  <div
    class="tab-card"
    :class="{ expanded: self.expanded }"
    @dragenter.stop="onDragEnter($event)"
    @dragleave.stop="onDragLeave($event)"
  >
    <!-- 卡片头 -->
    <div
      class="tab-card-header no-drag"
      :class="{ expanded: self.expanded }"
      :draggable="!self.expanded"
      @dragstart.stop="onTabCardDragStart($event)"
    >
      <div style="display: flex; flex-direction: row;">
        <div style="width: fit-content; height: 16px; align-self: center;">
          <svg t="1758388194426" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="52264" width="16" height="16"><path d="M405.79 96a32 32 0 0 1 24.256 11.128l0.322 0.381L527.483 224h347.833c40.832 0 74.014 32.76 74.674 73.432l0.01 1.235v192c0 17.673-14.327 32-32 32-17.496 0-31.713-14.042-31.996-31.471l-0.004-0.53v-192c0-5.793-4.627-10.512-10.4-10.662l-0.284-0.004H512.5a32 32 0 0 1-24.256-11.128l-0.323-0.381L390.806 160H149.684c-5.808 0-10.53 4.626-10.68 10.383l-0.004 0.284v682.666c0 5.794 4.627 10.513 10.4 10.663l0.284 0.004h320.132c17.673 0 32 14.327 32 32 0 17.496-14.042 31.713-31.471 32h-320.66c-40.833 0-74.015-32.76-74.675-73.432l-0.01-1.235V170.667c0-40.828 32.775-73.998 73.45-74.657l1.234-0.01H405.79z m427.745 499.664l0.377 0.37 106.71 106.667c12.379 12.373 12.502 32.362 0.372 44.887l-0.371 0.377-106.71 106.667c-12.5 12.494-32.761 12.49-45.256-0.01-12.369-12.374-12.488-32.355-0.362-44.877l0.372-0.377 84.069-84.035-84.07-84.034c-12.374-12.37-12.501-32.351-0.38-44.878l0.371-0.377c12.37-12.374 32.351-12.502 44.878-0.38z m-170.35 0.38c12.369 12.374 12.489 32.356 0.362 44.878l-0.372 0.377-84.07 84.034 84.07 84.035c12.375 12.37 12.503 32.351 0.38 44.877l-0.37 0.378c-12.37 12.374-32.351 12.502-44.878 0.38l-0.377-0.37-106.71-106.668c-12.379-12.372-12.502-32.361-0.372-44.886l0.371-0.378 106.71-106.666c12.5-12.495 32.761-12.49 45.256 0.009z" p-id="52265"></path></svg>
        </div>
        <input
          class="tab-title-input no-drag"
          v-model="titleInput"
          placeholder="卡片夹"
          @change="onTabCardTitleChange($event)"
          @keyup.enter="onTabCardTitleChange($event)"
          @mouseup="onMouseUp_input($event)"
          @focusout="onMouseUp_input($event)"
          @mousemove="onMouseUp_input($event)"
          @mouseenter="onMouseUp_input($event)"
        />
      </div>

      <PopMenu
        v-if="isShowMenu"
        :style="menuStyle"
        @close-menu="closePopMenu"
        @save-card="saveCardAsPredefined"
        @mark-card="markCard"
        @mark-content="updateMarkContent"
      />

      <el-tooltip
        v-if="isShowMark_"
        :content="markMessage"
        placement="left"
        effect="light"
        raw-content
      >
        <transition name="scale-fade">
          <button
            key="11"
            v-if="isShowMark"
            class="mark-btn"
            :class="{ mark_btn_right: mark_btn_right }"
            @click="hideMark"
          >
            <svg t="1778086454896" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="10188" width="20" height="20"><path d="M661.333333 426.666667a149.333333 149.333333 0 1 1-298.666666 0 149.333333 149.333333 0 0 1 298.666666 0z m-58.660571 0a90.672762 90.672762 0 1 0-181.345524 0 90.672762 90.672762 0 0 0 181.345524 0z" p-id="10189" fill="var(--apix-lightest-color)"></path><path d="M853.333333 426.666667c0 231.18019-341.333333 512-341.333333 512S170.666667 657.846857 170.666667 426.666667c0-188.513524 152.81981-341.333333 341.333333-341.333334s341.333333 152.81981 341.333333 341.333334z m-58.660571 0c0-156.111238-126.537143-282.672762-282.672762-282.672762-156.111238 0-282.672762 126.537143-282.672762 282.672762 0 44.080762 16.579048 94.98819 46.201905 149.504 29.330286 53.906286 69.193143 107.203048 110.250667 154.916571A1537.926095 1537.926095 0 0 0 512 860.598857a1537.926095 1537.926095 0 0 0 126.22019-129.511619c41.057524-47.713524 80.920381-101.010286 110.250667-154.916571 29.622857-54.51581 46.201905-105.423238 46.201905-149.504z" p-id="10190" fill="var(--apix-lightest-color)"></path></svg>
          </button>
        </transition>
      </el-tooltip>

      <div
        class="tab-card-btn-area"
        @mouseenter="mark_btn_right = false"
        @mouseleave="mark_btn_right = true"
      >
        <el-button
          ref="menuBtnRef"
          type="info"
          @click="showPopMenu"
          class="tab-card-btn-menu"
        >
          <el-icon><MoreFilled /></el-icon>
        </el-button>

        <el-button
          @click="editTabCard()"
          class="tab-card-btn-more"
          :class="{ tabcardbtnmoreexpanded: self.expanded }"
        >
          <el-icon>
            <component :is="self.expanded ? 'Check' : 'Postcard'" />
          </el-icon>
        </el-button>

        <el-button
          type="danger"
          @click="removeThisCard()"
          class="tab-card-btn-close"
        >
          <el-icon><Close /></el-icon>
        </el-button>
      </div>
    </div>

    <!-- Folder 卡片体 -->
    <div v-if="self.expanded" class="folder-card-body">
      <div class="place-holder-tag" style="width: 152px;"></div>
      <div class="folder-body-wrapper" :style="{ height: 'auto', overflow: 'auto', scrollbarWidth: 'none' }">
        <div
          class="tab-content"
          draggable="false"
          @dragover.prevent
          @drop.stop="DragCardDropInCardList()"
          :style="{ minHeight: 'auto' }"
        >
          <div
            v-for="(item, index) in self.content"
            :key="item.uid"
            class="tab-card-wrapper"
            @drop.stop="DragCardDropInCardList_insert(item, index, $event)"
            @dragover.prevent
            :draggable="!item.expanded"
          >
            <Task
              v-if="item.type === 'task'"
              :father_uid="self.uid"
              :self="item"
              :tab_key="tab_key"
              @update:delete-card="deleteTabCardInContent"
              @update:content-change="() => { emit('update:contentChange', self.uid) }"
            />

            <Script
              v-else-if="item.type === 'script'"
              :father_uid="self.uid"
              :self="item"
              :tab_key="tab_key"
              @update:delete-card="deleteTabCardInContent"
              @update:content-change="() => { emit('update:contentChange', self.uid) }"
            ></Script>

            <Folder
              v-else-if="item.type === 'folder'"
              :father_uid="self.uid"
              :self="item"
              :tab_key="tab_key"
              @update:delete-card="deleteTabCardInContent"
              @update:content-change="() => { emit('update:contentChange', self.uid) }"
            />

            <Note
              v-else-if="item.type === 'note'"
              :father_uid="self.uid"
              :self="item"
              :tab_key="tab_key"
              @update:delete-card="deleteTabCardInContent"
              @update:content-change="() => { emit('update:contentChange', self.uid) }"
            />
          </div>

          <div
            class="tab-card-bottom-line"
            :key="'bottomCard'"
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
import { More, Close } from '@element-plus/icons-vue'
import { useAppCacheData } from '../../../store/app'
import { ConfirmDialog } from './../comp/confirmDialog.js'
import { InputDialog } from '../comp/inputDialog'
import Task from './../tab_card/Task.vue'
import Script from './../tab_card/Script.vue'
import Folder from './../tab_card/Folder.vue'
import Note from './../tab_card/Note.vue'
import { globalState } from '../../../store/globalData.js'
import PopMenu from './comp/PopMenu.vue'

type CardBase = {
  id: string
  title: string
  type: string
  level: string
}

type TabCardBase = CardBase & {
  uid: number
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

const props = defineProps<{
  father_uid?: number
  self: FolderCard
  tab_key: string
}>()

const emit = defineEmits<{
  (e: 'update:delete-card', card_uid: number): void
  (e: 'update:contentChange', card_uid: number): void
}>()

const store = useAppCacheData()

function isContainerType(item: TabCardItem | FolderCard) {
  return item.type === 'folder'
}

function createCardByType(virtualCard: CardBase): TabCardItem {
  const base = {
    id: virtualCard.id,
    title: virtualCard.title,
    type: virtualCard.type,
    level: virtualCard.level,
    uid: Date.now() + Math.random(),
    expanded: false,
  }

  switch (virtualCard.type) {
    case 'task':
      return {
        ...base,
        type: 'task',
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
// 拖拽逻辑
// ------------------------
function onTabCardDragStart(event: DragEvent) {
  globalState.draggedStartCardUid_parent = props.father_uid
  globalState.draggedStartCardUid = props.self.uid
  globalState.draggedCard = ''
  globalState.draggedTabCard = JSON.stringify(props.self)
}

function onDragEnter(e: DragEvent) {
  if (
    (globalState.draggedStartCardUid === 0 && globalState.draggedCard === '') ||
    globalState.draggedStartCardUid === props.self.uid
  ) {
    return
  }
}

function onDragLeave(e: DragEvent) {
  const current = e.currentTarget as HTMLElement
  const related = e.relatedTarget as Node | null

  if (related && current.contains(related)) {
    return
  }
}

function isDescendant(target: TabCardItem, uid: number): boolean {
  if (target.type !== 'folder') return false

  for (const child of target.content) {
    if (child.uid === uid) return true
    if (isDescendant(child, uid)) return true
  }

  return false
}

// ------------------------
// 弹出菜单
// ------------------------
const mark_btn_right = ref(true)
const isShowMenu = ref(false)
const menuStyle = ref<Record<string, string>>({})
const menuBtnRef = ref()

function showPopMenu() {
  isShowMenu.value = !isShowMenu.value

  if (isShowMenu.value && menuBtnRef.value?.$el) {
    const menuWidth = 144
    const btnRect = menuBtnRef.value.$el.getBoundingClientRect()
    const parentRect = menuBtnRef.value.$el.offsetParent.getBoundingClientRect()
    const relativeLeft = btnRect.left - parentRect.left

    menuStyle.value = {
      position: 'absolute',
      top: '10px',
      left: `${relativeLeft - menuWidth}px`,
    }
  }
}

function closePopMenu() {
  isShowMenu.value = false
}

// ------------------------
// 标记逻辑
// ------------------------
const selfExt = props.self as FolderCard & {
  markIsShow?: boolean
  markMessage?: string
}

if (selfExt.markIsShow === undefined) {
  selfExt.markIsShow = false
}
if (!selfExt.markMessage) {
  selfExt.markMessage = '已标记'
}

const isShowMark = ref(selfExt.markIsShow)
const isShowMark_ = ref(true)
const markMessage = ref(selfExt.markMessage)

function saveCardAsPredefined() {
  // 预留
}

function markCard() {
  isShowMark.value = !isShowMark.value
  selfExt.markIsShow = isShowMark.value
  emit("update:contentChange", props.self.uid)
}

function hideMark() {
  isShowMark.value = false
  selfExt.markIsShow = false
  emit("update:contentChange", props.self.uid)

  setTimeout(() => {
    isShowMark_.value = false
  }, 200)

  setTimeout(() => {
    isShowMark_.value = true
  }, 220)
}

async function updateMarkContent() {
  try {
    InputDialog.open('请输入文本', '编辑 Mark 内容', {
      placeholder: markMessage.value,
      defaultValue: markMessage.value,
    })
      .then((value: string) => {
        markMessage.value = value
        selfExt.markMessage = value
        isShowMark.value = true
        selfExt.markIsShow = true
        emit("update:contentChange", props.self.uid)
      })
      .catch(() => {})
  } catch {}
}

// ------------------------
// 拖拽放入文件夹
// ------------------------
function DragCardDropInCardList() {
  if (
    (globalState.draggedStartCardUid === 0 && globalState.draggedCard === '') ||
    globalState.draggedStartCardUid === props.self.uid
  ) {
    return
  }

  if (globalState.draggedCard) {
    const virtualCard = JSON.parse(globalState.draggedCard)
    const newCard = createCardByType(virtualCard)
    props.self.content.push(newCard)
    emit("update:contentChange", props.self.uid)
  } else if (globalState.draggedTabCard) {
    const virtualCard = JSON.parse(globalState.draggedTabCard) as TabCardItem
    const newCard = { ...virtualCard }

    if (newCard.uid === props.self.uid || isDescendant(newCard, props.self.uid)) {
      console.warn('不能把卡片放到自己或子孙节点内部')
      return
    }

    const currentTab = store.tabs.find(t => t.tabKey === props.tab_key)
    if (!currentTab) {
      console.warn('未找到 tab:', props.tab_key)
      return
    }

    removeCardFromTree(currentTab.items, newCard.uid)
    props.self.content.push(newCard)
    emit("update:contentChange", props.self.uid)
  }

  globalState.draggedStartCardUid_parent = 0
  globalState.draggedStartCardUid = 0
  globalState.draggedCard = ''
  globalState.draggedTabCard = ''
}

function DragCardDropInCardList_insert(item: TabCardItem, dropIndex: number, event: DragEvent) {
  if (globalState.draggedTabCard) {
    const virtualCard = JSON.parse(globalState.draggedTabCard) as TabCardItem
    const currentIndex = props.self.content.findIndex(c => c.uid === virtualCard.uid)

    if (currentIndex !== -1) {
      props.self.content.splice(currentIndex, 1)
      props.self.content.splice(dropIndex, 0, virtualCard)
    } else {
      if (virtualCard.uid === props.self.uid || isDescendant(virtualCard, props.self.uid)) {
        console.warn('不能把卡片放到自己或子孙节点内部')
        return
      }

      const currentTab = store.tabs.find(t => t.tabKey === props.tab_key)
      if (!currentTab) {
        console.warn('未找到 tab:', props.tab_key)
        return
      }

      removeCardFromTree(currentTab.items, virtualCard.uid)
      props.self.content.splice(dropIndex, 0, virtualCard)
    }

    emit("update:contentChange", props.self.uid)
  } else if (globalState.draggedCard) {
    const virtualCard = JSON.parse(globalState.draggedCard)
    const newCard = createCardByType(virtualCard)
    props.self.content.splice(dropIndex, 0, newCard)
    emit("update:contentChange", props.self.uid)
  }

  globalState.draggedStartCardUid_parent = 0
  globalState.draggedStartCardUid = 0
  globalState.draggedCard = ''
  globalState.draggedTabCard = ''
}

// ------------------------
// 删除逻辑
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
    } catch {}
  } else {
    emit('update:delete-card', props.self.uid)
  }
}

function deleteTabCardInContent(card_uid: number) {
  const idx = props.self.content.findIndex(c => c.uid === card_uid)
  if (idx !== -1) {
    props.self.content.splice(idx, 1)
    emit("update:contentChange", props.self.uid)
    ElMessage({ type: 'success', message: '已删除' })
  }
}

// ------------------------
// 展开 / 收起
// ------------------------
function editTabCard() {
  props.self.expanded = !props.self.expanded
  emit("update:contentChange", props.self.uid)
}

// ------------------------
// 标题修改
// ------------------------
const titleInput = ref(props.self.title)

function onMouseUp_input(e: Event) {
  const el = e.target as HTMLInputElement
  const cursorEnd = el.selectionEnd ?? 0
  el.setSelectionRange(cursorEnd, cursorEnd)
}

function onTabCardTitleChange(e: Event) {
  props.self.title = titleInput.value
  emit("update:contentChange", props.self.uid)
  ;(e.target as HTMLInputElement).blur()
}

// ------------------------
// 页面动画控制
// ------------------------
const DURATION = 100
const EASE = 'linear'

function beforeLeave(el: HTMLElement) {
  el.style.boxSizing = 'border-box'
  el.style.height = el.offsetHeight + 'px'
  el.style.transition = `height ${DURATION}ms ${EASE},
                         margin ${DURATION}ms ${EASE},
                         padding ${DURATION}ms ${EASE},
                         opacity ${DURATION}ms ${EASE}`
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