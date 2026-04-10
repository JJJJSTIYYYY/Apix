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
          <svg t="1758388695292" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="53362" width="16" height="16"><path d="M512.488 751.91c60.502 0 109.546 49.045 109.546 109.546 0 60.5-49.044 109.544-109.546 109.544-60.5 0-109.543-49.044-109.543-109.544S451.989 751.91 512.488 751.91z m0 64c-25.153 0-45.543 20.391-45.543 45.546 0 25.154 20.39 45.544 45.543 45.544 25.156 0 45.546-20.39 45.546-45.544 0-25.155-20.391-45.546-45.546-45.546zM824.75 671.704c14.937 9.446 19.39 29.212 9.944 44.15A382.792 382.792 0 0 1 715.86 834.69c-14.936 9.446-34.703 4.995-44.149-9.942-9.446-14.937-4.995-34.703 9.942-44.15a318.792 318.792 0 0 0 98.948-98.95c9.446-14.938 29.212-19.39 44.15-9.944z m-580.339 9.944a318.792 318.792 0 0 0 98.95 98.95c14.936 9.447 19.387 29.213 9.94 44.15-9.445 14.937-29.212 19.388-44.149 9.942A382.792 382.792 0 0 1 190.32 715.853c-9.445-14.937-4.994-34.703 9.944-44.149 14.937-9.445 34.703-4.994 44.148 9.944z m-80.866-278.696c60.5 0 109.544 49.046 109.544 109.546 0 60.5-49.044 109.546-109.544 109.546S54 572.998 54 512.498c0-60.5 49.045-109.546 109.545-109.546z m697.91 0c60.5 0 109.545 49.046 109.545 109.546 0 60.5-49.046 109.546-109.546 109.546-60.5 0-109.545-49.046-109.545-109.546 0-60.5 49.046-109.546 109.545-109.546z m-697.91 64c-25.153 0-45.545 20.392-45.545 45.546s20.392 45.546 45.545 45.546c25.153 0 45.544-20.392 45.544-45.546 0-25.155-20.391-45.546-45.544-45.546z m697.91 0c-25.154 0-45.546 20.392-45.546 45.546s20.392 45.546 45.545 45.546c25.154 0 45.546-20.392 45.546-45.546s-20.392-45.546-45.546-45.546zM715.858 190.31a382.786 382.786 0 0 1 118.834 118.834c9.446 14.937 4.995 34.703-9.942 44.15-14.937 9.445-34.703 4.994-44.15-9.943a318.786 318.786 0 0 0-98.947-98.95c-14.938-9.445-19.39-29.211-9.944-44.148 9.446-14.937 29.212-19.39 44.15-9.943z m-362.557 9.943c9.446 14.937 4.994 34.703-9.943 44.149a318.786 318.786 0 0 0-98.948 98.949c-9.446 14.937-29.212 19.388-44.149 9.942-14.937-9.446-19.388-29.212-9.943-44.149A382.786 382.786 0 0 1 309.153 190.31c14.938-9.446 34.704-4.994 44.15 9.943zM512.488 54c60.502 0 109.546 49.045 109.546 109.545 0 60.501-49.044 109.545-109.546 109.545-60.5 0-109.543-49.044-109.543-109.545 0-60.5 49.044-109.545 109.543-109.545z m0 64c-25.153 0-45.543 20.391-45.543 45.545 0 25.155 20.39 45.545 45.543 45.545 25.156 0 45.546-20.39 45.546-45.545 0-25.154-20.39-45.545-45.546-45.545z" p-id="53363" fill="#2d7e8c"></path></svg>
        </div>
        <input
          class="tab-title-input no-drag"
          v-model="titleInput"
          :placeholder="'循环卡片'"
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

    <!--  Loop 卡片体 -->
    <div v-if="self.showCardBody" class="loop-card-body">
      <div class="body-title">
        <div class="upload-file" style="display: grid; gap: 2px; grid-template-columns: 75% 25%;">
          <el-tag class="file-dir-tag" type="info" disable-transitions>
            {{ selectedFile }}
          </el-tag>
          <div style="display: flex; flex-direction: row; gap: 2px;">
            <button class="clear-file-dir-btn" @click="clearSelectedFile()">
              <el-icon><Loading /></el-icon>
            </button>
            <el-button class="select-file-dir-btn" type="primary" @click="selectFile()">Open</el-button>
          </div>
        </div>

        <div style="height: 6px;"></div>
        
        <div class="loop-exit-condition" style="display: grid; gap: 2px; grid-template-columns: 75% 25%;">
          <el-mention 
            class="condition-input" 
            placeholder="循环终止条件" 
            v-model="conditionInput" 
            clearable 
            ref="InputRef"
            :options="options"
            :loading="loading"
            @search="handleSearch"
            @select="(option, prefix) => replaceMentioned(option, prefix, InputRef)"
          />
          <el-input-number class="loop-times-input" v-model="loopTimes" :min="1" style="width: auto;" />
        </div>
      </div>
      <div class="inner-card-body">
        <div class="place-holder-tag" style="width: 152px;"></div>
        <div class="loop-body-wrapper" :style="{height: 'auto', overflow: 'auto', scrollbarWidth: 'none'}">
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
              循环体中{{ self?.content.length }}张卡片 | 指定参数化文件或循环终止条件
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

import { watch, ref, nextTick } from 'vue'
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
let isShowMenu = ref(false)
const mark_btn_right = ref(true)
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
// 参数化-文件选择
// ------------------------
if (!props.self.prams) {
  props.self.prams = {}; // 确保是个字典
}
if (!props.self.prams.select_file) {
  props.self.prams.select_file = "";
}
const selectedFile = ref<string>(props.self?.prams.select_file)

const selectFile = async () => {
  // 调用主进程打开文件选择对话框
  const result = await window.api.openFileDialog()
  if (!result.canceled && result.filePaths.length > 0) {
    selectedFile.value = result.filePaths[0]
    props.self.prams.select_file = selectedFile.value
    store.saveTab(props.tab_key)
  }
}
const clearSelectedFile = async () => {
  selectedFile.value = ""
  props.self.prams.select_file = selectedFile.value
  store.saveTab(props.tab_key)
}

// ------------------------
// 参数化-循环终止条件与循环次数
// ------------------------
if (!props.self.prams.exit_condition) {
  props.self.prams.exit_condition = "";
}
if (!props.self.prams.loop_times) {
  props.self.prams.loop_times = 1;
}
const conditionInput = ref<string>(props.self.prams.exit_condition)
const loopTimes = ref<number>(props.self.prams.loop_times)
const InputRef = ref<InputInstance>()
// const options = ref<[]>(store.tabs[store.findTab(props.tab_key)].varNameList)
const options = ref<MentionOption[]>([])
const loading = ref(false)

const handleSearch = (pattern: string) => {
  loading.value = true
  options.value = formatVarNameList(store.getVarNameList(props.tab_key, props.self?.uid))
  loading.value = false
}
watch(conditionInput, (newVal) => {
  props.self.prams.exit_condition = newVal
  store.saveTab(props.tab_key)
})
watch(loopTimes, (newVal) => {
  props.self.prams.loop_times = newVal
  store.saveTab(props.tab_key)
})

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

.inner-card-body {
  display: grid;
  grid-template-columns: 152px 1fr;
}

.loop-body-wrapper {
    min-height: 80px;
}

.place-holder-tag {
  color: rgba(52, 67, 64, 0.656);
  border-radius: 3px 12px 12px 3px;
  background: rgba(139, 199, 190, 0.09);
  border: 1px solid rgba(255, 255, 255, 0.25);
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

.body-title {
  height: 70px;
  padding: 6px;
  margin: 4px;
  border-radius: 8px;
    /* 弱化的玻璃背景 */
  background: rgba(255, 255, 255, 0.805);
  border: 1px solid rgba(255, 255, 255, 0.25);
}

.loop-exit-condition
.upload-file {
  position: relative;
  width: 100%;
  height: 40px;
  padding: 4px;
}
.loop-times-input:deep(*) {
  border: none;
  box-shadow: none;
}
.loop-times-input:deep(*) {
  border: none;
  box-shadow: none;
}
.loop-times-input:deep(.el-input-number__decrease), 
.loop-times-input:deep(.el-input-number__increase) {
  background-color: rgba(79, 101, 99, 0.057);
}
.loop-times-input:deep(.el-input__wrapper) {
  border: 1px solid rgba(79, 101, 99, 0.097);
  box-shadow: none;
}

.file-dir-tag {
  width: 100%;
  height: 32px;
  display: block;
  line-height: 32px;
}

.clear-file-dir-btn {
  margin-left: 3px;
  height: 32px;
  width: 32px;
  border: none;
  background-color: transparent;
}

.clear-file-dir-btn:hover {
  height: 32px;
  width: 32px;
  border: none;
  background-color: transparent;
  color: rgb(238, 108, 108);
}

.select-file-dir-btn {
  height: 32px;
  width: 100%;
  margin-left: 3px;
  border-radius: 3px;
  --el-button-hover-bg-color: #52bbb28d !important;
  --el-button-active-color: #387e788d !important;
  --el-button-border-color: #83c0ba00 !important;
  --el-button-hover-border-color: #58827e00 !important;
  --el-button-active-border-color: #83c0ba00 !important;
  --el-button-outline-color: #83c0ba8d !important;
  --el-button-bg-color: #83c0ba8d !important;
}

.select-file-dir-btn:active {
  background-color: #387e788d !important;
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
