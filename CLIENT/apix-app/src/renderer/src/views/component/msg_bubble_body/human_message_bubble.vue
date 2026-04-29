<template>
  <div 
    class="message-wrapper"
    :class="{ selected: is_selecting && props.msg.selected }"
    @click.stop="toggleSelectFullArea"
  >
    <div
      v-if="is_selecting && props.msg.pending === false"
      class="message-select-box"
      :class="{ checked: props.msg.selected }"
      @click.stop="toggleSelect"
    ></div>
    <div 
      class="human-message-wrapper"
      v-if="!props.msg.is_editing"
      @contextmenu.prevent="onContextMenu"
    >

      <div class="branch-switch-wrapper"
          v-if="(props.msg.pre_node && props.msg.pre_node.length > 0) || (props.msg.next_node && props.msg.next_node.length > 0)">
        <div 
          class="branch-switch-label-wrapper"
        >
          <button
            class="branch-switch-btn pre"
            :disabled="!props.msg.pre_node || props.msg.pre_node.length === 0"
            @click="handlePreNodeClick"
          >
            <svg t="1777025380440" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="1147" width="16" height="16"><path d="M412.128 512l293.28-285.248c9.312-9.056 14.592-21.6 14.592-34.752 0-26.496-21.056-48-47.008-48-12.064 0-23.68 4.736-32.416 13.248l-317.12 308.416Q304 484.544 304 512q0 27.424 19.456 46.336l317.12 308.384c8.736 8.544 20.352 13.28 32.416 13.28 25.952 0 47.008-21.504 47.008-48 0-13.12-5.28-25.696-14.592-34.752L412.16 512z" fill="#7C8394" p-id="1148"></path></svg>
          </button>
          <div class="branch-page-label">{{ (props.msg.pre_node.length ?? 0) + 1}}{{ ' / ' }}{{ (props.msg.pre_node.length ?? 0) + (props.msg.next_node.length ?? 0) + 1}}</div>
          <button
            class="branch-switch-btn next"
            :disabled="!props.msg.next_node || props.msg.next_node.length === 0"
            @click="handleNextNodeClick"
          >
            <svg t="1777025401907" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="1364" width="16" height="16"><path d="M611.872 512L318.592 226.752A48.48 48.48 0 0 1 304 192c0-26.496 21.056-48 47.008-48 12.064 0 23.68 4.736 32.416 13.248l317.12 308.416q19.456 18.88 19.456 46.336 0 27.424-19.456 46.336l-317.12 308.384a46.528 46.528 0 0 1-32.416 13.28c-25.952 0-47.008-21.504-47.008-48 0-13.12 5.28-25.696 14.592-34.752L611.84 512z" fill="#7C8394" p-id="1365"></path></svg>
          </button>
        </div>
      </div>
      
      <div
        v-if="uploadedFiles.length > 0"
        key="files"
        class="uploaded-files"
      >
        <div
          v-for="file in uploadedFiles"
          :key="file.file_id"
          class="uploaded-file-item"
        >
          <span class="file-icon"><svg t="1772617848746" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="4793" width="200" height="200"><path d="M582.69905013 107.71347886v186.46874477a94.26540064 94.26540064 0 0 0 88.90405556 94.08865163l5.3613451 0.14729014H865.4952507V761.67969266a141.39810029 141.39810029 0 0 1-141.39810028 141.39810028H299.90284958a141.39810029 141.39810029 0 0 1-141.39810028-141.39810028V249.11157915a141.39810029 141.39810029 0 0 1 141.39810028-141.39810029h282.79620055z m91.64364376 543.88190068H349.65730611a43.86286855 43.86286855 0 0 0-4.21248552 87.51953204l4.21248552 0.20620647h324.68538778a43.86286855 43.86286855 0 1 0 0-87.72573851z m0-175.45147562H349.65730611a43.86286855 43.86286855 0 0 0-4.21248552 87.54898949l4.21248552 0.17674763h324.68538778a43.86286855 43.86286855 0 1 0 0-87.72573712z m23.21285525-360.56515571c9.72111939 0 19.08874354 3.82953142 26.04081587 10.66377248l63.12836112 62.15624916 63.09890225 62.12679031a36.29217952 36.29217952 0 0 1-25.45165804 62.12679031H704.65491163a44.18690634 44.18690634 0 0 1-44.18690633-44.18690634v-115.7696946c0-20.50272455 16.61427678-37.11700133 37.11700131-37.11700132z" fill="#666666" p-id="4794"></path></svg></span>
          <span class="file-name">{{ file.file_name }}</span>
        </div>
      </div>

      <div class="human-bubble-content-wrapper">
        <div class="send-state-tag">
          <svg t="1772620030116" v-if="msg.error" @click="reSendMsg" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="5818" width="200" height="200"><path d="M512 0C229.205333 0 0 229.205333 0 512s229.205333 512 512 512 512-229.205333 512-512S794.794667 0 512 0z m0 796.458667A56.917333 56.917333 0 1 1 511.957333 682.666667 56.917333 56.917333 0 0 1 512 796.458667z m54.186667-227.797334h0.128a60.501333 60.501333 0 0 1-53.802667 55.893334c2.048 0.256 3.882667 1.152 5.973333 1.152h-11.818666c2.048 0 3.84-0.981333 5.845333-1.109334a59.093333 59.093333 0 0 1-53.162667-55.893333l-13.056-284.16a54.314667 54.314667 0 0 1 54.613334-57.045333h26.282666a52.992 52.992 0 0 1 54.186667 57.002666l-15.146667 284.16z" fill="#d81e06" p-id="5819"></path></svg>
          <svg v-else-if="msg.pending" t="1772618878456" class="icon rotate-icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="4818" width="200" height="200"><path d="M469.333333 85.333333m42.666667 0l0 0q42.666667 0 42.666667 42.666667l0 128q0 42.666667-42.666667 42.666667l0 0q-42.666667 0-42.666667-42.666667l0-128q0-42.666667 42.666667-42.666667Z" fill="#000000" opacity=".8" p-id="4819"></path><path d="M469.333333 725.333333m42.666667 0l0 0q42.666667 0 42.666667 42.666667l0 128q0 42.666667-42.666667 42.666667l0 0q-42.666667 0-42.666667-42.666667l0-128q0-42.666667 42.666667-42.666667Z" fill="#000000" opacity=".4" p-id="4820"></path><path d="M938.666667 469.333333m0 42.666667l0 0q0 42.666667-42.666667 42.666667l-128 0q-42.666667 0-42.666667-42.666667l0 0q0-42.666667 42.666667-42.666667l128 0q42.666667 0 42.666667 42.666667Z" fill="#000000" opacity=".2" p-id="4821"></path><path d="M298.666667 469.333333m0 42.666667l0 0q0 42.666667-42.666667 42.666667l-128 0q-42.666667 0-42.666667-42.666667l0 0q0-42.666667 42.666667-42.666667l128 0q42.666667 0 42.666667 42.666667Z" fill="#000000" opacity=".6" p-id="4822"></path><path d="M783.530667 180.138667m30.169889 30.169889l0 0q30.169889 30.169889 0 60.339779l-90.509668 90.509668q-30.169889 30.169889-60.339779 0l0 0q-30.169889-30.169889 0-60.339779l90.509668-90.509668q30.169889-30.169889 60.339779 0Z" fill="#000000" opacity=".1" p-id="4823"></path><path d="M330.965333 632.661333m30.16989 30.16989l0 0q30.169889 30.169889 0 60.339778l-90.509668 90.509668q-30.169889 30.169889-60.339779 0l0 0q-30.169889-30.169889 0-60.339778l90.509668-90.509668q30.169889-30.169889 60.339779 0Z" fill="#000000" opacity=".5" p-id="4824"></path><path d="M843.861333 783.530667m-30.169889 30.169889l0 0q-30.169889 30.169889-60.339779 0l-90.509668-90.509668q-30.169889-30.169889 0-60.339779l0 0q30.169889-30.169889 60.339779 0l90.509668 90.509668q30.169889 30.169889 0 60.339779Z" fill="#000000" opacity=".3" p-id="4825"></path><path d="M391.338667 330.965333m-30.16989 30.16989l0 0q-30.169889 30.169889-60.339778 0l-90.509668-90.509668q-30.169889-30.169889 0-60.339779l0 0q30.169889-30.169889 60.339778 0l90.509668 90.509668q30.169889 30.169889 0 60.339779Z" fill="#000000" opacity=".7" p-id="4826"></path></svg>

        </div>
        <div
          key="bubble"
          class="human-bubble selectable"
          @mousedown="handleMouseDown"
          @mouseup="handleMouseUp"
        >
          <div class="bubble-content markdown-body" v-html="renderedContent"></div>
        </div>
      </div>

      <transition name="scale-fade">
        <msgBubbleMenu 
          v-if="isShowMenu"
          ref="menuRef"
          type="human"
          :style="menuStyle"
          @close-menu="closePopMenu"
          @copy-value="copyContextValue"
          @re-edit="reEditContext"
          @select-text="selectText"
          @delete-item="deleteItem"
          @click.stop
        />
      </transition>

      <msgSelectionBubble
        v-if="isShowSelectionBubble"
        :style="{
          left: bubblePosition.x + 'px',
          top: bubblePosition.y + 'px'
        }"
        @close-bubble="closeSelectionBubble"
        @copy-value=""
        @quote-content="handleQuoteContent"
      />
    </div>

    <div 
      v-else
      class="edit-message-wrapper"
      ref="wrapperRef"
    >
      <div 
        class="edit-message-box"
      >
        <textarea
          ref="reEditInput"
          v-model="reEditInputValue"
          class="cd-input"
          :placeholder="'编辑消息内容...'"
        >
        </textarea>
        <button class="send-button" type="primary" @click="handleSendMessage">
          <svg t="1777266449849" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="9749" width="24" height="24"><path class="confirm-icon-path" d="M512 76.8C271.36 76.8 76.8 271.36 76.8 512s194.56 435.2 435.2 435.2 435.2-194.56 435.2-435.2S752.64 76.8 512 76.8z m0 768c-184.32 0-332.8-148.48-332.8-332.8S327.68 179.2 512 179.2s332.8 148.48 332.8 332.8-148.48 332.8-332.8 332.8z" p-id="9750" fill="#ffffff"></path></svg>
        </button>
      </div>
    </div>
  </div>
</template>


<script setup lang="ts">
import { nextTick, ref, onMounted, onBeforeUnmount, computed } from 'vue'
import msgBubbleMenu from './comp/msgBubbleMenu.vue'
import MarkdownIt from 'markdown-it'
import msgSelectionBubble from './comp/msgSelectionBubble.vue'
import { globalSelection } from '../../../store/globalData.js'

const emit = defineEmits<{
  edit: [id: string]
  editFinish:  [id: string, newContent: string]
  selectText: [id: string, role: string]
  selected: [id: string]
  delete: [id: string]
  quoted: [hid: string, content: string]
  switchToBranch: [id: string]
}>()

type UploadedFile = {
  file_name: string
  file_id: string
}

type msgBubData = {
  id: string
  cid: string
  hid: string
  node_id?: number
  parent_id?: number
  pre_node?: str[]
  next_node?: str[]
  role: 'human'
  content: string
  extra: any
  pending?: boolean
  error?: boolean
  selected?: boolean
  is_editing?: boolean
}
const props = defineProps<{
  msg: msgBubData
  is_selecting?: boolean
}>()

const md = new MarkdownIt({
  breaks: true,
  linkify: true,
})

const renderedContent = computed(() => {
  return md.render(props.msg.content || '')
})

const uploadedFiles = computed<UploadedFile[]>(() => {
  return props.msg.extra?.user_meta_data?.uploaded_files ?? []
})

const isShowMenu = ref(false)
const menuStyle = ref<Record<string, string>>({})
const menuRef = ref<any>(null)
const menuWidthGuess = 144
const menuHeightGuess = 120

function toggleSelectFullArea() {
  if (props.is_selecting && props.msg.pending === false) {
    toggleSelect()
  }
}

function toggleSelect() {
  props.msg.selected = !props.msg.selected
  if (props.msg.selected) emit("selected", props.msg.id, )
}

function handlePreNodeClick() {
  emit("switchToBranch", props.msg.pre_node?.at(-1))
}

function handleNextNodeClick() {
  emit("switchToBranch", props.msg.next_node?.at(0))
}

function onContextMenu(e: MouseEvent) {
  showPopMenu(e.clientX, e.clientY)
}

function showPopMenu(position_x: number, position_y: number) {
  if (props.is_selecting) return
  isShowMenu.value = true

  menuStyle.value = {
    position: 'fixed',
    top: `${position_y}px`,
    left: `${position_x}px`,
  }

  nextTick(() => {
    const menuEl = menuRef.value?.$el || menuRef.value
    const viewportWidth = window.innerWidth
    const viewportHeight = window.innerHeight

    const realW = menuEl?.offsetWidth ?? menuWidthGuess
    const realH = menuEl?.offsetHeight ?? menuHeightGuess

    let left = position_x
    let top = position_y

    if (left + realW > viewportWidth) left = position_x - realW
    if (top + realH > viewportHeight) top = position_y - realH

    left = Math.min(Math.max(8, left), viewportWidth - realW - 8)
    top = Math.min(Math.max(8, top), viewportHeight - realH - 8)

    menuStyle.value = {
      position: 'fixed',
      top: `${top}px`,
      left: `${left}px`,
      zIndex: '1000',
    }
  })
}

function closePopMenu() {
  isShowMenu.value = false
}

function copyContextValue() {
  // Copy original text, not rendered HTML
  window.api?.copyToClipboard({ type: 'text', data: props.msg.content })
}

const newContext = ref("")
function reEditContext() {
  props.msg.is_editing = true
  emit("edit", props.msg.id)
}

function selectText() {
  emit("selectText", props.msg.id, 'human')
}

function deleteItem() {
  emit("delete", props.msg.id, )
}

// function onDocumentClick(e: MouseEvent) {
//   const menuEl = menuRef.value?.$el || menuRef.value
//   if (!menuEl) return
//   if (menuEl === e.target || menuEl.contains(e.target as Node)) return
//   closePopMenu()
// }

function onWindowResize() {
  closePopMenu()
}

const reEditInputValue = ref(props.msg.content || '')
const wrapperRef = ref<HTMLElement | null>(null)

const handleClickOutside = (e: MouseEvent) => {
  if (wrapperRef.value && !wrapperRef.value.contains(e.target as Node)) {
    props.msg.is_editing = false
  }
}

const handleSendMessage = () => {
  if(reEditInputValue.value !== '') {
    props.msg.content = reEditInputValue.value
    emit("editFinish", props.msg.id, reEditInputValue.value)
    props.msg.is_editing = false
  }
}

const reSendMsg = () => {
  emit("editFinish", props.msg.id, props.msg.content)
  props.msg.is_editing = false
}

// 选区逻辑
function handleMouseDown(e: MouseEvent) {
  globalSelection.id = ''
  globalSelection.content = ''
  globalSelection.rect = null
}

function handleMouseUp(e: MouseEvent) {
  const selection = window.getSelection()

  if (!selection || selection.isCollapsed) {
    globalSelection.content = ''
    globalSelection.id = ''
    return
  }

  const text = selection.toString().trim()
  if (!text) {
    globalSelection.content = ''
    globalSelection.id = ''
    return
  }

  const range = selection.getRangeAt(0)
  const container = range.commonAncestorContainer

  const wrapper = e.currentTarget as HTMLElement

  if (!wrapper.contains(container) || props.msg.pending) {
    globalSelection.content = ''
    globalSelection.id = ''
    return
  }

  const rect = range.getBoundingClientRect()

  globalSelection.content = text
  globalSelection.id = props.msg.id
  globalSelection.rect = rect
}

const isShowSelectionBubble = computed(() => {
  return (
    Boolean(globalSelection.content) &&
    globalSelection.id === props.msg.id
  )
})

const bubblePosition = computed(() => {
  const rect = globalSelection.rect
  if (!rect) return { x: 0, y: 0 }

  return {
    x: rect.left + rect.width / 2,
    y: rect.top - 16,
  }
})

function handleSelectionChange() {
  const selection = window.getSelection()

  // 如果拖动过程中被清空
  if (!selection || selection.isCollapsed) {
    globalSelection.content = ''
    globalSelection.id = ''
    globalSelection.rect = null
  }
}

function closeSelectionBubble() {
  window.getSelection()?.removeAllRanges()
}

function handleQuoteContent() {

  emit("quoted", props.msg.hid, globalSelection.content)
}

onMounted(() => {
  // document.addEventListener('click', onDocumentClick, true)
  document.addEventListener('selectionchange', handleSelectionChange)
  window.addEventListener('mousedown', handleClickOutside)
  window.addEventListener('resize', onWindowResize)
})

onBeforeUnmount(() => {
  // document.removeEventListener('click', onDocumentClick, true)
  document.removeEventListener('selectionchange', handleSelectionChange)
  window.removeEventListener('mousedown', handleClickOutside)
  window.removeEventListener('resize', onWindowResize)
})
</script>


<style scoped>
.message-wrapper {
  width: 100%;
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 6px;
  padding: 12px;
  border-radius: 18px;
  align-items: center;
  background: transparent;
  transition: background 0.6s cubic-bezier(0.23, 1, 0.32, 1);
}

.message-wrapper.selected {
  background: #e3dfdf7a;
}

.message-select-box {
  z-index: 999;
  border: 2px solid #bababa;
  border-radius: 6px;
  width: 16px;
  height: 16px;
  cursor: pointer;
  transition: all 0.15s ease;
  position: relative;
}

.message-select-box:hover {
  border-color: rgb(255, 131, 131);
}

.message-select-box.checked {
  background-color: #f35050;
  border-color: #ea4444;
}

.message-select-box.checked::after {
  content: "";
  position: absolute;
  left: 4px;
  top: 0px;
  width: 5px;
  height: 10px;
  border: solid white;
  border-width: 0 2px 2px 0;
  transform: rotate(45deg);
}

.human-bubble {
  padding: 8px 16px;
  font-size: 16px;
  overflow: hidden;
  border-radius: 16px 16px 6px 16px;
  line-height: 1.6;
  word-break: break-word;
  border: 1px solid #d2eeeda2;
  border-width: 0px 3px 2px 0px;
  transition: all 0.25s ease;
  background: #c0d1d2c9;
  color: #000000dc;
}

.human-bubble-content-wrapper {
  max-width: 85%;
  display: flex;
  flex-direction: row;
  /* animation: opacityFadeIn .5s cubic-bezier(0.22, 1, 0.36, 1); */
}

.send-state-tag {
  position: relative;
  margin-right: 24px;
  display: flex;
  align-items: center;
}

.send-state-tag:deep(.icon) {
  position: absolute;
  bottom: 1px;
  width: 16px;
  height: 16px;
}

.rotate-icon {
  animation: rotate 1s linear infinite;
}
@keyframes rotate {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.bubble-content {
  background-color: transparent;
}

.scale-fade-enter-active {
  animation: scaleFadeIn .25s cubic-bezier(0.22, 1, 0.36, 1);
}
.scale-fade-leave-active {
  animation: scaleFadeOut .2s cubic-bezier(0.4, 0, 0.2, 1);
}
@keyframes scaleFadeIn {
  0% { opacity: 0; transform: scale(0.9) translateY(6px); }
  60% { opacity: 1; transform: scale(1.03) translateY(0); }
  100% { opacity: 1; transform: scale(1); }
}
@keyframes scaleFadeOut {
  0% { opacity: 1; transform: scale(1); }
  100% { opacity: 0; transform: scale(0.95) translateY(6px); }
}

.human-message-wrapper {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  width: 100%;
  max-width: 100%;
  padding: 0px 16px;
  gap: 12px;
}

.uploaded-files {
  margin-top: 6px;
  padding: 6px 10px;
  max-width: 80%;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.uploaded-file-item {
  width: fit-content;
  display: flex;
  align-items: center;
  align-self: end;
  gap: 6px;
  font-size: 0.85rem;
  color: rgba(0, 0, 0, 0.617);
  background-color: #cad3d45a;
  padding: 3px 6px;
  border-radius: 8px 8px 3px 8px;
}

.file-icon {
  display: flex;
  align-items: center;
  justify-content: center;
}

.file-icon:deep(.icon) {
  width: 16px;
  height: 16px;
}

.file-name {
  word-break: break-all;
}

.branch-switch-wrapper {
  opacity: 0.4;
  width: 100%;
  background-color: #d0dedc;
  border-radius: 24px;
  border: 1px solid #7c98957e;
}

.branch-switch-wrapper:hover {
  opacity: 1;
}

.branch-switch-label-wrapper {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 4px;
  border-radius: 20px;
  margin: 0px auto;
  width: fit-content;
}

.branch-switch-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 16px;
  border: none;
  border-radius: 50%;
  background: transparent;
  cursor: pointer;
  padding: 0;
}

.branch-switch-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.branch-page-label {
  font-size: 14px;
  font-weight: 500;
  color: #606266;
  min-width: 32px;
  text-align: center;
  user-select: none;
  font-variant-numeric: tabular-nums;
}

.edit-message-wrapper {
  position: relative;
  display: flex;
  justify-content: center;
  min-width: 100%;
  max-width: 100%;
  min-height: 160px;
}

.edit-message-box {
  position: relative;
  display: flex;
  flex-direction: column;
  width: 92%;
  min-height: 160px;
  animation: opacityFadeIn .6s cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes opacityFadeIn {
  0% { 
    opacity: 0.3; 
    transform: scale(0.8); 
  }
  100% { 
    opacity: 1; 
    transform: scale(1); 
  }
}

.cd-input {
  border: 1.5px solid #909d9dc9;
  border-radius: 32px;
  min-height: 160px;
  border-radius: 32px;
  padding: 16px 16px;
  font-size: 16px;
  outline: none;
  color: #2f3d3cdc;
  background-color: rgba(255, 255, 255, 0.199);
  resize: none;
  transition: all 0.3s ease;
  scrollbar-width: none;
}

.cd-input:focus {
  background-color: rgba(255, 255, 255, 0.414);
  box-shadow: inset 0 0 0 1px #909d9dc9;
}

.send-button {
  position: absolute;
  width: 36px;
  height: 36px;
  font-size: 20px;
  border-radius: 100px;
  background: #60aca9;
  color: whitesmoke;
  border: none;
  cursor: pointer;

  display: flex;
  align-items: center;
  right: 12px;
  bottom: 12px;

  transition: all 0.35s ease;
}

.send-button:hover {
  transform: scale(1.08);
  box-shadow: 0 4px 14px rgb(255, 255, 255);
  background: #60aca9;
}

/* 点击效果：轻微缩小 + 暗色反馈 */
.send-button:active {
  transform: scale(0.95);
  background: #519794;
  box-shadow: 0 2px 8px rgba(255, 255, 255, 0.908);
}
</style>

<style scoped>
.markdown-body:deep(table) {
  border-radius: 12px !important;
  background-color: rgba(255, 255, 255, 0.431) !important;
  box-shadow: 
    inset 0 1px 0 1px var(--borderColor-default),  /* 顶部边框 */
    inset 1px 0 0 1px var(--borderColor-default), /* 右侧边框 */
    inset 0 -1px 0 1px var(--borderColor-default), /* 底部边框 */
    inset -1px 0 0 1px var(--borderColor-default); /* 左侧边框 */
}
.markdown-body:deep(thead) {
  background-color: rgba(178, 194, 199, 0.256) !important;
}
.markdown-body:deep(th) {
  background-color: rgba(255, 255, 255, 0) !important;
}
.markdown-body:deep(tbody) {
  background-color: rgba(255, 255, 255, 0) !important;
}
.markdown-body:deep(tr) {
  background-color: rgba(255, 255, 255, 0) !important;
}
.markdown-body:deep(td) {
  background-color: rgba(234, 234, 234, 0) !important;
}

.markdown-body:deep(pre) {
  padding: 0px;
  margin-bottom: 0px;
  margin-top: 14px;
  margin-bottom: 14px;
  scrollbar-width: none;
  border-radius: 24px !important;
}

.markdown-body:deep(blockquote) {
  margin: 16px 3px;
  padding: 0 1em;
  color: #59636eb6;
  border-left: .2em solid #5490914b;
}
</style>