<template>
  <div
    class="human-message-wrapper"
  >
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
        <svg t="1772620030116" v-if="msg.error" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="5818" width="200" height="200"><path d="M512 0C229.205333 0 0 229.205333 0 512s229.205333 512 512 512 512-229.205333 512-512S794.794667 0 512 0z m0 796.458667A56.917333 56.917333 0 1 1 511.957333 682.666667 56.917333 56.917333 0 0 1 512 796.458667z m54.186667-227.797334h0.128a60.501333 60.501333 0 0 1-53.802667 55.893334c2.048 0.256 3.882667 1.152 5.973333 1.152h-11.818666c2.048 0 3.84-0.981333 5.845333-1.109334a59.093333 59.093333 0 0 1-53.162667-55.893333l-13.056-284.16a54.314667 54.314667 0 0 1 54.613334-57.045333h26.282666a52.992 52.992 0 0 1 54.186667 57.002666l-15.146667 284.16z" fill="#d81e06" p-id="5819"></path></svg>
        <svg v-else-if="msg.pending" t="1772618878456" class="icon rotate-icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="4818" width="200" height="200"><path d="M469.333333 85.333333m42.666667 0l0 0q42.666667 0 42.666667 42.666667l0 128q0 42.666667-42.666667 42.666667l0 0q-42.666667 0-42.666667-42.666667l0-128q0-42.666667 42.666667-42.666667Z" fill="#000000" opacity=".8" p-id="4819"></path><path d="M469.333333 725.333333m42.666667 0l0 0q42.666667 0 42.666667 42.666667l0 128q0 42.666667-42.666667 42.666667l0 0q-42.666667 0-42.666667-42.666667l0-128q0-42.666667 42.666667-42.666667Z" fill="#000000" opacity=".4" p-id="4820"></path><path d="M938.666667 469.333333m0 42.666667l0 0q0 42.666667-42.666667 42.666667l-128 0q-42.666667 0-42.666667-42.666667l0 0q0-42.666667 42.666667-42.666667l128 0q42.666667 0 42.666667 42.666667Z" fill="#000000" opacity=".2" p-id="4821"></path><path d="M298.666667 469.333333m0 42.666667l0 0q0 42.666667-42.666667 42.666667l-128 0q-42.666667 0-42.666667-42.666667l0 0q0-42.666667 42.666667-42.666667l128 0q42.666667 0 42.666667 42.666667Z" fill="#000000" opacity=".6" p-id="4822"></path><path d="M783.530667 180.138667m30.169889 30.169889l0 0q30.169889 30.169889 0 60.339779l-90.509668 90.509668q-30.169889 30.169889-60.339779 0l0 0q-30.169889-30.169889 0-60.339779l90.509668-90.509668q30.169889-30.169889 60.339779 0Z" fill="#000000" opacity=".1" p-id="4823"></path><path d="M330.965333 632.661333m30.16989 30.16989l0 0q30.169889 30.169889 0 60.339778l-90.509668 90.509668q-30.169889 30.169889-60.339779 0l0 0q-30.169889-30.169889 0-60.339778l90.509668-90.509668q30.169889-30.169889 60.339779 0Z" fill="#000000" opacity=".5" p-id="4824"></path><path d="M843.861333 783.530667m-30.169889 30.169889l0 0q-30.169889 30.169889-60.339779 0l-90.509668-90.509668q-30.169889-30.169889 0-60.339779l0 0q30.169889-30.169889 60.339779 0l90.509668 90.509668q30.169889 30.169889 0 60.339779Z" fill="#000000" opacity=".3" p-id="4825"></path><path d="M391.338667 330.965333m-30.16989 30.16989l0 0q-30.169889 30.169889-60.339778 0l-90.509668-90.509668q-30.169889-30.169889 0-60.339779l0 0q30.169889-30.169889 60.339778 0l90.509668 90.509668q30.169889 30.169889 0 60.339779Z" fill="#000000" opacity=".7" p-id="4826"></path></svg>

      </div>
      <div
        key="bubble"
        class="human-bubble selectable"
        @contextmenu.prevent="onContextMenu"
      >
        <div class="bubble-content">{{ msg.content }}</div>
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
      @re-generate="reGenerateContext"
    />
  </transition>
</template>


<script setup lang="ts">
import { nextTick, ref, onMounted, onBeforeUnmount, computed } from 'vue'
import msgBubbleMenu from './comp/msgBubbleMenu.vue'

type UploadedFile = {
  file_name: string
  file_id: string
}

type msgBubData = {
  id: string
  cid: string
  hid: string
  role: 'human'
  content: string
  extra: any
  pending?: boolean
  error?: boolean
}
const props = defineProps<{
  msg: msgBubData
}>()

const uploadedFiles = computed<UploadedFile[]>(() => {
  return props.msg.extra?.user_meta_data?.uploaded_files ?? []
})

const isShowMenu = ref(false)
const menuStyle = ref<Record<string, string>>({})
const menuRef = ref<any>(null)
const menuWidthGuess = 144
const menuHeightGuess = 120

function onContextMenu(e: MouseEvent) {
  showPopMenu(e.clientX, e.clientY)
}

function showPopMenu(position_x: number, position_y: number) {
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

function reEditContext() {
  console.log("Note: reEditContext: msg.id = " + props.msg.id)
}

function reGenerateContext() {
  console.log("Note: reGenerateContext: msg.id = " + props.msg.id)
}

function onDocumentClick(e: MouseEvent) {
  const menuEl = menuRef.value?.$el || menuRef.value
  if (!menuEl) return
  if (menuEl === e.target || menuEl.contains(e.target as Node)) return
  closePopMenu()
}

function onWindowResize() {
  closePopMenu()
}

onMounted(() => {
  document.addEventListener('click', onDocumentClick, true)
  window.addEventListener('resize', onWindowResize)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', onDocumentClick, true)
  window.removeEventListener('resize', onWindowResize)
})
</script>


<style scoped>
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
  white-space: pre-wrap;   /* Keep \n as line break */
  word-break: break-word;  /* Prevent long text overflow */
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
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  width: 100%;
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
</style>
