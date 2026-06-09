<template>
  <Teleport to="body">
    <Transition name="cd">
      <div 
        v-if="visible"
        class="task-info-mask" 
        @click.self="close"
      >
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
                <svg t="1777025380440" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="1147" width="16" height="16">
                  <path d="M412.128 512l293.28-285.248c9.312-9.056 14.592-21.6 14.592-34.752 0-26.496-21.056-48-47.008-48-12.064 0-23.68 4.736-32.416 13.248l-317.12 308.416Q304 484.544 304 512q0 27.424 19.456 46.336l317.12 308.384c8.736 8.544 20.352 13.28 32.416 13.28 25.952 0 47.008-21.504 47.008-48 0-13.12-5.28-25.696-14.592-34.752L412.16 512z" fill="currentColor" p-id="1148"></path>
                </svg>
              </button>
              <button
                plain
                class="path-ctrl-btn after-btn"
                @click="returnAfterDir()"
              >
                <svg t="1777025401907" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="1364" width="16" height="16">
                  <path d="M611.872 512L318.592 226.752A48.48 48.48 0 0 1 304 192c0-26.496 21.056-48 47.008-48 12.064 0 23.68 4.736 32.416 13.248l317.12 308.416q19.456 18.88 19.456 46.336 0 27.424-19.456 46.336l-317.12 308.384a46.528 46.528 0 0 1-32.416 13.28c-25.952 0-47.008-21.504-47.008-48 0-13.12 5.28-25.696 14.592-34.752L611.84 512z" fill="currentColor" p-id="1365"></path>
                </svg>
              </button>
            </div>
            <div class="task-info-title">
              <div class="task-id">工具详情</div>
            </div>
            <div 
              class="btn-area"
            >
              <div style="min-width: 28px;"></div>
              <button
                plain
                class="close-btn"
                @click="close"
              >
                <svg class="icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1024 1024"><path d="M764.288 214.592 512 466.88 259.712 214.592a31.936 31.936 0 0 0-45.12 45.12L466.752 512 214.528 764.224a31.936 31.936 0 1 0 45.12 45.184L512 557.184l252.288 252.288a31.936 31.936 0 0 0 45.12-45.12L557.12 512.064l252.288-252.352a31.936 31.936 0 1 0-45.12-45.184z" fill="currentColor"></path></svg>
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
                      {{ item.displayKey ?? item.key }}
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
          <footer class="task-footer">
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
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { nextTick, ref, watch, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { mdDisplayer } from '../../comp/mdDisplayer';

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

async function close() {
  visible.value = false
  await nextTick()
  emit('close')
}

const visible = ref(false)

onMounted(() => {
  visible.value = true
})

// ------------------------
// Layout
// ------------------------
const COLUMN_WIDTH = 260 // Must match .task-column min-width

// ------------------------
// State
// ------------------------

const columns = ref([])
const footerPathLabel = ref([])

const backStack = ref([])     // history back
const forwardStack = ref([])  // history forward

// ------------------------
// Utils
// ------------------------
function isExpandable(val) {
  return val !== null && typeof val === 'object'
}

function normalizeValue(value) {
  // Avoid showing raw JSON strings
  if (typeof value === 'string') {
    try {
      return JSON.parse(value)
    }
    catch {
      return value
    }
  }

  return value
}

function buildColumn(data, depth = 0, basePath = '') {
  if (!isExpandable(data)) return []

  // Array support
  if (Array.isArray(data)) {
    return data.map((value, index) => {
      const rawValue = normalizeValue(value)
      const keyPath = basePath
        ? `${basePath}.${index}`
        : `${index}`

      return {
        // Logic key
        key: `${index}`,

        // UI display key
        displayKey: `[${index}]`,

        keyPath,

        value: isExpandable(rawValue)
          ? null
          : rawValue,

        rawValue,

        depth,

        hasChildren: isExpandable(rawValue),

        active: false,
      }
    })
  }

  return Object.keys(data).map((key) => {
    const rawValue = normalizeValue(data[key])

    const keyPath = basePath
      ? `${basePath}.${key}`
      : key

    return {
      key,

      keyPath,

      value: isExpandable(rawValue)
        ? null
        : rawValue,

      rawValue,

      depth,

      hasChildren: isExpandable(rawValue),

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
  const pathKeys = path ? path.split('.') : []

  const newColumns = []

  // Root is taskInfo itself
  let currentData = props.taskInfo

  let lastItem = null

  // Empty path -> root
  if (!pathKeys.length) {
    columns.value = [
      buildColumn(props.taskInfo, 0),
    ]

    updateFooterPath('')

    return
  }

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

  // Auto expand only once
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
      ElMessage({
        message: '空的子集',
        plain: true,
      })
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
  columns.value = [
    buildColumn(props.taskInfo, 0),
  ]

  backStack.value = []
  forwardStack.value = []
}

// ------------------------
// Interaction
// ------------------------
function onItemClick(item, colIndex) {
  const column = columns.value[colIndex]

  if (!column) return

  // Primitive value preview
  if (!item.hasChildren) {
    mdDisplayer.show(
      '**' + item.key + '**\n\n' +
      '`Path: ' + item.keyPath + '`\n\n' +
      '```\n' +
      String(item.rawValue) +
      '\n```'
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
/* ------------------------
   Root
------------------------ */
.task-info-mask {
  position: absolute;
  width: 100vw;
  height: 100vh;
  inset: 0;
  z-index: 9999;

  display: flex;
  align-items: center;
  justify-content: center;

  background: var(--apix-mask-background);
  backdrop-filter: saturate(180%) blur(6px);
  animation: opacityFadeIn 0.5s var(--apix-cubic-bezier);
}

@keyframes opacityFadeIn {
  0% { 
    opacity: 0.3; 
  }
  100% { 
    opacity: 1; 
  }
}

.task-info-root {
  max-width: 780px;
  min-width: 520px;
  display: flex;
  flex-direction: column;
  color: var(--apix-darkest-color);
  overflow: hidden;
  border-radius: 20px;
  background: var(--apix-panel-layer-1-background);
  box-shadow: var(--apix-shadow-lg);

  /* Width + enter/leave damping */
  transition:
    width 0.32s var(--apix-cubic-bezier),
    opacity 0.25s var(--apix-cubic-bezier),
    transform 0.25s var(--apix-cubic-bezier);
  scrollbar-width: none;
  animation: scaleFadeIn 0.5s var(--apix-cubic-bezier);
}

@keyframes scaleFadeIn {
  0% { 
    opacity: 0.3; 
    transform: scale(0.8); 
  }
  100% { 
    opacity: 1; 
    transform: scale(1); 
  }
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
  color: var(--apix-default-dark-color);
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
  border-top: 1px solid var(--apix-default-light-color);
  border-bottom: 1px solid var(--apix-default-light-color);
}

/* ------------------------
   Columns
------------------------ */
.task-content {
  display: flex;
  width: max-content;
  height: 100%;
  overflow-y: hidden;
  overflow-x: auto;
}

/* Column base */
.task-column {
  min-width: 260px;
  height: 100%;
  max-height: 500px;
  box-shadow: inset -1px 0 0 0 var(--apix-default-light-color);
  padding: 12px 0;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  overflow-y: hidden;
  overflow-x: auto;
  touch-action: pan-y;
  transition: height .25s var(--apix-cubic-bezier);
}

/* Column slide animation */
.column-slide-enter-active,
.column-slide-leave-active {
  transition:
    opacity 0.22s var(--apix-cubic-bezier),
    transform 0.22s var(--apix-cubic-bezier);
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
  transition: background 0.15s ease;
  color: var(--apix-default-dark-color);
}

.kv-item:hover {
  background: var(--apix-default-light-color);
}

.kv-key {
  font-weight: 500;
  font-size: 13px;
}

.kv-value {
  font-size: 12px;
  color: var(--apix-secondary-dark-color);
  margin-left: 8px;
  max-width: 140px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.kv-expand {
  font-size: 12px;
  color: var(--apix-tertiary-dark-color);
}

.kv-item.isSelect {
  background: var(--apix-common-button-active);
  color: var(--apix-common-button-text);
}

.kv-expand.isSelect {
  font-size: 12px;
  color: var(--apix-default-light-color);
}

.kv-item:active {
  background: var(--apix-common-button-active);
  color: var(--apix-common-button-text);
}

.kv-item:active .kv-value {
  color: var(--apix-default-light-color);
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

  color: var(--apix-secondary-dark-color);
  background: var(--apix-default-light-color);
}

.path-ctrl-btn:hover {
  background: var(--apix-lightest-color);
}

.path-ctrl-btn:active {
  background: var(--apix-default-light-color);
}

.close-btn {
  width: 28px;
  height: 28px;
  border-radius: 8px;

  border: none;
  cursor: pointer;
  font-size: 18px;
  line-height: 1;

  color: var(--apix-secondary-dark-color);
  background: var(--apix-default-light-color);

  display: flex;
  align-items: center;
  justify-content: center;
}

.close-btn:hover {
  color: var(--apix-danger-text);
  background: var(--apix-danger-hover);
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
  transition: all 0.25s var(--apix-cubic-bezier);
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
  min-height: 32px;
  padding: 4px 16px;
  text-align: center;
  color: var(--apix-tertiary-dark-color);
}

.footer-label {
  border-radius: 24px;
  padding: 4px 8px;
  transition: color 0.2s var(--apix-cubic-bezier),
    border 0.2s var(--apix-cubic-bezier),
    box-shadow 0.2s var(--apix-cubic-bezier);
}

.footer-label:hover { 
  color: var(--apix-link-color);
  text-decoration: underline;
}

/* ===== transition: mask ===== */
.cd-enter-active,
.cd-leave-active {
  transition: opacity 0.25s var(--apix-cubic-bezier);
}

.cd-enter-from,
.cd-leave-to {
  opacity: 0;
}

/* ===== transition: dialog ===== */
.cd-enter-active .cd-wrapper {
  transition:
    transform 0.25s var(--apix-cubic-bezier),
    opacity 0.25s var(--apix-cubic-bezier);
}

.cd-leave-active .cd-wrapper {
  transition:
    transform 0.25s var(--apix-cubic-bezier),
    opacity 0.25s var(--apix-cubic-bezier);
}

.cd-enter-from .cd-wrapper {
  opacity: 0;
  transform: scale(0.96);
}

.cd-leave-to .cd-wrapper {
  opacity: 0;
  transform: scale(0.92);
}
</style>
