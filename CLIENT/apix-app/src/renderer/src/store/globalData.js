import { reactive } from 'vue'
import darkCss from 'highlight.js/styles/atom-one-dark.css?url'
import lightCss from 'highlight.js/styles/github.css?url'

export const apix_client_version = '2.1.0'

export const defaultCards = () => [
  { id: '-folder-preset', title: '卡片组', type: 'folder', level: 'system' },
  { id: '-annotation-preset', title: '注释', type: 'note', level: 'system' },
  { id: '-script-preset', title: '运行脚本', type: 'script', level: 'system' },
  { id: '-task-preset', title: '执行任务', type: 'task', level: 'system' },
]

export const tabContentCache = {}

export const globalState = {
  draggedStartCardUid_parent: 0, // 记录被拖拽对象的来源，不是被拖拽对象的uid
  draggedStartCardUid: 0, // 记录被拖拽对象的uid
  draggedTabCard: "",
  draggedCard: "",
};

export const globalSelection = reactive({
  id: '',
  content: ''
})

export function clearDragMark() {
  globalState.draggedStartCardUid_parent = 0 // 记录被拖拽对象的来源，不是被拖拽对象的uid
  globalState.draggedStartCardUid = 0 // 记录被拖拽对象的uid
  globalState.draggedTabCard = ""
  globalState.draggedCard = ""
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