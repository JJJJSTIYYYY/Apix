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
      class="tab-card-header"
      :class="{ expanded: self.expanded }"
      :style="{ background: self.cardColor }"
    >
      <div style="display: flex; flex-direction: row;">
        <div style="width: fit-content; height: 16px; align-self: center;">
          <svg
            t="1774033814393"
            class="icon"
            viewBox="0 0 1024 1024"
            version="1.1"
            xmlns="http://www.w3.org/2000/svg"
            p-id="18411"
            width="16"
            height="16"
          >
            <path
              d="M352 384a32 32 0 0 1 32-32h256a32 32 0 0 1 0 64h-256a32 32 0 0 1-32-32z m32 160h256a32 32 0 0 0 0-64h-256a32 32 0 0 0 0 64z m128 64h-128a32 32 0 0 0 0 64h128a32 32 0 0 0 0-64zM896 192v434.752A63.488 63.488 0 0 1 877.248 672L672 877.248a63.36 63.36 0 0 1-45.248 18.752H192a64 64 0 0 1-64-64V192a64 64 0 0 1 64-64h640a64 64 0 0 1 64 64zM192 832h416v-192a32 32 0 0 1 32-32h192V192H192v640z m480-160v114.784L786.752 672H672z"
              p-id="18412"
            />
          </svg>
        </div>

        <input
          v-model="self.title"
          class="tab-title-input no-drag"
          placeholder="注记卡片"
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
        <!-- More 按钮 -->
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

    <!-- Note 卡片体 -->
    <div
      v-if="self.expanded"
      class="mark-card-body"
    >
      <div
        class="mark-body-wrapper"
        style="height: auto; overflow: auto; scrollbar-width: none;"
      >
        <div
          class="mark-content"
          draggable="false"
          style="display: grid; gap: 2px; grid-template-columns: 56px auto; min-height: auto"
        >
          <div class="field-value color-picker-wrapper">
            <el-color-picker
              v-model="self.cardColor"
              :predefine="predefineColors"
              @change="onColorChange"
            />
          </div>

          <div class="field-value">
            <el-input
              v-model="self.noteContent"
              type="textarea"
              :autosize="{ minRows: 3, maxRows: 10 }"
              placeholder="请输入注记内容"
              @input="onNoteContentChange"
            />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

import {
  MoreFilled,
  Close,
  Check,
  Postcard,
} from '@element-plus/icons-vue'

import { InputDialog } from '../comp/inputDialog'
import { 
  globalCardDragState,
  globalDragHoverCard, 
} from '../../../store/globalData.js'

import PopMenu from './comp/PopMenu.vue'

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
  marked?: boolean
  markMessage?: string
}

type NoteCardBase = TabCardBase & {
  cardColor: string
  noteContent: string
}

// ------------------------
// 参数列表
// ------------------------
const props = defineProps<{
  parent_uid?: string
  self: NoteCardBase
  tab_key: string
}>()

// ------------------------
// 触发事件列表
// ------------------------
const emit = defineEmits<{
  (e: 'update:delete-card', card_uid: string): void
  (e: 'update:contentChange', card_uid: string): void
}>()

// ------------------------
// 初始化默认值
// ------------------------
props.self.noteContent ??= ''
props.self.cardColor ??= ''
props.self.marked ??= false
props.self.markMessage ??= '已标记'

// ------------------------
// 拖拽逻辑
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
// 输入框光标修复
// ------------------------
function onMouseUpInput(e: Event) {
  const el = e.target as HTMLInputElement
  const cursorEnd = el.selectionEnd ?? 0

  el.setSelectionRange(cursorEnd, cursorEnd)
}

// ------------------------
// 标题修改
// ------------------------
function onTabCardTitleChange(e: Event) {
  emit('update:contentChange', props.self.uid)

  ;(e.target as HTMLInputElement).blur()
}

// ------------------------
// 内容修改
// ------------------------
function onNoteContentChange() {
  emit('update:contentChange', props.self.uid)
}

function onColorChange() {
  emit('update:contentChange', props.self.uid)
}

// ------------------------
// 弹出菜单
// ------------------------
const isShowMenu = ref(false)
const menuStyle = ref<Record<string, string>>({})
const menuBtnRef = ref()

function showPopMenu() {
  isShowMenu.value = !isShowMenu.value

  const btnEl = menuBtnRef.value?.$el

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
const markBtnRight = ref(true)
const isShowMarkUICtrl = ref(true)

function markCard() {
  props.self.marked = !props.self.marked

  emit('update:contentChange', props.self.uid)
}

function hideMark() {
  props.self.marked = false

  emit('update:contentChange', props.self.uid)

  setTimeout(() => {
    isShowMarkUICtrl.value = false
  }, 200)

  setTimeout(() => {
    isShowMarkUICtrl.value = true
  }, 220)
}

async function updateMarkContent() {
  try {
    const value = await InputDialog.open(
      '请输入文本',
      '编辑 Mark 内容',
      {
        placeholder: props.self.markMessage,
        defaultValue: props.self.markMessage,
      }
    )

    props.self.markMessage = value
    props.self.marked = true

    emit('update:contentChange', props.self.uid)
  }
  catch {}
}

// ------------------------
// 删除卡片
// ------------------------
function removeThisCard() {
  emit('update:delete-card', props.self.uid)
}

// ------------------------
// 展开 / 收起
// ------------------------
function editTabCard() {
  props.self.expanded = !props.self.expanded

  emit('update:contentChange', props.self.uid)
}

// ------------------------
// 预定义颜色
// ------------------------
const predefineColors = [
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
]
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

.field-value.color-picker-wrapper {

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
