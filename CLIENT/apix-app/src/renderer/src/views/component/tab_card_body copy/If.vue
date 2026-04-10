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
          <svg t="1758388745169" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="53857" width="16" height="16"><path d="M256.618 53c76.563 0 138.617 62.116 138.617 138.725 0 65.587-45.484 120.552-106.616 135.01l-0.002 111.676h309.177c110.775 0 200.772 88.979 202.561 199.407l0.027 3.353v221.518l51.98-52.03c12.49-12.503 32.751-12.513 45.254-0.022 12.378 12.365 12.512 32.347 0.394 44.877l-0.371 0.377L791.02 962.616l-0.186 0.184-0.175 0.172 0.361-0.356c-0.438 0.438-0.885 0.861-1.341 1.269l-0.133 0.116a31.82 31.82 0 0 1-8.218 5.273l-0.118 0.05a20.697 20.697 0 0 1-0.688 0.293l-0.378 0.152-0.097 0.037c-0.117 0.047-0.235 0.092-0.353 0.137l-0.103 0.038a31.808 31.808 0 0 1-8.901 1.937l-0.144 0.01c-0.137 0.01-0.273 0.017-0.41 0.025l-0.058 0.002-0.378 0.018-0.156 0.006a23.71 23.71 0 0 1-0.727 0.018 33.472 33.472 0 0 1-0.436 0.003h-0.105l-0.324-0.003 0.43 0.003a32.63 32.63 0 0 1-1.65-0.042l-0.153-0.008a31.84 31.84 0 0 1-9.398-1.965l-0.063-0.024a28.682 28.682 0 0 1-1.49-0.603l-0.097-0.043a31.85 31.85 0 0 1-8.853-5.799l-0.072-0.068a26.266 26.266 0 0 1-0.486-0.46l-0.117-0.114-0.135-0.133-0.125-0.125-106.618-106.725c-12.49-12.503-12.48-32.764 0.023-45.254 12.378-12.366 32.36-12.48 44.877-0.35l0.377 0.372 51.979 52.03V641.171c0-75.876-60.82-137.516-136.296-138.741l-2.292-0.019H288.617v360.278l51.98-52.03c12.49-12.503 32.751-12.513 45.254-0.022 12.378 12.365 12.512 32.347 0.394 44.877l-0.37 0.377-106.619 106.725c-12.374 12.387-32.373 12.51-44.9 0.372l-0.377-0.372L127.36 855.891c-12.49-12.503-12.48-32.764 0.023-45.254 12.378-12.366 32.36-12.48 44.878-0.35l0.377 0.372 51.978 52.03V326.734c-60.42-14.288-105.552-68.144-106.598-132.715l-0.019-2.294C118 115.116 180.054 53 256.618 53z m0 64C215.415 117 182 150.448 182 191.725c0 41.276 33.415 74.724 74.618 74.724 41.203 0 74.617-33.448 74.617-74.724 0-41.277-33.414-74.725-74.617-74.725z" p-id="53858" fill="#2d7e8c"></path></svg>
        </div>
        <input
          class="tab-title-input no-drag"
          v-model="titleInput"
          :placeholder="'条件卡片'"
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

    <!--  If 卡片体 -->
    <div v-if="self.showCardBody" class="if-card-body">
      <div class="if-body-wrapper" :style="{height: 'auto', overflow: 'auto', scrollbarWidth: 'none'}">
        <div
          class="tab-content"
          draggable="false"
          @dragover.prevent
          @drop.stop="DragCardDropInCardList()"
        >
          <div
            class="if-card-grid"
            @before-leave="beforeLeave"
            @leave="leave"
            @after-leave="afterLeave"
          >
            <!-- 左侧 tags -->
              <el-tag
                v-for="(tag, index) in dynamicTags"
                :key="tag"
                class="condition-tag"
                closable
                :disable-transitions="false"
                @close="handleClose(tag)"
                :style="{height: '100%', minHeight: '50px', gridColumn: 1, gridRow: index+1, overflowWrap: 'break-word', whiteSpace: 'normal', lineHeight: 1.4 }"
              >
                {{ tag }}
              </el-tag>

              <div key="none" :style="{height: '40px', gridColumn: 1, gridRow: dynamicTags.length+1,}">
              <el-mention
                v-if="inputVisible"
                ref="InputRef"
                v-model="inputValue"
                class="w-20 add-condition-tag"
                size="small"
                style="height: 40px;"
                :options="options"
                :loading="loading"
                @search="handleSearch"
                @select="(option, prefix) => replaceMentioned(option, prefix, InputRef)"
                @blur="handleInputConfirm"
              />
              <el-button
                v-else
                class="button-new-tag add-condition-tag"
                size="small"
                @click="showInput"
                style="height: 40px; width: 100%; color: rgba(0,0,0,0.6);"
              >
                + New C
              </el-button>
              </div>
              <!-- 右侧 cards -->
                <div
                  v-for="(item, index) in self?.content"
                  :key="item.uid"
                  class="tab-card-wrapper"
                  @drop.stop="DragCardDropInCardList_insert(item, index, $event)"
                  @dragover.prevent
                  :draggable="!item.expanded"
                  :style="{gridColumn: 2, gridRow: index+1,}"
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
                  class="tab-card-bottom"
                  :key="'tab-card-bottom'"
                  style="height: 40px; color: rgba(0,0,0,0.5); background-color: rgba(255,255,255,0.2); grid-column: 2; grid-row: -1;"
                >
                  条件卡中{{ dynamicTags.length }}个条件 | 所有分支条件满足即执行
                </div>
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

import { nextTick, ref } from 'vue'
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
import { formatVarNameList, globalState } from '../../../store/globalData.js'
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
    "if-card: onTabCardDragStart: item.expended & uid: " +
      props.self.expanded +
      " & " +
      props.self.uid
  )

}

function onDragEnter(e: DragEvent) {
  console.log("if: onDragEnter")
  if ((globalState.draggedStartCardUid === 0 && globalState.draggedCard === "") || globalState.draggedStartCardUid === props.self?.uid) {
    console.warn("if: onDragEnter: globalState.draggedStartCardUid:" + globalState.draggedStartCardUid)
    console.warn("if: onDragEnter: globalState.draggedCard:" + globalState.draggedCard)
    console.warn("if: onDragEnter: props.self?.uid:" + props.self?.uid)
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
  if(dynamicTags.value.length <= props.self?.content.length) {
    ElMessage({ type: 'error', message: '条件数量应大于卡片数' });
    return
  }
  if (globalState.draggedCard) {
    // 未实例化的卡片放到本卡片内部
    console.log("if-card: DragCardDropInCardList: " + globalState.draggedCard)
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
    console.log("if-card: DragCardDropInCardList: " + globalState.draggedTabCard)
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
  console.log("if-card: DragCardDropInCardList_insert: dropIndex: " + dropIndex)
  if (globalState.draggedTabCard) {
    const virtualCard = JSON.parse(globalState.draggedTabCard)
    const currentIndex = props.self?.content.findIndex(c => c.uid === virtualCard.uid)
    if (currentIndex != -1) {
      // 同一层级内拖拽
      props.self?.content.splice(currentIndex, 1) // 删除原位置
      props.self?.content.splice(dropIndex, 0, virtualCard) // 插入新位置
    } else {
      if(dynamicTags.value.length <= props.self?.content.length) {
        ElMessage({ type: 'error', message: '条件数量应大于卡片数' });
        return
      }
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
    if(dynamicTags.value.length <= props.self?.content.length) {
      ElMessage({ type: 'error', message: '条件数量应大于卡片数' });
      return
    }
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
      console.log("if: removeThisCard: " + props.self?.uid)
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
// 添加新的条件
// ------------------------
if (!props.self.prams) {
  props.self.prams = {}; // 确保是个字典
}
if (!props.self.prams.condition_tags) {
  props.self.prams.condition_tags = [];
}
const inputValue = ref('')
const dynamicTags = ref(props.self?.prams.condition_tags)
const inputVisible = ref(false)
const InputRef = ref<InputInstance>()
// const options = ref<[]>(store.tabs[store.findTab(props.tab_key)].varNameList)
const options = ref<MentionOption[]>([])
const loading = ref(false)
const mark_btn_right = ref(true)

const handleSearch = (pattern: string) => {
  loading.value = true
  options.value = formatVarNameList(store.getVarNameList(props.tab_key, props.self?.uid))
  loading.value = false
}

const handleClose = (tag: string) => {
  if(dynamicTags.value.length <= props.self?.content.length) {
    ElMessage({ type: 'error', message: '条件数量应大于卡片数' });
    return
  }
  dynamicTags.value.splice(dynamicTags.value.indexOf(tag), 1)
  store.saveTab(props.tab_key)
}

const showInput = () => {
  inputVisible.value = true
  nextTick(() => {
    InputRef.value!.input!.focus()
  })
}

const handleInputConfirm = () => {
  if (inputValue.value) {
    dynamicTags.value.push(inputValue.value)
  }
  inputVisible.value = false
  inputValue.value = ''
  store.saveTab(props.tab_key)
}

const replaceMentioned = (option: MentionOption, prefix: string, mentionComp?: any) => {
  // ⬇️ 在 nextTick 外先抓住 cursorPos
  let textarea: HTMLInputElement | HTMLTextAreaElement | null = null;
  if (mentionComp) {
    const root = (mentionComp as any).$el ?? mentionComp;
    textarea =
      root?.querySelector?.(".el-input__inner") ??
      (root?.classList?.contains?.("el-input__inner") ? root : null);

    if (!textarea) {
      textarea =
        root?.querySelector?.(".el-textarea__inner") ??
        (root?.classList?.contains?.("el-textarea__inner") ? root : null);
    }
  }
  let cursorPos = textarea?.selectionStart ?? text.length; // ✅ 提前保存 
  cursorPos = cursorPos + option.value.length

  nextTick(() => {
    if (!textarea) return;
    console.log("interface: replaceMentioned: cursorPos: " + cursorPos)
    const text = mentionComp?.$props?.modelValue ?? "";
    console.log("interface: replaceMentioned: text: " + text)
    const target = prefix + option.value;
    const beforeCursor = text.slice(0, cursorPos);
    const lastIndex = beforeCursor.lastIndexOf(target);
    if (lastIndex === -1) return;

    const newText =
      text.slice(0, lastIndex) +
      `<<${option.value}>>` +
      text.slice(lastIndex + target.length);

    mentionComp.$emit("update:modelValue", newText);

    const newCursor = lastIndex + option.value.length + 4;
    requestAnimationFrame(() => {
      textarea.selectionStart = textarea.selectionEnd = newCursor;
      textarea.focus();
    });
  });
};

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

.if-body-wrapper {
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
  flex-wrap: wrap;
  margin-right: 5px;
  overflow: auto;         /* 保持可滚动 */
  scrollbar-width: none;  /* Firefox 隐藏滚动条 */
  padding: 4px 4px;
}

.tab-card-bottom {
  position: absolute;
  bottom: 0;
  box-sizing: border-box;
  background: rgba(255, 255, 255, 0.92);
  border-radius: 8px;
  padding: 8px 12px;
  box-shadow: 0 2px 6px rgba(0,0,0,0.1);
  min-height: 40px;
  width: 100%;
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

.if-card-grid {
  width: 100%;
  height: auto;
  position: relative;
  display: grid;
  grid-template-columns: 152px 1fr;
  gap: 8px;
  padding-right: 8px;
  align-items: start;
}

.condition-tag {
  color: rgba(52, 67, 64, 0.656);
  border-radius: 3px 12px 12px 3px;
  background: rgba(139, 199, 190, 0.09);
  border: 1px solid rgba(255, 255, 255, 0.25);
}

.condition-tag:deep(.el-tag__close) {
  color: rgba(52, 67, 64, 0.656);
  transition: all 0.15s ease;
}

.condition-tag:deep(.el-tag__close:hover) {
  color: rgba(255, 255, 255, 0.774);
  background: rgba(107, 177, 166, 0.707);
}

.add-condition-tag {
  border: none;
}

.button-new-tag {
  border: none;
  background: rgba(139, 199, 190, 0.09);
  transition: all 0.25 ease;
}

.button-new-tag:hover {
  background: rgba(90, 235, 199, 0.186);
}

</style>
