<template>
  <div
    class="tab-card"
    :class="{ expanded: self.expanded }"
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
          <svg t="1774033696111" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="17196" width="16" height="16"><path d="M641.536 382.464l102.4 102.4a38.4 38.4 0 0 1 0 54.272l-102.4 102.4-54.3232-54.272 75.264-75.264-75.264-75.264 54.272-54.272zM280.064 539.136l102.4 102.4 54.3232-54.272L361.5232 512l75.264-75.264-54.272-54.272-102.4 102.4a38.4 38.4 0 0 0 0 54.272z" p-id="17197"></path><path d="M870.4 921.6H153.6a25.6 25.6 0 0 1-25.6-25.6v-768A25.6 25.6 0 0 1 153.6 102.4h513.3312a25.6 25.6 0 0 1 18.1248 7.4752l203.4688 203.4688a25.6 25.6 0 0 1 7.4752 18.1248V896a25.6 25.6 0 0 1-25.6 25.6z m-51.2-76.8V352.6656L645.7344 179.2H204.8v665.6h614.4z" p-id="17198"></path></svg>
        </div>
        <input
          class="tab-title-input no-drag"
          v-model="titleInput"
          placeholder="脚本卡"
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

    <!-- script 卡片体 -->
    <div v-if="self.expanded" class="script-card-body">
      <div class="script-body-wrapper">
        <div class="script-content">
          <div class="field-label">
            脚本内容:
          </div>
          <div class="field-value">
            <el-input
              v-model="scriptInput"
              type="textarea"
              :autosize="{ minRows: 6, maxRows: 16 }"
              placeholder="请输入脚本内容"
              @input="onScriptChange"
            />
          </div>

          <div class="field-label">
            脚本描述:
          </div>
          <div class="field-value">
            <el-input
              v-model="descriptionInput"
              type="textarea"
              :autosize="{ minRows: 3, maxRows: 10 }"
              placeholder="请输入脚本描述，包括需要执行的代码或伪代码，需要收集的运行结果等"
              @input="onDescriptionChange"
            />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { More, Close } from '@element-plus/icons-vue'
import { useAppCacheData } from '../../../store/app'
import { InputDialog } from '../comp/inputDialog'
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
  script: string
  description: string
}

const props = defineProps<{
  father_uid?: number
  self: TabCardBase
  tab_key: string
}>()

const emit = defineEmits<{
  (e: 'update:delete-card', card_uid: number): void
  (e: 'update:contentChange', card_uid: number): void
}>()

const store = useAppCacheData()

// ------------------------
// 初始化兜底
// ------------------------
if (!props.self.script) {
  props.self.script = ''
}

if (!props.self.description) {
  props.self.description = ''
}

// ------------------------
// 页面输入状态
// ------------------------
const titleInput = ref(props.self.title)
const scriptInput = ref(props.self.script)
const descriptionInput = ref(props.self.description)

// ------------------------
// 拖拽逻辑
// ------------------------
function onTabCardDragStart(event: DragEvent) {
  globalState.draggedStartCardUid_parent = props.father_uid
  globalState.draggedStartCardUid = props.self.uid
  globalState.draggedCard = ''
  globalState.draggedTabCard = JSON.stringify(props.self)
}

// ------------------------
// 标题修改
// ------------------------
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
// 卡片体字段修改
// ------------------------
function onScriptChange(value: string) {
  props.self.script = value
  emit("update:contentChange", props.self.uid)
}

function onDescriptionChange(value: string) {
  props.self.description = value
  emit("update:contentChange", props.self.uid)
}

// ------------------------
// 弹出菜单
// ------------------------
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
const mark_btn_right = ref(true)

const selfExt = props.self as TabCardBase & {
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
  emit("update:contentChange", props.self.uid)
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

.script-body-wrapper {
  min-height: 60px;
}

.script-content {
  position: relative;
  border-radius: 8px;
  background: transparent;
  margin-right: 5px;
  overflow: auto;
  scrollbar-width: none;
  padding: 8px 12px;

  display: grid;
  gap: 8px 12px;
  grid-template-columns: 100px 1fr;
  align-items: start;
}

.field-label {
  min-height: 32px;
  display: flex;
  justify-content: center;
  align-items: center;
}

.field-value {
  width: 100%;
  display: flex;
  flex-direction: row;
}

/* 开启动画 */
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