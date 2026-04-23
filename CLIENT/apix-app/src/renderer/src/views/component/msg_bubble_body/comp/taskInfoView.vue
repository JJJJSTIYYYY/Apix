<template>
  <!-- Root enter / leave -->
  <Transition name="fade" appear style="position: fixed; top: 46vh; left: 62%; transform: translate(-50%, -50%);">
    <div
      class="task-info-root"
      :style="{
        width: `${(columns.length * COLUMN_WIDTH) > 520 ? (columns.length * COLUMN_WIDTH) : 520}px`
      }"
    >
      <!-- Header -->
      <header class="task-header">
        <div 
          class="btn-area"
        >
          <button
            plain
            class="path-ctrl-btn before-btn"
            @click="returnBeforeDir()"
          >
            <div style="transform: scaleY(1.8);"><</div>
          </button>
          <button
            plain
            class="path-ctrl-btn after-btn"
            @click="returnAfterDir()"
          >
            <div style="transform: scaleY(1.8);">></div>
          </button>
        </div>
        <div class="task-info-title">
          <div class="task-id">任务详情</div>
          <div class="task-id">{{ taskInfo.messages.task_id }}</div>
        </div>
        <div 
          class="btn-area"
        >
          <button
            plain
            class="close-btn"
            @click="emit('close')"
          >
            ×
          </button>
        </div>
      </header>

      <!-- Scroll Wrapper -->
      <div class="scroll-wrapper">
        <TransitionGroup
          name="column-slide"
          tag="div"
          class="task-content"
        >
          <div
            v-for="(column, colIndex) in columns"
            :key="colIndex"
            class="task-column"
          >
            <!-- Column inner scroll -->
            <div class="column-scroll">
              <div
                v-for="item in column"
                :key="item.keyPath"
                class="kv-item"
                :class="{isSelect: item.active}"
                @click="onItemClick(item, colIndex)"
              >
                <div class="kv-key">
                  {{ item.key }}
                </div>

                <div class="kv-value" v-if="!item.hasChildren">
                  {{ item.value }}
                </div>

                <div class="kv-expand" :class="{isSelect: item.active}" v-else>
                  ▶
                </div>
              </div>
            </div>
          </div>
        </TransitionGroup>
      </div>

      <!-- Footer -->
      <footer class="task-footer" v-if="footerPathLabel.length">
        <TransitionGroup
          name="footer-label"
          tag="div"
          class="footer-label-wrapper"
        >
          <span
            v-for="(label, index) in footerPathLabel"
            :key="label"
            class="footer-label-item"
          >
            <span 
              class="footer-label"
              @click="jumpToPath(index)"
            >
              {{ label }}
            </span>
            <span v-if="index < footerPathLabel.length - 1"> > </span>
          </span>
        </TransitionGroup>
      </footer>

    </div>
  </Transition>
</template>

<script setup>
// ------------------------
// Props / Emits
// ------------------------
const props = defineProps({
  taskInfo: {
    type: Object,
    required: true,
  },
})

const emit = defineEmits({
  close: () => true,
})

// ------------------------
// Layout
// ------------------------
const COLUMN_WIDTH = 260 // Must match .task-column min-width

// ------------------------
// State
// ------------------------
import { nextTick, ref, watch, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { mdDisplayer } from '../../comp/mdDisplayer';

const columns = ref([])
const footerPathLabel = ref([])

const backStack = ref([])     // history back
const forwardStack = ref([])  // history forward

// ------------------------
// Utils
// ------------------------
function isObject(val) {
  return val !== null && typeof val === 'object'
}

function normalizeValue(value) {
  // Avoid showing raw JSON strings
  if (typeof value === 'string') {
    try {
      return JSON.parse(value)
    } catch {
      return value
    }
  }
  return value
}

function buildColumn(data, depth = 0, basePath = '') {
  if (!isObject(data)) return []

  return Object.keys(data).map((key) => {
    const rawValue = normalizeValue(data[key])
    const keyPath = basePath ? `${basePath}.${key}` : key

    return {
      key,
      keyPath,
      value: isObject(rawValue) ? null : rawValue,
      rawValue,
      depth,
      hasChildren: isObject(rawValue),
      active: false,
    }
  })
}

function updateFooterPath(path) {
  const pathList = path ? path.split('.') : []
  footerPathLabel.value = pathList

  // Clear all active states first
  columns.value.forEach(column => {
    column.forEach(item => {
      item.active = false
    })
  })

  // Highlight items along the path
  let currentPath = ''
  pathList.forEach((key, depth) => {
    currentPath = currentPath ? `${currentPath}.${key}` : key

    const column = columns.value[depth]
    if (!column) return

    const targetItem = column.find(i => i.keyPath === currentPath)
    if (targetItem) {
      targetItem.active = true
    }
  })
}


// ------------------------
// Core navigation (NO history side effects)
// ------------------------
function jumpToKeyPath(path) {
  const pathKeys = path.split('.')
  const newColumns = []

  let currentData = {
    payload: props.taskInfo.messages.payload,
    result: props.taskInfo.messages.result,
    status: props.taskInfo.messages.status,
    created_at: props.taskInfo.messages.created_at,
    finished_at: props.taskInfo.messages.finished_at,
  }

  let lastItem = null

  for (let depth = 0; depth < pathKeys.length; depth++) {
    const key = pathKeys[depth]

    const column = buildColumn(
      currentData,
      depth,
      pathKeys.slice(0, depth).join('.')
    )

    const item = column.find(i => i.key === key)
    if (!item) break

    newColumns.push(column)
    currentData = item.rawValue
    lastItem = item
  }

  // Auto expand only once (file-manager behavior)
  if (lastItem && lastItem.hasChildren) {
    const nextColumn = buildColumn(
      lastItem.rawValue,
      pathKeys.length,
      lastItem.keyPath
    )
    if (nextColumn.length) {
      newColumns.push(nextColumn)
    }
    else {
      ElMessage({ message: '空的子集', plain: true, }) 
    }
  }

  columns.value = newColumns
  updateFooterPath(path)
}

// ------------------------
// Unified navigation entry (ONLY place that writes history)
// ------------------------
function navigateTo(path) {
  const currentPath = footerPathLabel.value.join('.')

  if (currentPath && currentPath !== path) {
    backStack.value.push(currentPath)
    forwardStack.value = []
  }

  jumpToKeyPath(path)
}

function scrollToRight() {
  const box = document.querySelector('.scroll-wrapper')
  if (!box) return

  box.scrollTo({
    left: box.scrollWidth,
    behavior: 'smooth'
  });
}

// ------------------------
// Init
// ------------------------
function initColumns() {
  const { payload, status, result, created_at, finished_at } =
    props.taskInfo.messages

  const rootData = {
    payload,
    result,
    status,
    created_at,
    finished_at,
  }

  columns.value = [
    buildColumn(rootData, 0),
  ]

  // updateFooterPath('result')

  // Init history ONCE
  backStack.value = []
  forwardStack.value = []
}

// ------------------------
// Interaction
// ------------------------
function onItemClick(item, colIndex) {
  const column = columns.value[colIndex]
  if (!column) return

  if (!item.hasChildren && item.rawValue) {
    mdDisplayer.show(
      '**' + item.key + '**\n\n' +
      '`Path: ' + item.keyPath + '`\n\n' +
      '```\n' + item.rawValue + '\n```'
    )
    return
  }
  navigateTo(item.keyPath)
}

function jumpToPath(index) {
  if (index < 0 || index >= footerPathLabel.value.length) return
  const targetPath = footerPathLabel.value.slice(0, index + 1).join('.')
  navigateTo(targetPath)
}

function returnBeforeDir() {
  if (!backStack.value.length) return

  const currentPath = footerPathLabel.value.join('.')
  const prevPath = backStack.value.pop()

  if (currentPath) {
    forwardStack.value.push(currentPath)
  }

  jumpToKeyPath(prevPath)
}

function returnAfterDir() {
  if (!forwardStack.value.length) return

  const currentPath = footerPathLabel.value.join('.')
  const nextPath = forwardStack.value.pop()

  if (currentPath) {
    backStack.value.push(currentPath)
  }

  jumpToKeyPath(nextPath)
}

// ------------------------
// Watch
// ------------------------
watch(
  () => props.taskInfo,
  () => {
    initColumns()
  },
  { immediate: true }
)
watch(
  () => columns.value.length,
  async (newLength, oldLength = 0) => {
    if (newLength > oldLength) {
      await nextTick()
      scrollToRight()
    }
  }
)
</script>

<style scoped>
.fade-enter-from {
  opacity: 0;
}

.fade-enter-to {
  opacity: 1;
}

.fade-enter-active {
  transition: opacity 0.5s cubic-bezier(0.4, 0, 0.2, 1),
              transform 0.5s cubic-bezier(0.4, 0, 0.2, 1);
}

/* ------------------------
   Root
------------------------ */
.task-info-root {
  max-width: 780px;
  min-width: 520px;
  display: flex;
  flex-direction: column;
  color: #333;
  overflow: hidden;
  border-radius: 20px;
  background: rgb(247, 248, 248);
  border-top: 3px solid rgba(43, 159, 140, 0.509);
  border-bottom: 3px solid rgba(43, 159, 140, 0.509);
  box-shadow:0 10px 26px rgba(0, 0, 0, 0.166);

  /* Width + enter/leave damping */
  transition:
    width 0.32s cubic-bezier(0.22, 1, 0.36, 1),
    opacity 0.25s ease,
    transform 0.25s ease;
  scrollbar-width: none;
}

/* ------------------------
   Header
------------------------ */
.task-header {
  display: flex;
  height: 36px;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  flex-shrink: 0;
}

.task-id {
  font-size: 15px;
  font-weight: 600;
  color: #222;
  text-align: center;
}

/* ------------------------
   Scroll
------------------------ */
.column-scroll {
  flex: 1;
  padding: 0 12px;

  overflow: auto;

  overscroll-behavior: contain;
  scroll-behavior: smooth;
  touch-action: pan-y;
}

.scroll-wrapper {
  overflow-x: auto;
  overflow-y: hidden;
  height: calc(100% - 110px);
  width: 100%;
  scroll-behavior: smooth;
  border-top: 1px solid #02676515;
  border-bottom: 1px solid #02676515;
}

/* ------------------------
   Columns
------------------------ */
.task-content {
  display: flex;
  width: max-content;
  height: 100%;
  overflow-y: hidden;  /* 🚫 禁止纵向滚动 */
  overflow-x: auto;
}

/* Column base */
.task-column {
  min-width: 260px;
  height: 100%;              /* 关键：限定高度 */
  box-shadow: inset -1px 0 0 0 rgba(0, 0, 0, 0.05);
  padding: 12px 0;           /* 左右 padding 交给内部 */
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  overflow-y: hidden;
  overflow-x: auto;
  touch-action: pan-y;
}

/* Column slide animation */
.column-slide-enter-active,
.column-slide-leave-active {
  transition:
    opacity 0.22s ease,
    transform 0.22s cubic-bezier(0.22, 1, 0.36, 1);
}

.column-slide-enter-from {
  opacity: 0;
  transform: translateX(-28px);
}

.column-slide-leave-to {
  opacity: 0;
}

/* ------------------------
   KV
------------------------ */
.kv-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 8px;
  cursor: pointer;
  border-radius: 10px;
  transition: all 0.15s ease;
}
.kv-item.isSelect {
  background: #94ead54c;
}

.kv-item:hover {
  background: #94ead5b3;
}

.kv-item:active {
  background: #7ad1bbb3;
}

.kv-key {
  font-weight: 500;
  font-size: 13px;
}

.kv-value {
  font-size: 12px;
  color: #666;
  margin-left: 8px;
  max-width: 140px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.kv-expand {
  font-size: 12px;
  color: #9999992a;
}

.kv-expand.isSelect {
  font-size: 12px;
  color: #999999de;
}

/* ------------------------
   Btn area
------------------------ */
.btn-area {
  width: fit-content;
  height: fit-content;
  display: flex;
  flex-direction: row;
  gap: 3px;
}

.path-ctrl-btn {
  width: 28px;
  height: 28px;
  border-radius: 28px;

  border: none;
  cursor: pointer;
  font-size: 12px;
  line-height: 1;

  color: #555555;
  background: rgba(0, 0, 0, 0.05);
}

.path-ctrl-btn:hover {
  background: rgba(255, 255, 255, 0.435);
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.09);
}

.path-ctrl-btn:active {
  background: rgba(255, 255, 255, 0.429);
}

.close-btn {
  width: 28px;
  height: 28px;
  border-radius: 8px;

  border: none;
  cursor: pointer;
  font-size: 18px;
  line-height: 1;

  color: #555555;
  background: rgba(0, 0, 0, 0.05);
}

.close-btn:hover {
  color: #be0e0e;
  background: rgba(255, 47, 0, 0.196);
}

.close-btn:active {
  transform: scale(0.9);
}

/* ------------------------
   Footer
------------------------ */
.footer-label-wrapper {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

/* TransitionGroup 动画 */
.footer-label-enter-active {
  transition: all 0.25s cubic-bezier(0.22, 1, 0.36, 1);
}
.footer-label-enter-from {
  opacity: 0;
  transform: translateX(-6px);
}
.footer-label-enter-to {
  opacity: 1;
  transform: translateY(0);
}

/* 内部 label 样式 */
.footer-label-item {
  display: flex;
  align-items: center;
  gap: 2px;
}

.task-footer {
  padding: 4px 16px;
  text-align: center;
  color: #012b2a71;
}

.footer-label {
  border-radius: 24px;
  padding: 4px 8px;
  transition: all 0.2s ease;
  border: 1px solid #ffffff00;
}

.footer-label:hover { 
  color: #012b2ac4;
  border: 1px solid #83838380;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.07);
}
</style>
