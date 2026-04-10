<template>
  <div 
    class="tab-card"
    :class="{ expanded: self.expanded }"
    @dragenter.stop="onDragEnter($event)"
    @dragleave.stop="onDragLeave($event)"

  >
    <!-- 卡片头 -->
    <div
      class="tab-card-header"
      :class="{ expanded: self.expanded }"
      :draggable="!self.expanded"
      @dragstart.stop="onTabCardDragStart($event)"
    >
      <div style="display: flex; flex-direction: row;">
        <!-- <el-icon style="color: cadetblue;"> <Paperclip /> </el-icon> -->
        <div style="width: fit-content; height: 16px; align-self: center;">
          <svg t="1758388194426" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="52264" width="16" height="16"><path d="M405.79 96a32 32 0 0 1 24.256 11.128l0.322 0.381L527.483 224h347.833c40.832 0 74.014 32.76 74.674 73.432l0.01 1.235v192c0 17.673-14.327 32-32 32-17.496 0-31.713-14.042-31.996-31.471l-0.004-0.53v-192c0-5.793-4.627-10.512-10.4-10.662l-0.284-0.004H512.5a32 32 0 0 1-24.256-11.128l-0.323-0.381L390.806 160H149.684c-5.808 0-10.53 4.626-10.68 10.383l-0.004 0.284v682.666c0 5.794 4.627 10.513 10.4 10.663l0.284 0.004h320.132c17.673 0 32 14.327 32 32 0 17.496-14.042 31.713-31.471 32h-320.66c-40.833 0-74.015-32.76-74.675-73.432l-0.01-1.235V170.667c0-40.828 32.775-73.998 73.45-74.657l1.234-0.01H405.79z m427.745 499.664l0.377 0.37 106.71 106.667c12.379 12.373 12.502 32.362 0.372 44.887l-0.371 0.377-106.71 106.667c-12.5 12.494-32.761 12.49-45.256-0.01-12.369-12.374-12.488-32.355-0.362-44.877l0.372-0.377 84.069-84.035-84.07-84.034c-12.374-12.37-12.501-32.351-0.38-44.878l0.371-0.377c12.37-12.374 32.351-12.502 44.878-0.38z m-170.35 0.38c12.369 12.374 12.489 32.356 0.362 44.878l-0.372 0.377-84.07 84.034 84.07 84.035c12.375 12.37 12.503 32.351 0.38 44.877l-0.37 0.378c-12.37 12.374-32.351 12.502-44.878 0.38l-0.377-0.37-106.71-106.668c-12.379-12.372-12.502-32.361-0.372-44.886l0.371-0.378 106.71-106.666c12.5-12.495 32.761-12.49 45.256 0.009z" p-id="52265" fill="#2d7e8c"></path></svg>
        </div>
        <input
          class="tab-title-input no-drag"
          v-model="titleInput"
          :placeholder="'卡片夹'"
          @change="onTabCardTitleChange($event)"
          @keyup.enter="onTabCardTitleChange($event)"
          @mouseup="onMouseUp_input($event)"
          @focusout="onMouseUp_input($event)"
          @mousemove="onMouseUp_input($event)"
          @mouseenter="onMouseUp_input($event)"
        />
      </div>

      <transition name="scale-fade">
        <PopMenu 
          v-if="isShowMenu"
          :style="menuStyle"
          @close-menu="closePopMenu"
          @save-card="saveCardAsPredefined"
          @mark-card="markCard"
          @mark-content="updateMarkContent"
        />
      </transition>

      <el-tooltip
        v-if="isShowMark_"
        :content="markMessage"
        placement="left"
        effect="light"
        raw-content
      ><transition name="scale-fade">
        <el-button key="11" v-if="isShowMark" class="mark-btn" :class="{ mark_btn_right: mark_btn_right }" @click="hideMark"></el-button>
      </transition></el-tooltip>

      <div class="tab-card-btn-area"
        @mouseenter="mark_btn_right = false"
        @mouseleave="mark_btn_right = true"
      >
        <el-button
          ref="menuBtnRef"
          type="info"
          @click="showPopMenu"
          class="tab-card-btn-menu"
        >
          <el-icon><More /></el-icon>
        </el-button>

        <el-button
          :type="self.btnType"
          @click="editTabCard()"
          class="tab-card-btn-more"
          :class="{ tabcardbtnmoreexpanded: self?.expanded }"
        >
          <el-icon>
            <component :is="self.btnIcon" />
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

    <!--  Folder 卡片体 -->
    <div v-if="self.showCardBody" class="folder-card-body">
      <div class="place-holder-tag" style="width: 152px;"></div>
      <div class="folder-body-wrapper" :style="{height: 'auto', overflow: 'auto', scrollbarWidth: 'none'}">
        <div
          class="tab-content"
          draggable="false"
          @dragover.prevent
          @drop.stop="DragCardDropInCardList()"
          @before-leave="beforeLeave"
          @leave="leave"
          @after-leave="afterLeave"
          :style="{ minHeight: 'auto' }"
        >
          <div
            v-for="(item, index) in self?.content"
            :key="item.uid"
            class="tab-card-wrapper"
            @drop.stop="DragCardDropInCardList_insert(item, index, $event)"
            @dragover.prevent
            :draggable="!item.expanded"
          >
            <Interface 
              v-if="item.type === 'interface'" 
              :father_uid="self?.uid"
              :self="item"
              :tab_key="tab_key"
              @update:delete-card="deleteTabCardInContent"
            />
            <Database 
              v-else-if="item.type === 'database'" 
              :father_uid="self?.uid"
              :self="item"
              :tab_key="tab_key"
              @update:delete-card="deleteTabCardInContent"
            />
            <Folder
              v-else-if="item.type === 'folder'"
              :father_uid="self?.uid"
              :self="item"
              :tab_key="tab_key"
              @update:delete-card="deleteTabCardInContent"
            />
            <Note 
              v-else-if="item.type === 'note'" 
              :father_uid="self?.uid"
              :self="item"
              :tab_key="tab_key"
              @update:delete-card="deleteTabCardInContent"
            />
            <IfBlock 
              v-else-if="item.type === 'if'" 
              :father_uid="self?.uid"
              :self="item"
              :tab_key="tab_key"
              @update:delete-card="deleteTabCardInContent"
            />
            <Loop 
              v-else-if="item.type === 'loop'" 
              :father_uid="self?.uid"
              :self="item"
              :tab_key="tab_key"
              @update:delete-card="deleteTabCardInContent"
            />
            <SwitchBlock 
              v-else-if="item.type === 'switch'" 
              :father_uid="self?.uid"
              :self="item"
              :tab_key="tab_key"
              @update:delete-card="deleteTabCardInContent"
            />
          </div>

          <!-- 占位卡片 -->
          <div
            class="tab-card-bottom-line"
            :key="'bottomCard'"
            style="height: 40px; color: rgba(0,0,0,0.5); background-color: rgba(255,255,255,0.2);"
          >
            卡片夹中{{ self?.content.length }}张卡片
          </div>
        </div>
      </div>
    </div>
  </div>
</template>


<script setup lang="ts">
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
  prams: {}
  content: []
}

// ------------------------
// 参数列表
// ------------------------
const props = defineProps<{
  father_uid?: number
  self?: TabCardBase
  tab_key: string
}>()

// ------------------------
// 触发事件列表
// ------------------------
const emit = defineEmits<{
  (e: "update:delete-card", card_uid: number): void
  (e: "update:PlaceIntoFolder", card_uid: string): void
}>()

import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useAppCacheData } from '../../../store/app'
import { ConfirmDialog } from './../comp/confirmDialog.js'
import { InputDialog } from '../comp/inputDialog'
import Interface from './../tab_card_body/Interface.vue'
import Database from './../tab_card_body/Database.vue'
import Folder from './../tab_card_body/Folder.vue'
import Note from './../tab_card_body/Note.vue'
import IfBlock from './../tab_card_body/If.vue'
import Loop from './../tab_card_body/Loop.vue'
import SwitchBlock from './../tab_card_body/Switch.vue'
import { globalState } from '../../../store/globalData.js'
import PopMenu from './comp/PopMenu.vue'

function isContainerType(item) {
  return (
    item.type === "folder" ||
    item.type === "if" ||
    item.type === "loop" ||
    item.type === "switch"
  )
}

const store = useAppCacheData()

// ------------------------
// 右侧标签页里卡片的拖拽逻辑
// ------------------------
function onTabCardDragStart(event: DragEvent) {
  globalState.draggedStartCardUid_parent = props.father_uid
  globalState.draggedStartCardUid = props.self?.uid
  globalState.draggedCard = ""
  globalState.draggedTabCard = ""
  globalState.draggedTabCard = JSON.stringify(props.self)

  console.log(
    "folder-card: onTabCardDragStart: item.expended & uid: " +
      props.self.expanded +
      " & " +
      props.self.uid
  )

}

function onDragEnter(e: DragEvent) {
  console.log("folder: onDragEnter")
  if ((globalState.draggedStartCardUid === 0 && globalState.draggedCard === "") || globalState.draggedStartCardUid === props.self?.uid) {
    console.warn("folder: onDragEnter: globalState.draggedStartCardUid:" + globalState.draggedStartCardUid)
    console.warn("folder: onDragEnter: globalState.draggedCard:" + globalState.draggedCard)
    console.warn("folder: onDragEnter: props.self?.uid:" + props.self?.uid)
    return
  }
  if (isContainerType(props.self)) {
    props.self.expanded = true
    props.self.showCardBody = true
    props.self.btnType = "success"
    props.self.btnIcon = "Check"
  }
}

function onDragLeave(e: DragEvent) {
  // 关键点：判断离开时，鼠标是不是还在当前元素内部
  const current = e.currentTarget as HTMLElement
  const related = e.relatedTarget as Node | null
  if (related && current.contains(related)) {
    // 说明只是进入了子元素，不算真正离开
    return
  }

  if (isContainerType(props.self)) {
    props.self.expanded = false
    props.self.showCardBody = false
    props.self.btnType = "primary"
    props.self.btnIcon = "Postcard"
  }
}

function isDescendant(target, uid) {
  if (!target?.content) return false
  for (const child of target.content) {
    if (child.uid === uid) return true
    if (isDescendant(child, uid)) return true
  }
  return false
}

// ------------------------
// 显示弹出菜单
// ------------------------
const mark_btn_right = ref(true)
let isShowMenu = ref(false)
let menuStyle = ref({})
let menuBtnRef = ref(null)

function showPopMenu() {
  isShowMenu.value = !isShowMenu.value
  console.log("Note: showPopMenu: isShowMenu = " + isShowMenu.value)

  if (isShowMenu.value && menuBtnRef.value) {
    const rect = menuBtnRef.value.$el.getBoundingClientRect()
    const menuWidth = 144 // 你自己设定的菜单宽度
    console.log("Note: showPopMenu: rect = "+rect.left+" "+rect.top)

    const btnRect = menuBtnRef.value.$el.getBoundingClientRect()
    const parentRect = menuBtnRef.value.$el.offsetParent.getBoundingClientRect()

    // 相对父容器的坐标
    const relativeTop = btnRect.top - parentRect.top
    const relativeLeft = btnRect.left - parentRect.left

    menuStyle.value = {
      position: 'absolute',
      top: '10px',
      left: relativeLeft-menuWidth+'px',
    }
  }
}

function closePopMenu() {
  isShowMenu.value = false
  console.log("Note: closePopMenu")
}

// ------------------------
// 弹出菜单里的操作
// ------------------------
if (!props.self.prams.markIsShow) {
  props.self.prams.markIsShow = false;
}
const isShowMark = ref(props.self.prams.markIsShow)
const isShowMark_ = ref(true)

if (!props.self.prams.markMessage) {
  props.self.prams.markMessage = "已标记";
}
const markMessage = ref(props.self.prams.markMessage)

function saveCardAsPredefined() {
  
}

function markCard() {
  isShowMark.value = !isShowMark.value
  props.self.prams.markIsShow = isShowMark.value
  store.saveTab(props.tab_key)
}

function hideMark() {
  isShowMark.value = false
  props.self.prams.markIsShow = isShowMark.value
  store.saveTab(props.tab_key)
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
    }).then(value => {
      markMessage.value = value
      props.self.prams.markMessage = markMessage.value
      isShowMark.value = true
      props.self.prams.markIsShow = isShowMark.value
      store.saveTab(props.tab_key)
    }).catch(() => {
    })
  } catch {}
}

// ------------------------
// 左侧来的卡片 | 外侧卡片放置最底下时使用
// ------------------------
function DragCardDropInCardList() {
  if ((globalState.draggedStartCardUid === 0 && globalState.draggedCard === "") || globalState.draggedStartCardUid === props.self?.uid) return
  
  if (globalState.draggedCard) {
    // 未实例化的卡片放到本卡片内部
    console.log("folder-card: DragCardDropInCardList: " + globalState.draggedCard)
    const virtualCard = JSON.parse(globalState.draggedCard)
    const newCard = {
      id: virtualCard.id,
      title: virtualCard.title,
      type: virtualCard.type,
      level: virtualCard.level,
      uid: Date.now() + Math.random(),
      showCardBody: false,
      expanded: false,
      btnType: "primary",
      btnIcon: "Postcard",
      prams: {},
      content: []
    }
    props.self.content.push(newCard)
    store.saveTab(props.tab_key)
  } else if (globalState.draggedTabCard) {
    // 外侧已实例化的卡片放入此卡片内部的逻辑，先删除原位置卡片，再在当前卡片内添加卡片
    console.log("folder-card: DragCardDropInCardList: " + globalState.draggedTabCard)
    const virtualCard = JSON.parse(globalState.draggedTabCard)
    const newCard = { ...virtualCard }

    // 防止拖动卡片放入自己或自己的子孙节点
    if (newCard.uid === props.self.uid || isDescendant(newCard, props.self.uid)) {
      console.warn("不能把卡片放到自己或子孙节点内部")
      return
    }

    // 找到当前 tab
    const currentTab = store.tabs.find(t => t.tabKey === props.tab_key)
    if (!currentTab) {
      console.warn("未找到 tab:", props.tab_key)
      return
    }
    removeCardFromTree(currentTab.items, newCard.uid)
    props.self.content.push(newCard)
    store.saveTab(props.tab_key)
  }
    globalState.draggedStartCardUid_parent = 0
    globalState.draggedStartCardUid = 0
    globalState.draggedCard = ""
    globalState.draggedTabCard = ""
  }

// ------------------------
// 卡片放置在其他卡片上时使用
// ------------------------
function DragCardDropInCardList_insert(item, dropIndex, event) {
  console.log("folder-card: DragCardDropInCardList_insert: dropIndex: " + dropIndex)
  if (globalState.draggedTabCard) {
    const virtualCard = JSON.parse(globalState.draggedTabCard)
    const currentIndex = props.self?.content.findIndex(c => c.uid === virtualCard.uid)
    if (currentIndex != -1) {
      // 同一层级内拖拽
      props.self?.content.splice(currentIndex, 1) // 删除原位置
      props.self?.content.splice(dropIndex, 0, virtualCard) // 插入新位置
    } else {

      // 防止拖动卡片放入自己或自己的子孙节点
      if (newCard.uid === props.self.uid || isDescendant(newCard, props.self.uid)) {
        console.warn("不能把卡片放到自己或子孙节点内部")
        return
      }

      // 跨层级拖拽
      const currentTab = store.tabs.find(t => t.tabKey === props.tab_key)
      if (!currentTab) {
        console.warn("未找到 tab:", props.tab_key)
        return
      }
      removeCardFromTree(currentTab.items, virtualCard.uid) // 删除原位置卡片
      props.self?.content.splice(dropIndex, 0, virtualCard)// 插入到目标位置
    }
    store.saveTab(props.tab_key)
  } else if (globalState.draggedCard) {
    const virtualCard = JSON.parse(globalState.draggedCard)
    const newCard = {
      id: virtualCard.id,
      title: virtualCard.title,
      type: virtualCard.type,
      level: virtualCard.level,
      uid: Date.now() + Math.random(),
      showCardBody: false,
      expanded: false,
      btnType: "primary",
      btnIcon: "Postcard",
      prams: {},
      content: []
    }
    props.self.content.splice(dropIndex, 0, newCard)
  }
  globalState.draggedStartCardUid_parent = 0
  globalState.draggedStartCardUid = 0
  globalState.draggedCard = ""
  globalState.draggedTabCard = ""
  store.saveTab(props.tab_key)
}

// ------------------------
// 删除右侧卡片
// ------------------------
// 递归函数：从树中删除指定 uid 的卡片
function removeCardFromTree(tree: any[], uid: number): boolean {
  if (!Array.isArray(tree)) return false
  for (let i = 0; i < tree.length; i++) {
    const node = tree[i]
    if (node.uid === uid) {
      tree.splice(i, 1) // 删除
      return true
    }
    if (Array.isArray(node.content) && node.content.length > 0) {
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
        `要删除该卡片夹吗？此操作将同时删除卡片夹里所有卡片`,
        '删除确认',
        {
          confirmButtonText: '确定',
          cancelButtonText: '取消',
          type: 'warning',
        }
      )
      console.log("folder: removeThisCard: " + props.self?.uid)
      emit("update:delete-card", props.self?.uid)
    } catch {}
  } else {
    emit("update:delete-card", props.self?.uid)
  }
}

function deleteTabCardInContent(card_uid) {
  const idx = props.self.content.findIndex(c => c.uid === card_uid)
  props.self.content.splice(idx, 1)
  store.saveTab(props.tab_key)
  ElMessage({ type: 'success', message: '已删除' })
}

// ------------------------
// 编辑右侧卡片
// ------------------------
function editTabCard() {
  if (props.self.showCardBody) {
    props.self.btnType = "primary"
    props.self.btnIcon = "Postcard"
  } else {
    props.self.btnType = "success"
    props.self.btnIcon = "Check"
  }
  props.self.expanded = !props.self.expanded
  props.self.showCardBody = !props.self.showCardBody
  store.saveTab(props.tab_key)
}

// ------------------------
// 页面布局控制
// ------------------------
const titleInput = ref(props.self.title)

function onMouseUp_input(e: Event) {
  const el = e.target as HTMLInputElement
  const cursorPos = el.selectionStart   // 光标起始位置
  const cursorEnd = el.selectionEnd     // 光标结束位置
  // console.log("光标位置:", cursorPos, cursorEnd)
  el.setSelectionRange(cursorEnd, cursorEnd)
}

function onTabCardTitleChange(e: Event) {
  if (props.self) {
    props.self.title = titleInput.value
    store.saveTab(props.tab_key)
  }
  (e.target as HTMLInputElement).blur()
}

// ------------------------
// 页面动画控制
// ------------------------
const DURATION = 100
const EASE = 'linear'

// 卡片过渡动画
function beforeLeave(el) {
  el.style.boxSizing = 'border-box'
  el.style.height = el.offsetHeight + 'px'
  el.style.transition = `height ${DURATION}ms ${EASE},
                         margin ${DURATION}ms ${EASE},
                         padding ${DURATION}ms ${EASE},
                         opacity ${DURATION}ms ${EASE}`
}

function leave(el, done) {
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

function afterLeave(el) {
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

input, textarea {
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
  /* min-height: 100%; */
  position: relative;
  border-radius: 8px;
  background: transparent;
  display: flex;
  flex-direction: column;
  flex-wrap: wrap;
  margin-right: 5px;
  overflow: auto;         /* 保持可滚动 */
  scrollbar-width: none;  /* Firefox 隐藏滚动条 */
  gap: 4px;
  padding: 8px 12px;
}

/* 开启动画 */
.scale-fade-enter-active {
  animation: scaleFadeIn .25s cubic-bezier(0.22, 1, 0.36, 1); /* 弹性进入 */
}

.scale-fade-leave-active {
  animation: scaleFadeOut .2s cubic-bezier(0.4, 0, 0.2, 1);   /* 柔和离开 */
}

@keyframes scaleFadeIn {
  0% {
    opacity: 0;
    transform: scale(0.9) translateY(6px);
  }
  60% {
    opacity: 1;
    transform: scale(1.03) translateY(0); /* 稍微放大一点 */
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
    transform: scale(0.95) translateY(6px); /* 离场下沉一点 */
  }
}

.tab-card-bottom-line {
  box-sizing: border-box;
  background: rgba(255, 255, 255, 0.92);
  border-radius: 8px;
  padding: 8px 12px;
  box-shadow: 0 2px 6px rgba(0,0,0,0.1);
  height: 30px;
  /* transition: none; */
}
</style>
