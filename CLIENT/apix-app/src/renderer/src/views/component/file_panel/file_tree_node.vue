<template>
  <div
    @contextmenu.prevent="onContextMenu"
  >

    <!-- Row -->
    <div
      class="tree-node"
      :class="{
        selected: selectedPath === node.path
      }"
      :style="{
        paddingLeft: `${depth * 8 + 4}px`,
        paddingRight: '6px'
      }"
      @click.stop="onClick"
    >

      <!-- Arrow -->
      <div
        class="arrow"
        :class="{
          expanded: node.expanded
        }"
      >
        <svg v-if="node.type === 'directory'" t="1778344377725" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="13026" width="16" height="16"><path d="M703.48 522.47l-243.21-213.6c-23.08-20.27-59.29-3.88-59.29 26.84v427.2c0 30.72 36.21 47.11 59.29 26.84l243.21-213.6c16.2-14.23 16.2-39.45 0-53.67z" fill="var(--apix-secondary-dark-color)" p-id="13027"></path></svg>
      </div>

      <!-- Icon -->
      <div class="icon-wrapper">
        <svg v-if="node.type === 'directory'" t="1778343244907" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="8542" width="20" height="20"><path d="M453.315048 146.285714a73.142857 73.142857 0 0 1 71.411809 57.295238l3.535238 15.847619H828.952381a73.142857 73.142857 0 0 1 73.142857 73.142858v512a73.142857 73.142857 0 0 1-73.142857 73.142857H195.047619a73.142857 73.142857 0 0 1-73.142857-73.142857V219.428571a73.142857 73.142857 0 0 1 73.142857-73.142857h258.267429z m0 73.142857H195.047619v585.142858h633.904762V414.47619H496.688762l-43.373714-195.047619zM780.190476 658.285714v73.142857H243.809524v-73.142857h536.380952z m48.761905-365.714285H544.49981l10.849523 48.761904H828.952381v-48.761904z" fill="var(--apix-secondary-dark-color)" p-id="8543"></path></svg>
        <svg v-else t="1778344738953" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="9209" width="16" height="16"><path d="M170.666667 219.428571h682.666666V146.285714H170.666667v73.142857z m0 219.428572h487.619047v-73.142857H170.666667v73.142857z m0 219.428571h292.571428v-73.142857H170.666667v73.142857z m0 219.428572h682.666666v-73.142857H170.666667v73.142857z" fill="var(--apix-secondary-dark-color)" p-id="9210"></path></svg>
      </div>

      <!-- Name -->
      <div class="label">
        {{ node.name }}
      </div>

    </div>

    <!-- Children -->
    <Transition name="expand">
      <div
        v-if="
          node.type === 'directory'
          &&
          node.expanded
        "
      >
        <div
          v-if="node.is_creating"
          class="input-node"
          :style="{
            paddingLeft: `${(depth + 1) * 8 + 4}px`,
            paddingRight: '6px'
          }"
        >
          <div class="icon-wrapper">
            <svg v-if="node.creating_type === 'directory'" t="1778343244907" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="8542" width="20" height="20"><path d="M453.315048 146.285714a73.142857 73.142857 0 0 1 71.411809 57.295238l3.535238 15.847619H828.952381a73.142857 73.142857 0 0 1 73.142857 73.142858v512a73.142857 73.142857 0 0 1-73.142857 73.142857H195.047619a73.142857 73.142857 0 0 1-73.142857-73.142857V219.428571a73.142857 73.142857 0 0 1 73.142857-73.142857h258.267429z m0 73.142857H195.047619v585.142858h633.904762V414.47619H496.688762l-43.373714-195.047619zM780.190476 658.285714v73.142857H243.809524v-73.142857h536.380952z m48.761905-365.714285H544.49981l10.849523 48.761904H828.952381v-48.761904z" fill="var(--apix-secondary-dark-color)" p-id="8543"></path></svg>
            <svg v-else t="1778344738953" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="9209" width="16" height="16"><path d="M170.666667 219.428571h682.666666V146.285714H170.666667v73.142857z m0 219.428572h487.619047v-73.142857H170.666667v73.142857z m0 219.428571h292.571428v-73.142857H170.666667v73.142857z m0 219.428572h682.666666v-73.142857H170.666667v73.142857z" fill="var(--apix-secondary-dark-color)" p-id="9210"></path></svg>
          </div>
          <input 
            id="file-tree-node-create-input"
            class="file-tree-node-create-input"
            v-model="inputValue"
            type="text"
            @keydown="handleInputKeydown"
          />
        </div>

        <TreeNode
          v-for="child in node.children"
          :key="child.path"
          :node="child"
          :depth="depth + 1"
          :selected-path="selectedPath"
          @toggle="$emit('toggle', $event)"
          @select="$emit('select', $event)"
          @create="(...args) => $emit('create', ...args)"
          @hide-all-input="(...args) => $emit('hideAllInput', ...args)"
        />
      </div>
    </Transition>

    <transition name="scale-fade">
      <fileNodeMenu
        v-if="isShowMenu"
        ref="menuRef"
        :style="menuStyle"
        @close-menu="closePopMenu"
        @click.stop
      />
    </transition>
  </div>
</template>

<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'
import TreeNode from './file_tree_node.vue'
import fileNodeMenu from './comp/fileNodeMenu.vue'

// ------------------------
// Props
// ------------------------
export interface NodeBase {
  name: string
  path: string
  type: string
  children: NodeBase[]
  expanded?: Boolean
  is_creating?: Boolean
  creating_type?: string
}

const props = defineProps<{
  node: NodeBase
  depth?: Number
  selectedPath?: string
}>()

const emit = defineEmits([
  'toggle',
  'select',
  'wantToCreate',
  'create',
  'hideAllInput'
])

// ------------------------
// Click
// ------------------------
function onClick() {
  emit('select', props.node)

  if (props.node.type === 'directory') {
    emit('toggle', props.node)
  }
}

// ------------------------
// Input
// ------------------------
const inputValue = ref('')

function handleInputKeydown(e) {
  if (e.isComposing || e.keyCode === 229) {
    return
  }
  console.log('[handleInputKeydown]', props.node.path)
  if (e.key === 'Enter') {
    emit("hideAllInput", props.node.path)
  }
}

watch(
  () => props.node.is_creating,
  async (newValue, oldValue) => {
    if (newValue === oldValue) return

    if (!newValue && props.node.type === 'directory') {
      await nextTick()
      console.log('[watch] inputValue: ', inputValue.value, '. Creating: ', props.node.creating_type)
      let file_name = inputValue.value
      if (props.node.creating_type === 'file') {
        if (!file_name.endsWith(".md") && !file_name.endsWith(".aflow")) file_name += '.aflow'
        emit("create", props.node.path, file_name, 'file')
      }
      else {
        emit("create", props.node.path, file_name, 'directory')
      }

      inputValue.value = ''
    }
    else if (newValue && props.node.type === 'directory') {
      await nextTick()
      document.getElementById('file-tree-node-create-input').focus();
    }
  }
)

// -----------------
// Menu
// -----------------
const isShowMenu = ref(false)
const menuStyle = ref<Record<string, string>>({})
const menuRef = ref<any>(null)

const menuWidthGuess = 144
const menuHeightGuess = 120

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
</script>

<style scoped>
.input-node,
.tree-node {
  height: 24px;

  color: var(--apix-secondary-dark-color);

  display: flex;
  align-items: center;
  justify-content: center;

  cursor: pointer;

  user-select: none;

  transition: background 0.12s ease;
}

.tree-node:hover {
  color: var(--apix-default-dark-color);
  background: var(--apix-default-light-color);
}

.tree-node.selected {
  color: var(--apix-default-dark-color);
  border-left: .5px solid var(--apix-lightest-color);
  background: var(--apix-default-light-color);
}

.tree-node .icon {
  fill: var(--apix-secondary-dark-color);
}

.tree-node:hover .icon,
.tree-node.selected .icon {
  fill: var(--apix-default-dark-color);
}

/* ------------------------
   Arrow
------------------------ */
.arrow {
  display: flex;
  justify-content: center;

  width: 16px;

  font-size: 10px;

  transition: transform 0.12s ease;
}

.arrow.expanded {
  transform: rotate(90deg);
}

/* ------------------------
   Icon
------------------------ */
.icon-wrapper {
  display: flex;
  width: 18px;

  margin-right: 4px;

  text-align: center;
  justify-content: center;

  font-size: 13px;
}

/* ------------------------
   Label
------------------------ */
.label {
  flex: 1;

  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;

  font-size: 13px;
}

/* ------------------------
   Expand
------------------------ */
.expand-enter-active,
.expand-leave-active {
  transition:
    opacity 0.15s ease,
    transform 0.15s ease;
}

.expand-enter-from,
.expand-leave-to {
  opacity: 0;
  transform: translateY(-2px);
}

/* ------------------------
   Input
------------------------ */
.file-tree-node-create-input {
  outline: none;
  background: transparent;
  font-family: inherit;
  color: inherit;
  -webkit-appearance: none;
  appearance: none;
  
  flex: 1;
  font-size: 13px;
  box-sizing: border-box;
  border: 1px solid var(--apix-primary-color);
  border-radius: 6px;
  background-color: transparent;
}

.file-tree-node-create-input:active {
  border: 1px solid var(--apix-primary-color);
}

.file-tree-node-create-input:focus {
  outline: none;
  border: 1px solid var(--apix-primary-color);
}

/* ------------------------
Menu animation
------------------------ */
.scale-fade-enter-active {
  animation: scaleFadeIn 0.35s var(--apix-cubic-bezier);
}
.scale-fade-leave-active {
  animation: scaleFadeOut 0.2s var(--apix-cubic-bezier);
}
@keyframes scaleFadeIn {
  0% { opacity: 0; transform: scale(0.9); }
  100% { opacity: 1; transform: scale(1); }
}
@keyframes scaleFadeOut {
  0% { opacity: 1; transform: scale(1); }
  100% { opacity: 0; transform: scale(0.95); }
}
</style>