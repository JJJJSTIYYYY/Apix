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
      return `<svg t="1779020358662" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="5416" width="20" height="20"><path d="M96 672v-341.333333h85.333333l128 128 128-128h85.333334v341.333333h-85.333334v-220.586667l-128 128-128-128v220.586667h-85.333333m597.333333-341.333333h128v170.666666h106.666667l-170.666667 192-170.666666-192h106.666666z" fill="#42A5F5" p-id="5417"></path></svg>`
    case 'js':
      return `<svg t="1779020299271" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="4969" width="20" height="20"><path d="M128 128h768v768H128V128m201.813333 641.706667c17.066667 36.266667 50.773333 66.133333 108.373334 66.133333 64 0 107.946667-34.133333 107.946666-108.8v-246.613333h-72.533333V725.333333c0 36.693333-14.933333 46.08-38.4 46.08-24.746667 0-34.986667-17.066667-46.506667-37.12l-58.88 35.413334m255.146667-7.68c21.333333 41.813333 64.426667 73.813333 131.84 73.813333 68.266667 0 119.466667-35.413333 119.466667-100.693333 0-60.16-34.56-87.04-96-113.493334l-17.92-7.68c-31.146667-13.226667-44.373333-22.186667-44.373334-43.52 0-17.493333 13.226667-31.146667 34.56-31.146666 20.48 0 34.133333 8.96 46.506667 31.146666l55.893333-37.12c-23.466667-40.96-56.746667-56.746667-102.4-56.746666-64.426667 0-105.813333 40.96-105.813333 95.146666 0 58.88 34.56 86.613333 86.613333 108.8l17.92 7.68c33.28 14.506667 52.906667 23.466667 52.906667 48.213334 0 20.48-19.2 35.413333-49.066667 35.413333-35.413333 0-55.893333-18.346667-71.253333-43.946667l-58.88 34.133334z" fill="#FFCA28" p-id="4970"></path></svg>`
    case 'py':
      return `<svg t="1779020329964" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="5190" width="20" height="20"><path d="M420.693333 85.333333C353.28 85.333333 298.666667 139.946667 298.666667 207.36v71.68h183.04c16.64 0 30.293333 24.32 30.293333 40.96H207.36C139.946667 320 85.333333 374.613333 85.333333 442.026667v161.322666c0 67.413333 54.613333 122.026667 122.026667 122.026667h50.346667v-114.346667c0-67.413333 54.186667-122.026667 121.6-122.026666h224c67.413333 0 122.026667-54.229333 122.026666-121.642667V207.36C725.333333 139.946667 670.72 85.333333 603.306667 85.333333z m-30.72 68.693334c17.066667 0 30.72 5.12 30.72 30.293333s-13.653333 38.016-30.72 38.016c-16.64 0-30.293333-12.8-30.293333-37.973333s13.653333-30.336 30.293333-30.336z" fill="#3C78AA" p-id="5191"></path><path d="M766.250667 298.666667v114.346666a121.6 121.6 0 0 1-121.6 121.984H420.693333A121.6 121.6 0 0 0 298.666667 656.597333v160a122.026667 122.026667 0 0 0 122.026666 122.026667h182.613334A122.026667 122.026667 0 0 0 725.333333 816.64v-71.68h-183.082666c-16.64 0-30.250667-24.32-30.250667-40.96h304.64A122.026667 122.026667 0 0 0 938.666667 581.973333v-161.28a122.026667 122.026667 0 0 0-122.026667-122.026666zM354.986667 491.221333l-0.170667 0.170667c0.512-0.085333 1.066667-0.042667 1.621333-0.170667z m279.04 310.442667c16.64 0 30.293333 12.8 30.293333 37.973333a30.293333 30.293333 0 0 1-30.293333 30.293334c-17.066667 0-30.72-5.12-30.72-30.293334s13.653333-37.973333 30.72-37.973333z" fill="#FDD835" p-id="5192"></path></svg>`
    case 'txt':
      return `<svg t="1779035655244" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="5137" width="20" height="20"><path d="M554.666667 384h234.666666L554.666667 149.333333V384M256 85.333333h341.333333l256 256v512a85.333333 85.333333 0 0 1-85.333333 85.333334H256a85.333333 85.333333 0 0 1-85.333333-85.333334V170.666667c0-47.36 37.973333-85.333333 85.333333-85.333334m384 682.666667v-85.333333H256v85.333333h384m128-170.666667v-85.333333H256v85.333333h512z" fill="#42A5F5" p-id="5138"></path></svg>`
    case 'aflow':
      return `<svg t="1779020515853" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="11343" width="20" height="20"><path d="M170.666667 597.333333h170.666666v-170.666666H170.666667v170.666666z m0 213.333334h170.666666v-170.666667H170.666667v170.666667z m213.333333-213.333334h512v-170.666666H384v170.666666z m0 213.333334h512v-170.666667H384v170.666667z" fill="var(--apix-tertiary-dark-color)" p-id="11344"></path><path d="M170.666667 384h170.666666V213.333333H170.666667v170.666667z m213.333333-170.666667v170.666667h512V213.333333H384z" fill="#94c0c0" p-id="11345" data-spm-anchor-id="a313x.search_index.0.i5.7e263a81eZIatH" class="selected"></path></svg>`
    default:
      return `<svg t="1778344738953" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="9209" width="16" height="16"><path d="M170.666667 219.428571h682.666666V146.285714H170.666667v73.142857z m0 219.428572h487.619047v-73.142857H170.666667v73.142857z m0 219.428571h292.571428v-73.142857H170.666667v73.142857z m0 219.428572h682.666666v-73.142857H170.666667v73.142857z" fill="var(--apix-secondary-dark-color)" p-id="9210"></path></svg>`
  }
}

// const messageCache = reactive<Record<string, ChatMessage[]>>({})
// const generatingState = reactive<Record<string, GeneratingState[]>>({})

// globalDataLock 用于保护后续五个公共数据不被多个页面并发写入, 页面切入/切出时比较 page_id 和 globalDataLock.value
export const globalDataLock = ref("default")
export const historyList = ref([])
export const messageCache = reactive({})
export const generatingState = reactive({})
export const loadedHistorySet = reactive(new Set())
export const loadingHistorySet = reactive(new Set())

export const tabContentCache = {}

export const globalSelection = reactive({
  id: '',
  role: '',
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

export const showWarnBannerInCodeEditor = ref(true)