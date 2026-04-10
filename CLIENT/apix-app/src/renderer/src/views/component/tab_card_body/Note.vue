<template>
  <div 
    class="tab-card"
    :class="{ expanded: self.expanded }"
    :style="{background: self.expanded?color+'CD':color+'58'}"
  >
    <!-- 卡片头 -->
    <div
      class="tab-card-header"
      :class="{ expanded: self.expanded }"
      :draggable="!self.expanded"
      @dragstart.stop="onTabCardDragStart($event)"
    >
      <div style="display: flex; flex-direction: row;">        
        <div style="width: fit-content; height: 16px; align-self: center;">
          <svg t="1774033814393" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="18411" width="16" height="16"><path d="M352 384a32 32 0 0 1 32-32h256a32 32 0 0 1 0 64h-256a32 32 0 0 1-32-32z m32 160h256a32 32 0 0 0 0-64h-256a32 32 0 0 0 0 64z m128 64h-128a32 32 0 0 0 0 64h128a32 32 0 0 0 0-64zM896 192v434.752A63.488 63.488 0 0 1 877.248 672L672 877.248a63.36 63.36 0 0 1-45.248 18.752H192a64 64 0 0 1-64-64V192a64 64 0 0 1 64-64h640a64 64 0 0 1 64 64zM192 832h416v-192a32 32 0 0 1 32-32h192V192H192v640z m480-160v114.784L786.752 672H672z" p-id="18412" fill="#2d7e8c"></path></svg>
        </div>
        <input
          class="tab-title-input no-drag"
          v-model="titleInput"
          :placeholder="'注记卡片'"
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
        <!-- More 按钮 -->
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

    <!--  mark 卡片体 -->
    <div v-if="self.showCardBody" class="mark-card-body">
      <div class="mark-body-wrapper" :style="{height: 'auto', overflow: 'auto', scrollbarWidth: 'none'}">
        <div
          tag="div"
          class="mark-content"
          draggable="false"
          style="display: grid; gap: 2px; grid-template-columns: 10% 90%; min-height: auto"
        >
          <el-color-picker class="color-picker" key="2" v-model="color" style="width: 50px; height: 100%;;" :predefine="predefineColors" />
          <el-mention
            v-model="textValue"
            key="1"
            type="textarea"
            :autosize="{ minRows: 2, maxRows: 10 }"
            style="width: 100%;"
            placeholder="Please input"
          />
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
}>()

import { watch, ref } from 'vue'
import { useAppCacheData } from '../../../store/app'
import { InputDialog } from '../comp/inputDialog'
import { globalState } from '../../../store/globalData.js'
import PopMenu from './comp/PopMenu.vue'

const store = useAppCacheData()

const loadAllVarName = () => {
  return [
    { label: 'No Suggestion', value: '' }
  ]
}
if (!props.self.prams) {
  props.self.prams = {}; // 确保是个字典
}
if (!props.self.prams.text) {
  props.self.prams.text = "";
}
if (!props.self.prams.color) {
  props.self.prams.color = "#ffffff";
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
// 删除右侧卡片
// ------------------------
async function removeThisCard() {
  emit("update:delete-card", props.self?.uid)
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

const textValue = ref(props.self.prams.text)
const color = ref(props.self.prams.color)

watch(textValue, (newVal) => {
  props.self.prams.text = newVal
  store.saveTab(props.tab_key)
})
watch(color, (newVal) => {
  props.self.prams.color = newVal
  store.saveTab(props.tab_key)
})

const predefineColors = ref([
  '#ff4500',
  '#ff8c00',
  '#ffd700',
  '#90ee90',
  '#00ced1',
  '#1e90ff',
  '#c71585',
  'rgba(255, 69, 0, 0.68)',
  'rgb(255, 120, 0)',
  'hsv(51, 100, 98)',
  'hsva(120, 40, 94, 0.5)',
  'hsl(181, 100%, 37%)',
  'hsla(209, 100%, 56%, 0.73)',
  '#c7158577',
])
</script>


<style scoped>
.no-drag {
  -webkit-app-region: no-drag; 
}

input, textarea {
  user-select: none;
}

.mark-body-wrapper {
  min-height: 60px;
}

.mark-content {
  /* min-height: 100%; */
  position: relative;
  border-radius: 8px;
  background: transparent;
  display: grid;
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
</style>
