<template>
  <div
    class="explorer-root"
    :style="{
      width: `${explorerWidth}px`
    }"
  >

    <!-- Resize handle -->
    <div
      class="resize-handle"
      @mousedown="startResize($event)"
      @click="showPanel()"
    ></div>

    <!-- Header -->
    <header class="explorer-header">
      <div class="explorer-title">
        文件资源管理
      </div>

      <div class="header-actions">
        <button
          class="icon-btn close-btn"
          @click="closeWorkspace"
        >
          <svg class="icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1024 1024"><path d="M764.288 214.592 512 466.88 259.712 214.592a31.936 31.936 0 0 0-45.12 45.12L466.752 512 214.528 764.224a31.936 31.936 0 1 0 45.12 45.184L512 557.184l252.288 252.288a31.936 31.936 0 0 0 45.12-45.12L557.12 512.064l252.288-252.352a31.936 31.936 0 1 0-45.12-45.184z" fill="var(--apix-default-dark-color)"></path></svg>
        </button>
      </div>
    </header>

    <!-- Workspace -->
    <div
      class="workspace-label-wrapper"
    >
      <span 
        class="workspace-label"
        :class="{empty_workspace: workspace.length === 0 || !workspace[0]}"
      >
        {{ workspaceName }}
      </span>

      <div class="workspace-label-btn-wrapper">
        <button
          class="icon-btn new-dir-btn"
          @click="createNewDir(selectedPath)"
          v-if="workspace.length > 0 && !!workspace[0]"
        >
          <svg t="1778492051017" class="icon" viewBox="0 0 1129 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="1214" width="20" height="20"><path d="M70.570342 176.426504h542.47341c-15.667589-60.875437-70.92725-105.856162-136.694267-105.856162H105.854864c-19.487148 0-35.284522 15.797374-35.284522 35.28582v70.569045z m614.563529 0h338.13674c58.461445 0 105.854864 47.392122 105.854864 105.854865v635.13308c0 58.462743-47.39342 105.856162-105.856162 105.856162H105.856162C47.39342 1023.270611 0 975.875894 0 917.414449V105.854864C0 47.39342 47.39342 0 105.856162 0H476.348188c104.903544 0 191.985075 76.296436 208.784385 176.426504z m2.926641 70.570343H70.570342v670.417602c0 19.487148 15.797374 35.28582 35.28582 35.28582h917.414449c19.487148 0 35.284522-15.798672 35.284522-35.28582V282.281369c0-19.487148-15.797374-35.28582-35.28582-35.28582h-335.207503zM529.278215 564.562738V390.731924a2.595691 2.595691 0 0 1 2.595691-2.595691h65.378961a2.595691 2.595691 0 0 1 2.595691 2.595691V564.562738h173.829516a2.595691 2.595691 0 0 1 2.59569 2.59569v65.378961a2.595691 2.595691 0 0 1-2.59569 2.595691H599.84726v173.830814a2.595691 2.595691 0 0 1-2.595691 2.59569h-65.378961a2.595691 2.595691 0 0 1-2.59569-2.59569V635.13308H355.447402a2.595691 2.595691 0 0 1-2.595691-2.595691V567.158428a2.595691 2.595691 0 0 1 2.595691-2.59569h173.830813z" fill="var(--apix-default-dark-color)" p-id="1215"></path></svg>
        </button>

        <button
          class="icon-btn new-file-btn"
          @click="createNewFile(selectedPath)"
          v-if="workspace.length > 0 && !!workspace[0]"
        >
          <svg t="1778492256909" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="7724" width="20" height="20"><path d="M480.426 410.047h62.463v333.14h-62.463z" fill="var(--apix-default-dark-color)" p-id="7725"></path><path d="M345.088 545.385h333.139v62.464H345.088z" fill="var(--apix-default-dark-color)" p-id="7726"></path><path d="M803.196 961.013H220.202c-40.185 0-72.874-32.69-72.874-72.874V138.576c0-40.185 32.69-72.875 72.874-72.875h437.245v214.417H876.07V888.14c0 40.183-32.69 72.873-72.874 72.873zM220.16 128.123c-5.747 0-10.41 4.664-10.41 10.41v749.564c0 5.704 4.663 10.41 10.41 10.41h582.993c5.705 0 10.41-4.706 10.41-10.41V342.58H630.339c-19.53 0-35.396-15.866-35.396-35.395V128.123H220.161z" fill="var(--apix-default-dark-color)" p-id="7727"></path><path d="M657.448 65.7L876.07 280.13l-43.766 44.622-218.623-214.428z" fill="var(--apix-default-dark-color)" p-id="7728"></path></svg>
        </button>
      </div>
    </div>

    <!-- Tree -->
    <div 
      class="tree-container"
      v-if="workspace.length > 0 && !!workspace[0]"
    >
      <div
        v-for="node in treeData"
        :key="node.path"
      >
        <TreeNode
          :node="node"
          :selected-path="selectedPath"
          :depth="0"
          @toggle="toggleFolder"
          @select="selectNode"
          @create="handleCreate"
          @want-to-create-file="createNewFile"
          @want-to-create-dir="createNewDir"
          @hide-all-input="(...args) => $emit('hideAllInput', ...args)"
          @upload-skill="handleUploadSkill"
        />
      </div>
    </div>

    <div
      class="empty-btn-wrapper"
      v-else
    >
      <button
        class="open-btn"
        @click="handleConnectWorkspace"
      >
        选择一个工作区
      </button>
    </div>

  </div>
</template>

<script setup lang="ts">
import {
  computed,
  ref,
  watch,
  onMounted,
  onBeforeUnmount,
} from 'vue'

import TreeNode from './file_tree_node.vue'
import { type NodeBase} from './file_tree_node.vue'

// ------------------------
// Props / Emits
// ------------------------
const props = defineProps<{
  workspace: NodeBase[]
}>()

const emit = defineEmits({
  close: () => true,
  create: (at_path, name, type) => true,  // Really create.
  delete: (path) => true,
  openFile: (path, name) => true,
  createNewPath: (at_path, type) => true,  // Fake create, only open a file name input.
  expandDir: (path) => true,
  collapseDir: (path) => true,
  changeWorkspace: (path) => true,
  hideAllInput: (nodePath) => true,
  uploadSkill: (atPath) => true,
})

// ------------------------
// State
// ------------------------
const selectedPath = ref('')
const creatingPath = ref('')

defineExpose({
  selectedPath,
  creatingPath
})

// ------------------------
// Workspace
// ------------------------
const workspaceName = ref('未选择工作区')

const handleConnectWorkspace = async () => {
  const result = await window.api.openFileDialog("folder")
  if (result.canceled || result.filePaths.length === 0) {
    return
  }

  const selected_path = (result.filePaths[0])
  console.log('Select workspace: ', selected_path)
  try {
    await window.api.watchWorkspace(selected_path)
    emit('changeWorkspace', selected_path)
  } catch (error) {
    console.error("[handleConnectWorkspace] error: ", error)
  }
}

// ------------------------
// Tree normalize
// ------------------------
function normalizeNode(node) {
  if (!node) return null
  return {
    name: node.name,
    path: node.path,
    type: node.type,
    expanded: node.expanded ?? false,
    is_creating: node.is_creating ?? false,
    creating_type: node.creating_type ?? 'directory',
    root: props.workspace[0].path,

    children: node.children
      ? node.children.map(normalizeNode)
      : [],
  }
}

const treeData = ref([])

// ------------------------
// Actions
// ------------------------
function toggleFolder(node) {
  // selectedPath.value = node.path
  // console.log("[toggleFolder] selectedPath: ", selectedPath.value)
  if (node.type !== 'directory') {
    return
  }
  // node.expanded = !node.expanded
  if (!node.expanded) {
    emit("expandDir", node.path)
  }
  else {
    emit("collapseDir", node.path)
  }
}

function selectNode(node) {
  selectedPath.value = node.path
  workspaceName.value = node.name
  emit("hideAllInput", creatingPath.value)
  console.log("[selectNode] selectedPath: ", selectedPath.value)

  if (node.type === 'file') {
    emit('openFile', node.path, node.name)
  }
}

function handleCreate(at_path, name, type) {
  emit("create", at_path, name, type)
}

const closeWorkspace = async () => {
  try {
    await window.api.unwatchWorkspace()
    selectedPath.value = ""
    workspaceName.value = ""
    emit('close')
  } catch (error) {
    console.error("[closeWorkspace] error: ", error)
  }
}

const createNewFile = async (atPath: string) => {
  creatingPath.value = atPath
  emit("createNewPath", atPath, 'file')
}

const createNewDir = async (atPath: string) => {
  creatingPath.value = atPath
  emit("createNewPath", atPath, 'directory')
}

const handleUploadSkill = async (atPath: string) => {
  emit("uploadSkill", atPath)
}

// ------------------------
// Resize
// ------------------------
const explorerWidth = ref(200)

const isResizing = ref(false)

let startX = 0
let startWidth = 0

function startResize(e) {
  isResizing.value = true

  startX = e.clientX
  startWidth = explorerWidth.value

  document.addEventListener(
    'mousemove',
    handleResize
  )

  document.addEventListener(
    'mouseup',
    stopResize
  )
}

function handleResize(e) {
  if (!isResizing.value) {
    return
  }

  const delta = e.clientX - startX

  const minWidth = 179
  const maxWidth = 720

  let newWid = Math.min(
    maxWidth,
    Math.max(
      minWidth,
      startWidth + delta
    )
  )
  if (newWid < 180 && delta < 30) newWid = 2
  explorerWidth.value = newWid
}

function stopResize() {
  isResizing.value = false

  document.removeEventListener(
    'mousemove',
    handleResize
  )

  document.removeEventListener(
    'mouseup',
    stopResize
  )
}

function showPanel() {
  if (explorerWidth.value < 180) explorerWidth.value = 200
}

// ------------------------
// Watch
// ------------------------
watch(
  () => props.workspace,
  (workspace) => {
    treeData.value =
      workspace?.map(normalizeNode) || []
  },
  {
    immediate: true,
    deep: true,
  }
)

// ------------------------
// Initial
// ------------------------
const globalHandleKeydown = async (
  e: KeyboardEvent & {
    isComposing?: boolean
    keyCode?: number
  }
) => {
  // IME composing
  if (e.isComposing || e.keyCode === 229) {
    return
  }

  // if ((e.metaKey || e.ctrlKey) && e.key === 'Backspace') {
  //   emit('delete', selectedPath.value)
  // }
}

onMounted(async () => {
  window.addEventListener('keydown', globalHandleKeydown)
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', globalHandleKeydown)
})
</script>

<style scoped>
/* ------------------------
   Root
------------------------ */
.explorer-root {
  position: relative;

  height: 100%;

  display: flex;
  flex-direction: column;

  overflow: hidden;

  background-color: var(--apix-panel-layer-2-background);
  color: var(--apix-default-dark-color);

  flex-shrink: 0;

  border-radius: var(--apix-border-radius-base) 0 0 var(--apix-border-radius-base);
}

/* ------------------------
   Resize
------------------------ */
.resize-handle {
  position: absolute;

  top: 0;
  right: 0;

  width: 2px;
  height: 100%;

  cursor: ew-resize;

  z-index: 20;

  background-color: var(--apix-default-light-color);
  transition: background 0.15s ease;
}

.resize-handle:hover {
  background: var(--apix-primary-dark);
}

/* ------------------------
   Header
------------------------ */
.explorer-header {
  height: 38px;

  display: flex;
  align-items: center;
  justify-content: space-between;

  padding: 0 10px;

  flex-shrink: 0;

  border-bottom: .5px solid var(--apix-border-disabled);
}

.explorer-title {
  font-size: 13px;
  letter-spacing: 1px;
  font-weight: 700;

  color: var(--apix-default-dark-color);
}

/* ------------------------
   Workspace
------------------------ */
.workspace-label-wrapper {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-right: 10px;
}

.workspace-label {
  padding: 6px 12px;

  flex: 1;

  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;

  font-size: 13px;
  font-weight: 600;

  color: var(--apix-default-dark-color);
}

.workspace-label.empty_workspace {
  color: var(--apix-tertiary-dark-color);
}

.workspace-label-btn-wrapper {
  display: flex;
  gap: 3px;
}

/* ------------------------
   Tree
------------------------ */
.tree-container {
  flex: 1;

  overflow-y: auto;
  overflow-x: hidden;

  padding-bottom: 30px;
}

/* ------------------------
   Buttons
------------------------ */
.header-actions {
  display: flex;
  gap: 6px;
}

.icon-btn {
  display: flex;
  justify-content: center;
  align-items: center;

  width: 24px;
  height: 24px;

  border: none;
  border-radius: 4px;
  padding: 0;

  cursor: pointer;

  background: transparent;

  opacity: 0.3;
}

.explorer-header:hover .icon-btn {
  opacity: 1;
}

.icon-btn:hover {
  background: var(--apix-secondary-light-color);
}

.close-btn:hover {
  background: color-mix(in srgb, var(--apix-danger-color) 30%, transparent);
}

.icon-btn .icon {
  width: 16px;
  height: 16px;
}

.empty-btn-wrapper {
  position: relative;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  align-items: center;
  width: calc(100% - 2px);
  padding: 6px;
}

.open-btn {
  border-radius: 4px;
  width: 100%;
  padding: 2px 6px;
  background-color: var(--apix-primary-color);
  border: none;
  color: var(--apix-lightest-color);
}

.open-btn:hover {
  background-color: var(--apix-primary-hover);
}

.new-file-btn .icon {
  width: 17px;
  height: 17px;
}
</style>