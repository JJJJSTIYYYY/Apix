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
          <svg t="1758388530780" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="52705" width="16" height="16"><path d="M918 821.333c17.673 0 32 14.327 32 32 0 17.497-14.042 31.713-31.47 31.996l-0.53 0.004H661.895c-17.673 0-32-14.327-32-32 0-17.496 14.042-31.713 31.47-31.995l0.53-0.005H918zM491.153 138.898c17.674 0 32.005 14.323 32.005 31.996 0 17.496-14.038 31.715-31.467 32l-0.529 0.004-3.74 0.002-2.191 0.008-2.748 0.022-1.947 0.027-1.864 0.036-1.202 0.03-1.752 0.054-1.139 0.042-1.12 0.047-1.106 0.053-1.094 0.06-1.086 0.065-1.624 0.11-1.628 0.125-1.093 0.092-1.105 0.1-1.12 0.108-1.137 0.115c-11.58 1.206-22.27 3.497-32.066 7.128-28.962 10.736-48.425 32.186-57.072 71.63l-0.259 1.201c-11.56 54.603-38.031 110.216-73.634 160.83-8.72 12.398-17.844 24.243-27.034 35.199l218.757-0.001c17.673 0 32 14.327 32 32 0 17.496-14.042 31.713-31.47 31.996l-0.53 0.004H272.395c9.192 10.96 18.318 22.81 27.04 35.212 35.247 50.113 61.543 105.124 73.283 159.2l0.351 1.639c8.519 40.233 28.107 62.074 57.38 72.98 9.844 3.668 20.586 5.983 32.215 7.201l1.167 0.12 1.715 0.162 1.685 0.145 1.113 0.087 1.11 0.08 1.11 0.073 1.114 0.067 1.123 0.06 1.71 0.077 1.16 0.045 1.785 0.057 1.848 0.046 1.924 0.034 1.332 0.018 2.081 0.02 2.952 0.012 3.56 0.002c17.673-0.003 32.005 14.321 32.005 31.994 0 17.497-14.037 31.716-31.466 32.001l-0.529 0.005h-3.083l-2.755-0.009-2.625-0.019-2.512-0.03-1.62-0.027-1.583-0.033-1.55-0.04-0.763-0.023-1.51-0.05-1.49-0.058-1.474-0.066-1.464-0.074a236 236 0 0 1-0.73-0.04l-1.458-0.088-1.46-0.097-1.468-0.106-1.48-0.117-1.496-0.127-0.757-0.068-1.532-0.144-1.561-0.155-0.794-0.082c-16.664-1.745-32.585-5.176-47.893-10.88-48.886-18.213-83.785-56.762-97.246-117.839l-0.402-1.857c-9.596-45.324-32.41-93.259-63.37-137.278l-0.76-1.078-1.528-2.145-1.534-2.13a465.942 465.942 0 0 0-3.09-4.212l-1.552-2.08a465.375 465.375 0 0 0-8.604-11.108l-1.57-1.954-0.785-0.969-1.57-1.92-1.568-1.898a437.366 437.366 0 0 0-3.13-3.724l-1.56-1.825-0.78-0.903-1.554-1.787c-0.775-0.887-1.55-1.764-2.32-2.63l-1.54-1.72a386.1 386.1 0 0 0-0.768-0.85l-1.529-1.677a359.898 359.898 0 0 0-3.785-4.064l-1.498-1.573a321.791 321.791 0 0 0-2.962-3.052l-1.463-1.477a257.218 257.218 0 0 0-8.486-8.145l-1.358-1.232a176.273 176.273 0 0 0-5.88-5.067l-1.252-1.017-1.229-0.975c-2.638-2.069-5.118-3.842-7.405-5.292l-0.22-0.137a31.783 31.783 0 0 1-5.196-3.913l-0.124-0.116a31.784 31.784 0 0 1-6.255-8.104 31.818 31.818 0 0 1-2.699-6.67 31.834 31.834 0 0 1-1.167-8.952 31.8 31.8 0 0 1 1.046-7.772l0.012-0.043-0.012 0.043a31.787 31.787 0 0 1 3.003-7.45 31.782 31.782 0 0 1 6.105-7.8l0.121-0.113c0.09-0.084 0.181-0.168 0.273-0.25l0.078-0.069a31.676 31.676 0 0 1 4.83-3.576l-0.319 0.201c4.341-2.692 9.403-6.59 14.95-11.486l1.341-1.194a231.19 231.19 0 0 0 5.534-5.146l1.423-1.376 1.437-1.41c0.481-0.475 0.965-0.957 1.45-1.444l1.464-1.477c2.694-2.738 5.45-5.64 8.245-8.688l1.53-1.677a427.485 427.485 0 0 0 16.359-19.197l1.57-1.964c1.83-2.304 3.659-4.65 5.48-7.035l1.56-2.053a467.297 467.297 0 0 0 3.106-4.16l1.544-2.106 1.538-2.122 1.531-2.137c0.51-0.715 1.017-1.432 1.523-2.152 30.65-43.573 53.316-90.984 63.077-135.905l0.292-1.36c13.163-62.169 48.289-101.27 97.699-119.585 15.24-5.649 31.088-9.046 47.684-10.774l0.773-0.08 1.52-0.15 1.494-0.14 1.469-0.128 1.45-0.12 1.436-0.108 1.426-0.1 1.421-0.09 1.421-0.083 1.425-0.073 1.435-0.066 1.448-0.058 1.467-0.05 1.49-0.044 0.754-0.02 1.534-0.034 1.568-0.029 2.427-0.032 2.533-0.021 2.653-0.014h4.17zM918 479.992c17.673 0 32 14.327 32 32 0 17.496-14.042 31.713-31.47 31.995l-0.53 0.005H661.895c-17.673 0-32-14.327-32-32 0-17.497 14.042-31.713 31.47-31.996l0.53-0.004H918z m0-341.325c17.673 0 32 14.327 32 32 0 17.496-14.042 31.713-31.47 31.995l-0.53 0.005H661.895c-17.673 0-32-14.327-32-32 0-17.497 14.042-31.713 31.47-31.996l0.53-0.004H918z" p-id="52706" fill="#2d7e8c"></path><path d="M107 511.981a85.368 85.333 0 1 0 170.736 0 85.368 85.333 0 1 0-170.736 0Z" p-id="52707" fill="#2d7e8c"></path></svg>
        </div>
        <input
          class="tab-title-input no-drag"
          v-model="titleInput"
          :placeholder="'分支卡片'"
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

    <!--  Switch 卡片体 -->
    <div v-if="self.showCardBody" class="switch-card-body">
      <div class="body-title">
        <el-autocomplete
          v-model="monitoredVariable"
          :fetch-suggestions="querySearch"
          clearable
          class="w-50 var-name-input"
          :class="{ nameNotFound: nameNotFound }"
          placeholder="匹配值 (已提取的变量名)"
          @input="saveVarNameInput"
          @focusin="cheakVarNameInput"
          @select="handleSelect"
          @mouseup="onMouseUp_input($event)"
          @focusout="onMouseUp_input($event)"
          @mousemove="onMouseUp_input($event)"
          @mouseenter="onMouseUp_input($event)"
        />
      </div>

      <div style="height: 6px;"></div>

      <div class="if-body-wrapper" :style="{height: 'auto', overflow: 'auto', scrollbarWidth: 'none'}">
        <div
          class="tab-content"
          draggable="false"
          @dragover.prevent
          @drop.stop="DragCardDropInCardList()"
        >
          <div
            class="switch-card-grid"
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
                @keyup.enter="handleInputConfirm"
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
                  分支卡中{{ dynamicTags.length }}个分支 | 每张分支卡仅执行一个分支
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

import { watch, nextTick, ref } from 'vue'
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

if (!props.self.prams) {
  props.self.prams = {}; // 确保是个字典
}

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
  if(dynamicTags.value.length <= props.self?.content.length) {
    ElMessage({ type: 'error', message: '分支数量应大于卡片数' });
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
        ElMessage({ type: 'error', message: '分支数量应大于卡片数' });
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
      ElMessage({ type: 'error', message: '分支数量应大于卡片数' });
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
  let el = e.target as HTMLInputElement
  if (el.tagName !== 'INPUT') {
    el = el.querySelector('input') as HTMLInputElement
  }
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
// 编辑监听的变量名
// ------------------------
interface RestaurantItem {
  label: string
  value: string
  link: string
}
let nameNotFound = ref(false)
const loadAllVarName = () => {
  return [
    { label: 'No Suggestion', value: '' }
  ]
}
if (!props.self.prams.monitored_variable) {
  props.self.prams.monitored_variable = "";
}
// if (!store.tabs[store.findTab(props.tab_key)].varNameList){
//   store.tabs[store.findTab(props.tab_key)].varNameList = loadAllVarName()
// }
const monitoredVariable = ref(props.self?.prams.monitored_variable)
const restaurants = ref<RestaurantItem[]>([])
const querySearch = (queryString: string, cb: any) => {
  restaurants.value = formatVarNameList(store.getVarNameList(props.tab_key, props.self?.uid))

  const results = queryString
    ? restaurants.value.filter(createFilter(queryString))
    : restaurants.value
  // call callback function to return suggestions
  cb(results)
}
const createFilter = (queryString: string) => {
  return (restaurant: RestaurantItem) => {
    return (
      restaurant.value.toLowerCase().indexOf(queryString.toLowerCase()) === 0
    )
  }
}
const handleSelect = (item: Record<string, any>) => {
  monitoredVariable.value = item.value
  props.self.prams.monitored_variable = monitoredVariable.value
  // store.saveTab(props.tab_key)
}
const saveVarNameInput = (text) => {
  monitoredVariable.value = text
  props.self.prams.monitored_variable = text
  store.saveTab(props.tab_key)
}
function cheakVarNameInput() {
  if(!monitoredVariable.value) {
    nameNotFound.value = false
    return
  }
  const idx = restaurants.value.findIndex(i => i.value === monitoredVariable.value)
  if (idx === -1) nameNotFound.value = true
  else nameNotFound.value = false
}
watch(monitoredVariable, (newVal) => {
  if(!newVal) {
    nameNotFound.value = false
    return
  }
  const idx = restaurants.value.findIndex(i => i.value === newVal)
  if (idx === -1) nameNotFound.value = true
  else nameNotFound.value = false
})

// ------------------------
// 添加新的分支
// ------------------------
if (!props.self.prams.condition_tags) {
  props.self.prams.condition_tags = [];
}
const inputValue = ref('')
const dynamicTags = ref(props.self?.prams.condition_tags ?? [])
const inputVisible = ref(false)
const InputRef = ref<InputInstance>()
// const options = ref<[]>(store.tabs[store.findTab(props.tab_key)].varNameList)
const options = ref<MentionOption[]>([])
const loading = ref(false)

const handleSearch = (pattern: string) => {
  loading.value = true
  options.value = formatVarNameList(store.getVarNameList(props.tab_key, props.self?.uid))
  loading.value = false
}

const handleClose = (tag: string) => {
  if(dynamicTags.value.length <= props.self?.content.length) {
    ElMessage({ type: 'error', message: '分支数量应大于卡片数' });
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

.body-title {
  height: 32px;
  padding: 0px;
  margin: 4px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.347);
}

.body-title:deep(.el-input__wrapper) {
  border: 0px solid transparent !important;
}

:deep(.var-name-input.nameNotFound) {
  --el-input-text-color: rgba(247, 104, 104, 0.764);
}

.var-name-input::selection {
  background-color: transparent;
}

.tab-title-input:-webkit-autofill {
  box-shadow: 0 0 0px 1000px transparent inset !important;
  -webkit-text-fill-color: rgba(0,0,0,0.6) !important;
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

.switch-card-grid {
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
