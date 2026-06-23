<template>
  <div 
    class="message-wrapper"
    :class="{ selected: is_selecting && props.msg.selected }"
    @click.stop="toggleSelectFullArea"
  >
    <div class="hover-menu-bar" v-if="!props.msg.is_editing && showHumanBubble">
      <button 
        class="menu-item"
        @click="reEditContext"
        style="transform: scaleX(0.94) scaleY(1.06);"
      >
        <svg t="1776756230407" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="9832" width="20" height="20"><path d="M720.042667 170.666667v73.142857H195.047619v536.380952h585.142857V512h73.142857v268.190476a73.142857 73.142857 0 0 1-73.142857 73.142857H195.047619a73.142857 73.142857 0 0 1-73.142857-73.142857V243.809524a73.142857 73.142857 0 0 1 73.142857-73.142857h524.995048z m156.281904 27.696762l51.541334 51.882666-392.825905 390.046476-53.101714 1.950477 1.511619-54.028191 392.874666-389.851428z" p-id="9833" fill="currentColor"></path></svg>
      </button>

      <button 
        class="menu-item"
        @click="copyContextValue"
      >
        <svg t="1776756262130" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="10157" width="20" height="20"><path d="M585.142857 365.714286a73.142857 73.142857 0 0 1 73.142857 73.142857v390.095238a73.142857 73.142857 0 0 1-73.142857 73.142857H195.047619a73.142857 73.142857 0 0 1-73.142857-73.142857V438.857143a73.142857 73.142857 0 0 1 73.142857-73.142857h390.095238z m0 73.142857H195.047619v390.095238h390.095238V438.857143z m-73.142857 219.428571v73.142857H268.190476v-73.142857h243.809524zM828.952381 121.904762a73.142857 73.142857 0 0 1 73.142857 73.142857v390.095238a73.142857 73.142857 0 0 1-73.142857 73.142857h-121.904762v-73.142857h121.904762V195.047619H438.857143v121.904762h-73.142857V195.047619a73.142857 73.142857 0 0 1 73.142857-73.142857h390.095238zM512 536.380952v73.142858H268.190476v-73.142858h243.809524z" p-id="10158" fill="currentColor"></path></svg>
      </button>
    </div>

    <div
      v-if="is_selecting && props.msg.pending === false"
      class="message-select-box"
      :class="{ checked: props.msg.selected }"
      @click.stop="toggleSelect"
    ></div>
    <div 
      class="human-message-wrapper"
      :class="{ is_selecting: is_selecting }"
      v-if="!props.msg.is_editing"
      @contextmenu.prevent="onContextMenu"
    >

      <div class="branch-switch-wrapper"
          v-if="(props.msg.pre_node && props.msg.pre_node.length > 0) || (props.msg.next_node && props.msg.next_node.length > 0)">
        <div style="height: 2px; width: 100%; background: linear-gradient(to right, transparent, var(--apix-default-light-color));"></div>
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
        <div style="height: 2px; width: 100%; background: linear-gradient(to left, transparent, var(--apix-default-light-color));"></div>
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
          class="system-instruction-bar"
          v-if="systemInstruction && systemInstruction.length > 0"
        >
          <div
            v-for="instruction in systemInstruction"
            class="instruction-bar"
            @click="showInstruction(instruction.ins)"
          >
            <svg t="1782128941029" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="9449" width="16" height="16"><path d="M874.057143 276.72381l-490.057143 490.105904-234.057143-234.081524 41.447619-41.49638 192.609524 192.609523 448.609524-448.609523 41.447619 41.49638z" fill="currentColor" p-id="9450"></path></svg>
            <span class="instruction-bar-content">{{ ''+instruction.preview }}</span>
          </div>
        </div>
        <div
          key="bubble"
          v-if="showHumanBubble"
          class="human-bubble"
          @mousedown="handleMouseDown"
          @mouseup="handleMouseUp"
        >
          <div
            v-if="activedFile && activedFile !== ''"
            class="actived-file noselect"
            :title="activedFile"
          >
            <svg t="1780037117744" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="6619" width="20" height="20"><path d="M64 254.638v176.34c0 38.128 13.504 69.901 40.511 95.319 27.007 25.418 57.986 38.128 92.936 38.128h614.808L669.277 707.404l61.957 61.957 228.766-224v-52.426L731.234 264.17l-61.957 66.723 142.979 142.979H197.447c-12.709 0-23.035-3.972-30.979-11.915-7.943-7.943-11.915-18.27-11.915-30.979v-176.34H64z" fill="currentColor" p-id="6620"></path></svg>
            <span class="actived-file-name noselect">{{ activedFile }}</span>
          </div>

          <div 
            v-if="referencedMessage && referencedMessage.content && referencedMessage.content !== ''"
            class="referenced-message noselect"
            :title="referencedMessage.content"
            @click="emit('jumpTo', referencedMessage.msg_id, referencedMessage.role)"
          >
            <svg t="1780037117744" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="6619" width="20" height="20"><path d="M64 254.638v176.34c0 38.128 13.504 69.901 40.511 95.319 27.007 25.418 57.986 38.128 92.936 38.128h614.808L669.277 707.404l61.957 61.957 228.766-224v-52.426L731.234 264.17l-61.957 66.723 142.979 142.979H197.447c-12.709 0-23.035-3.972-30.979-11.915-7.943-7.943-11.915-18.27-11.915-30.979v-176.34H64z" fill="currentColor" p-id="6620"></path></svg>
            <span class="reference-message-content noselect">{{ referencedMessage.content }}</span>
          </div>

          <div
            ref="bubbleContentRef"
            v-if="renderedContent && renderedContent !== ''"
            class="bubble-content markdown-body selectable"
            :class="{ collapsed: shouldCollapse && !isExpanded }"
            v-html="renderedContent"
          ></div>

          <div
            v-if="shouldCollapse"
            class="collapse-action"
          >
            <button
              class="collapse-btn"
              @click.stop="toggleCollapse"
            >
              <span>{{ isExpanded ? '收起' : '展开全文' }}</span>
              <svg v-if="isExpanded" t="1779348484868" class="c-icon icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="6631" width="20" height="20"><path d="M902.5 749.2l57.5-57.5-421.6-416.9h-52.7L64 691.7l57.5 57.5 388.1-392.9 392.9 392.9z" fill="currentColor" p-id="6632"></path></svg>
              <svg v-else t="1779348528205" class="e-icon icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="6844" width="20" height="20"><path d="M121.5 274.8L64 332.3l421.6 416.9h52.7l421.6-416.9-57.5-57.5-388.1 392.9-392.8-392.9z" fill="currentColor" p-id="6845"></path></svg>
            </button>
          </div>
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
        v-if="isShowSelectionBubble && globalSelection.role === 'human'"
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
import { nextTick, ref, onMounted, onBeforeUnmount, computed, watch } from 'vue'
import msgBubbleMenu from './comp/msgBubbleMenu.vue'
import { ConfirmDialog } from '../comp/confirmDialog.js'
import MarkdownIt from 'markdown-it'
import msgSelectionBubble from './comp/msgSelectionBubble.vue'
import { globalSelection } from '../../../store/globalData.js'

const emit = defineEmits<{
  edit: [id: string]
  editFinish:  [id: string, newContent: string]
  selectText: [id: string, role: string]
  selected: [id: string]
  delete: [id: string]
  quoted: [hid: string, mid: string, role: string, content: string]
  jumpTo: [id: string, role: string]
  switchToBranch: [id: string]
}>()

type UploadedFile = {
  file_name: string
  file_id: string
}

interface MessageLabel {
  content: string
  label_type: 'think' | 'content'
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
  chunks: MessageLabel[]
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
  return md.render(props.msg.chunks[0].content || '')
})

const uploadedFiles = computed<UploadedFile[]>(() => {
  return props.msg.extra?.user_meta_data?.uploaded_files ?? []
})

const systemInstruction = computed<object[]>(() => {
  const rawSystemInstruction = props.msg.extra?.system_instruction ?? []
  const SystemInstructionView = []
  for (const si of rawSystemInstruction) {
    console.log("si:", si)
    if (si.startsWith("/system-heartbeat")) SystemInstructionView.push({
      preview: "已发出自动任务",
      ins: si
    })
    if (si.startsWith("/system-cron")) SystemInstructionView.push({
      preview: "已发出定时任务",
      ins: si
    })
  }
  return SystemInstructionView
})

const referencedMessage = computed<object>(() => {
  return props.msg.extra?.referenced_message ?? {}
})

const activedFile = computed<string>(() => {
  return props.msg.extra?.active_file ?? ''
})

const showHumanBubble = computed(() => {
  return activedFile.value && activedFile.value !== '' ||
    referencedMessage.value && referencedMessage.value.content && referencedMessage.value.content !== '' ||
    renderedContent.value && renderedContent.value !== ''
  }
)


// 折叠/展开
const bubbleContentRef = ref<HTMLElement | null>(null)

const isExpanded = ref(false)
const shouldCollapse = ref(false)

const COLLAPSE_HEIGHT = 195

async function toggleCollapse() {
  const wrapper = bubbleContentRef.value

  if (!wrapper) {
    isExpanded.value = !isExpanded.value
    return
  }

  // 展开
  if (!isExpanded.value) {
    isExpanded.value = true
    return
  }

  // 收起
  isExpanded.value = false

  await nextTick()

  const rect = wrapper.getBoundingClientRect()

  const viewportTop = 0
  const viewportBottom = window.innerHeight

  // 元素完全可见
  const fullyVisible =
    rect.top >= viewportTop &&
    rect.bottom <= viewportBottom

  if (fullyVisible) return

  // 顶部超出
  if (rect.top < viewportTop) {
    wrapper.scrollIntoView({
      block: 'start',
      behavior: 'smooth',
    })
    return
  }

  // 底部超出
  if (rect.bottom > viewportBottom) {
    wrapper.scrollIntoView({
      block: 'end',
      behavior: 'smooth',
    })
  }
}

function checkNeedCollapse() {
  nextTick(() => {
    const el = bubbleContentRef.value
    if (!el) return

    shouldCollapse.value = el.scrollHeight > COLLAPSE_HEIGHT
  })
}

watch(
  () => props.msg.chunks[0].content,
  () => {
    isExpanded.value = false
    checkNeedCollapse()
  },
  { immediate: true }
)


const showInstruction = async (ins: string) => {
  await ConfirmDialog.confirm(ins, '指令详情', {
    confirmButtonText: '确定',
    type: 'info',
  })
}


// 菜单
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
  window.api?.copyToClipboard({ type: 'text', data: props.msg.chunks[0].content })
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

const reEditInputValue = ref(props.msg.chunks[0].content || '')
const wrapperRef = ref<HTMLElement | null>(null)

const handleClickOutside = (e: MouseEvent) => {
  if (wrapperRef.value && !wrapperRef.value.contains(e.target as Node)) {
    props.msg.is_editing = false
  }
}

const handleSendMessage = () => {
  if(reEditInputValue.value !== '') {
    props.msg.chunks[0].content = reEditInputValue.value
    emit("editFinish", props.msg.id, reEditInputValue.value)
    props.msg.is_editing = false
  }
}

const reSendMsg = () => {
  emit("editFinish", props.msg.id, props.msg.chunks[0].content)
  props.msg.error = false
  props.msg.is_editing = false
}

// 选区逻辑
function handleMouseDown(e: MouseEvent) {
  globalSelection.id = ''
  globalSelection.content = ''
  globalSelection.role = ''
  globalSelection.rect = null
}

function handleMouseUp(e: MouseEvent) {
  const selection = window.getSelection()

  if (!selection || selection.isCollapsed) {
    globalSelection.content = ''
    globalSelection.id = ''
    globalSelection.role = ''
    return
  }

  const text = selection.toString().trim()
  if (!text) {
    globalSelection.content = ''
    globalSelection.id = ''
    globalSelection.role = ''
    return
  }

  const range = selection.getRangeAt(0)
  const container = range.commonAncestorContainer

  const wrapper = e.currentTarget as HTMLElement

  if (!wrapper.contains(container) || props.msg.pending) {
    globalSelection.content = ''
    globalSelection.id = ''
    globalSelection.role = ''
    return
  }

  const rect = range.getBoundingClientRect()

  globalSelection.content = text
  globalSelection.id = props.msg.id
  globalSelection.role = 'human'
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
    globalSelection.role = ''
    globalSelection.rect = null
  }
}

function closeSelectionBubble() {
  window.getSelection()?.removeAllRanges()
}

function handleQuoteContent() {
  emit('quoted', props.msg.hid, props.msg.id, 'human', globalSelection.content)
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
/* ==================== 公共变量（与 AI 气泡完全统一） ==================== */
.message-wrapper {
  --msg-transition: background 0.6s var(--apix-cubic-bezier);
  --select-box-border: var(--apix-tertiary-light-color);
  --select-box-hover-border: var(--apix-border-error);
  --select-box-checked-bg: var(--apix-danger-color);
  --select-box-checked-border: var(--apix-danger-color);
  --branch-bg: var(--apix-default-light-color);
  --branch-border: var(--apix-lightest-color);
  --branch-hover-border: var(--apix-default-light-color);
  --branch-label-color: var(--apix-default-dark-color);
  --bubble-radius: var(--apix-panel-border-radius);
  --content-color: var(--apix-secondary-dark-color);
  --content-hover-color: var(--apix-default-dark-color);
}

/* ==================== 布局 ==================== */
.message-wrapper {
  width: 840px;
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 6px;
  padding: 12px 0px;
  border-radius: var(--bubble-radius);
  background: transparent;
  transition: var(--msg-transition);
}

.message-wrapper.selected {
  background: var(--apix-default-light-color);
}

/* ==================== 悬停菜单 ==================== */
.hover-menu-bar {
  opacity: 0;
  position: absolute;
  right: 14px;
  bottom: -10px;
  z-index: 999;
  display: flex;
  flex-direction: row;
  gap: 0;
}

.message-wrapper:hover .hover-menu-bar {
  opacity: 0.3;
}

.menu-item {
  display: flex;
  align-items: center;
  border: none;
  border-radius: 7px;
  background: transparent;
  color: var(--apix-default-dark-color);
  cursor: pointer;
  transition: all 0.12s var(--apix-cubic-bezier);
  padding: 0 3px;
}

.menu-item:hover {
  color: var(--apix-default-dark-color);
}

.menu-item:active {
  transform: scale(0.9);
}

/* ==================== 多选复选框 ==================== */
.message-select-box {
  z-index: 999;
  border: 2px solid var(--select-box-border);
  border-radius: 6px;
  width: 16px;
  min-width: 16px;
  margin-left: 3px;
  height: 16px;
  cursor: pointer;
  transition: border-color 0.15s ease,
              background-color 0.15s ease;
  position: relative;
}

.message-select-box:hover {
  border-color: var(--select-box-hover-border);
}

.message-select-box.checked {
  background-color: var(--select-box-checked-bg);
  border-color: var(--select-box-checked-border);
}

.message-select-box.checked::after {
  content: "";
  position: absolute;
  left: 4px;
  top: 0px;
  width: 5px;
  height: 10px;
  border: solid var(--apix-lightest-color);
  border-width: 0 2px 2px 0;
  transform: rotate(45deg);
}

/* ==================== 人类消息气泡容器 ==================== */
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

.human-message-wrapper.is_selecting {
  padding: 0px 3px 0px 0px !important;
}

/* ==================== 上传文件列表 ==================== */
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
  color: var(--apix-secondary-dark-color);
  background-color: var(--apix-panel-base-layer-background);
  padding: 3px 6px;
  border-radius: 8px 8px 3px 8px;
}

.file-icon {
  display: flex;
  align-items: center;
  justify-content: center;
}

.file-icon :deep(.icon) {
  width: 16px;
  height: 16px;
}

.file-name {
  word-break: break-all;
}

/* ==================== 人类消息气泡 ==================== */
.human-bubble {
  padding: 8px 16px;
  font-size: 16px !important;
  overflow: hidden;
  border-radius: 16px 16px 3px 16px;
  line-height: 1.6;
  word-break: break-word;
  border: 0px;
  background-color: var(--apix-default-light-color);
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.human-bubble-content-wrapper {
  max-width: 85%;
  display: flex;
  flex-direction: row;
  font-size: 16px !important;
}

.human-bubble-content-wrapper:deep(*) {
  font-size: 16px !important;
}

.send-state-tag {
  position: relative;
  margin-right: 24px;
  display: flex;
  align-items: center;
}

.send-state-tag :deep(.icon) {
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

.system-instruction-bar {
  width: 100%;
}

.instruction-bar {
  display: flex;
  flex-direction: row;
  justify-content: center;
  align-items: center;
  gap: 3px;
  padding-right: 3px;
  height: 20px;
  color: var(--apix-link-color);
}

.instruction-bar:hover {
  box-shadow: inset 0 -1px 0 0 var(--apix-link-hover);
  color: var(--apix-link-hover);
}

.instruction-bar-content {
  font-size: 14px !important;
  color: currentColor !important;
}

.bubble-content {
  color: var(--content-color);
  background-color: transparent;
  transition: color 0.2s var(--apix-cubic-bezier);
}

.bubble-content:hover {
  color: var(--content-hover-color);
}

.bubble-content.collapsed {
  max-height: 195px;
  overflow: hidden;
  position: relative;
}

.bubble-content.collapsed::after {
  content: '';
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  height: 72px;
  width: 100%;
  pointer-events: none;
  background: linear-gradient(
    to bottom,
    rgba(255, 255, 255, 0),
    var(--apix-default-light-color)
  );
}

.collapse-action {
  display: flex;
  width: 100%;
  bottom: 1px;
}

.collapse-btn {
  padding: 0;
  display: flex;
  align-items: center;
  gap: 5px;
  border: none;
  background: transparent;
  cursor: pointer;
  font-size: 15px !important;
  color: var(--apix-link-color);
  opacity: 0.6;
}

.collapse-btn:hover {
  opacity: 1;
  box-shadow: inset 0 -1px 0 0 var(--apix-link-color);
}

.c-icon {
  width: 14px;
  height: 14px;
  padding-bottom: 3px;
}

.e-icon {
  width: 14px;
  height: 14px;
  padding-top: 4px;
}

.referenced-message,
.actived-file {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0px 6px;
  border-radius: 8px;
  color: var(--apix-tertiary-dark-color);
}

.referenced-message:hover,
.actived-file:hover {
  color: var(--apix-secondary-dark-color);
}

.actived-file-name,
.reference-message-content {
  font-size: 0.85rem;
  max-width: 300px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.actived-file:deep(.icon),
.referenced-message:deep(.icon) {
  width: 12px;
  height: 12px;
  min-width: 12px;
}

/* ==================== 分支切换器（与 AI 气泡统一） ==================== */
.branch-switch-wrapper {
  opacity: 0.4;
  width: calc(840px - 34px);
  margin-bottom: 12px;
  display: grid;
  grid-template-columns: 45% 10% 45%;
  justify-content: space-between;
  align-items: center;
}

.branch-switch-wrapper:hover {
  opacity: 1;
}

.branch-switch-label-wrapper {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 4px 0px;
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
  color: var(--branch-label-color);
  min-width: 32px;
  text-align: center;
  user-select: none;
  font-variant-numeric: tabular-nums;
}

/* ==================== 编辑模式 ==================== */
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
  animation: opacityFadeIn 0.6s var(--apix-cubic-bezier);
}

.cd-input {
  border: 1.5px solid var(--apix-tertiary-light-color);
  border-radius: var(--apix-panel-border-radius);
  min-height: 160px;
  padding: 16px 16px;
  font-size: 16px;
  outline: none;
  background-color: var(--apix-panel-layer-1-background);
  color: var(--content-color);
  resize: none;
  transition: background-color 0.3s var(--apix-cubic-bezier),
    box-shadow 0.3s var(--apix-cubic-bezier);
  scrollbar-width: none;
}

.cd-input:focus {
  background-color: var(--apix-panel-layer-2-background);
  box-shadow: inset 0 0 0 1px var(--apix-tertiary-light-color);
}

.send-button {
  position: absolute;
  width: 36px;
  height: 36px;
  font-size: 20px;
  border-radius: 100px;
  background: var(--apix-primary-color);
  color: var(--apix-primary-text);
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  right: 10px;
  bottom: 10px;
  transition: 
    transform 0.35s var(--apix-cubic-bezier),
    box-shadow 0.35s var(--apix-cubic-bezier),
    background 0.35s var(--apix-cubic-bezier);
}

.send-button:hover {
  transform: scale(1.08);
  box-shadow: var(--apix-shadow-layer-1);
  background: var(--apix-primary-hover);
}

.send-button:active {
  transform: scale(0.95);
  background: var(--apix-common-button-active);
  box-shadow: var(--apix-shadow-layer-2);
}

/* ==================== 动画（与 AI 气泡统一） ==================== */
.scale-fade-enter-active {
  animation: scaleFadeIn 0.25s cubic-bezier(0.22, 1, 0.36, 1);
}
.scale-fade-leave-active {
  animation: scaleFadeOut 0.2s cubic-bezier(0.4, 0, 0.2, 1);
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

@keyframes opacityFadeIn {
  0% { opacity: 0.2; transform: scale(0.85); }
  100% { opacity: 1; transform: scale(1); }
}
</style>

<style scoped>
/* ==================== Markdown 通用表格/代码块增强 ==================== */
.markdown-body:deep(table) {
  position: relative;
  /* margin: auto; */
  /* margin-bottom: 12px; */
  /* border-radius: var(--apix-panel-border-radius) !important; */
  background-color: var(--apix-panel-layer-2-background) !important;
  /* box-shadow: inset 0 0 0 1px var(--apix-tertiary-dark-color); */
  /* border: 1px solid var(--apix-tertiary-dark-color); */
}
.markdown-body:deep(thead) {
  width: auto;
  background-color: var(--apix-default-light-color) !important;
}
.markdown-body:deep(th) {
  width: auto;
  background-color: transparent !important;
  border: 1px solid var(--apix-tertiary-light-color);
}
.markdown-body:deep(tbody) {
  width: auto !important;
  background-color: transparent !important;
}
.markdown-body:deep(tr) {
  width: auto;
  background-color: transparent !important;
}
.markdown-body:deep(td) {
  width: auto;
  background-color: transparent !important;
  border: 1px solid var(--apix-tertiary-light-color);
}

.markdown-body:deep(pre) {
  scrollbar-width: none;
  background-color: var(--apix-panel-layer-2-background);
  /* border-radius: var(--apix-panel-border-radius); */
  padding: 16px;
  /* margin-bottom: 0; */
}

.markdown-body:deep(blockquote) {
  border-left: .25em solid var(--apix-border-hover);
  color: var(--apix-tertiary-dark-color);
}

.markdown-body:deep(hr) {
  background-color: var(--apix-border-hover);
  opacity: 0.6;
}

.markdown-body:deep(h2) {
  border-bottom: 1px solid color-mix(in srgb, var(--apix-border-hover) 50%, transparent);
}
</style>