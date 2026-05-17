import { reactive, ref } from 'vue'
import darkCss from 'highlight.js/styles/atom-one-dark.css?url'
import lightCss from 'highlight.js/styles/github.css?url'

export const apix_client_version = '2.1.0'

export function genUUID() {
  return crypto.randomUUID()
}

export const defaultCards = [
  { id: '-folder-preset', title: '卡片组', type: 'folder', level: 'system' },
  { id: '-annotation-preset', title: '注释', type: 'note', level: 'system' },
  { id: '-script-preset', title: '运行脚本', type: 'script', level: 'system' },
  { id: '-task-preset', title: '执行任务', type: 'task', level: 'system' },
]

export function getSupportFileSVG (path) {
  const fileName = path.split('/').pop()
  const fileType = fileName.split('.').pop()
  // console.log('[getSupportFileSVG] File type:', fileType)
  switch (fileType) {
    case 'md':
      return `<svg t="1778939473456" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="13048" width="20" height="20"><path d="M153.6 0h514.5856L972.8 307.9424V921.6a102.4 102.4 0 0 1-102.4 102.4H153.6a102.4 102.4 0 0 1-102.4-102.4V102.4a102.4 102.4 0 0 1 102.4-102.4z" fill="#39AFD1" p-id="13049"></path><path d="M665.6 0l307.2 307.2h-204.8a102.4 102.4 0 0 1-102.4-102.4V0z" fill="#298099" p-id="13050"></path><path d="M639.1552 384h-62.2592l-70.528 228.224L435.84 384h-62.2592L307.2 715.9552h58.112l45.6192-232.3712 70.5536 224.0768h49.792l66.3808-224.0768 49.7664 232.3712h58.0864L639.1296 384h0.0256z" fill="#FFFFFF" p-id="13051"></path></svg>`
    case 'aflow':
      return `<svg t="1778939527820" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="14434" width="200" height="200"><path d="M767.984001 1024H256.015999a255.984001 255.984001 0 0 1-255.984001-255.984001v-511.968002a255.984001 255.984001 0 0 1 255.984001-255.984001h511.968002a255.984001 255.984001 0 0 1 255.984001 255.984001v511.968002a255.984001 255.984001 0 0 1-255.984001 255.984001zM298.957315 661.078683a43.005312 43.005312 0 0 0-43.005312 42.941316 43.069308 43.069308 0 0 0 43.005312 43.005312 43.005312 43.005312 0 0 0 42.87732-43.005312 42.941316 42.941316 0 0 0-42.813324-43.005312z m139.639273 6.975564a35.901756 35.901756 0 0 0-35.773764 35.965752 35.83776 35.83776 0 0 0 35.773764 35.773764h293.485657a35.83776 35.83776 0 0 0 35.773764-35.773764 35.901756 35.901756 0 0 0-35.773764-35.965752z m-139.639273-199.027561a43.005312 43.005312 0 0 0-43.005312 42.87732 43.005312 43.005312 0 0 0 43.005312 42.87732 42.941316 42.941316 0 0 0 42.87732-42.87732 42.941316 42.941316 0 0 0-42.813324-42.87732z m139.639273 7.103556a35.83776 35.83776 0 0 0-35.773764 35.773764 35.83776 35.83776 0 0 0 35.773764 35.773764h293.485657a35.83776 35.83776 0 0 0 35.773764-35.773764 35.83776 35.83776 0 0 0-35.773764-35.773764zM298.957315 276.974689a43.069308 43.069308 0 0 0-43.005312 43.069308 43.005312 43.005312 0 0 0 43.005312 42.87732 42.941316 42.941316 0 0 0 42.87732-42.87732 43.005312 43.005312 0 0 0-42.813324-43.005312z m139.639273 7.167552a35.901756 35.901756 0 0 0-35.773764 35.901756 35.83776 35.83776 0 0 0 35.773764 35.773764h293.485657a35.83776 35.83776 0 0 0 35.773764-35.773764 35.901756 35.901756 0 0 0-35.773764-35.901756z" fill="#94c0c0" p-id="14435"></path></svg>`
    default:
      return `<svg t="1778344738953" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="9209" width="16" height="16"><path d="M170.666667 219.428571h682.666666V146.285714H170.666667v73.142857z m0 219.428572h487.619047v-73.142857H170.666667v73.142857z m0 219.428571h292.571428v-73.142857H170.666667v73.142857z m0 219.428572h682.666666v-73.142857H170.666667v73.142857z" fill="var(--apix-secondary-dark-color)" p-id="9210"></path></svg>`
  }
}

export const tabContentCache = {}

export const globalSelection = reactive({
  id: '',
  content: '',
  rect: null
})

export const globalCardDragState = {
  sourceUid: "",
  cardUid: "",
  cardType: "", // 'preset' or 'inTab'
}

export const globalDragHoverCard = ref('')

export function clearGlobalDragState() {
  globalCardDragState.sourceUid = ''
  globalCardDragState.cardUid = ''
  globalCardDragState.cardType = ''
}

export const setHighlightTheme = (isDark) => {
  const id = 'hljs-theme'
  let link = document.getElementById(id)

  if (!link) {
    link = document.createElement('link')
    link.id = id
    link.rel = 'stylesheet'
    document.head.appendChild(link)
  }

  link.href = isDark ? darkCss : lightCss
}