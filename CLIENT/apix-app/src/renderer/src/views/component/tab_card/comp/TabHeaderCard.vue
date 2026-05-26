<template>
  <div
    :title="tab.tabKey"
    :data-tab-key="tab.tabKey"
    class="editor-tab"
    :class="{
      active: active,
      deleted: tab.status === 'deleted',
      outdated: tab.status === 'outdated'
    }"
    draggable="true"
    @click="$emit('change-tab', tab)"
    @auxclick="$emit('middle-click', tab)"
    @dragstart="$emit('drag-start')"
    @dragover.prevent
    @drop="$emit('drop')"
    @contextmenu.prevent="onContextMenu"
  >
    <!-- Unsaved dot -->
    <div
      v-if="tab.saved === false"
      class="tab-unsaved-dot"
    />

    <!-- Icon -->
    <div
      class="icon-wrapper"
      v-html="getSupportFileSVG(tab.tabKey)"
    />

    <!-- Title -->
    <span class="tab-title">
      {{ tab.title }}
    </span>

    <!-- Close -->
    <div
      v-if="!tab.pinned"
      class="tab-close"
      draggable="false"
      @click.stop="$emit('close-tab', tab)"
    >
      <svg
        t="1778579309106"
        class="icon"
        viewBox="0 0 1024 1024"
        version="1.1"
        xmlns="http://www.w3.org/2000/svg"
        p-id="7164"
        width="20"
        height="20"
      >
        <path
          d="M140.5 960L64 883.5 441 512 64 140.5 140.5 64 512 441 883.5 64l76.5 76.5L583 512l377 371.5-76.5 76.5L512 583 140.5 960z"
          p-id="7165"
        />
      </svg>
    </div>
    <div
      v-else
      class="tab-close tab-pinned"
    >
      <svg t="1779009255670" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="6810" width="32" height="32"><path d="M271.475 86.033c0 26.929 6.12 52.022 18.361 75.279s29.377 43.454 51.41 60.59v198.295c-44.066 19.585-78.339 48.962-102.82 88.131a529.122 529.122 0 0 0-25.705 60.59c-7.344 20.809-11.016 43.454-11.016 67.934v33.049h275.41v220.328L513.836 960l33.049-69.771V669.902h275.41v-33.049c0-24.481-3.06-47.738-9.18-69.771s-15.301-42.229-27.541-60.59c-12.24-18.361-26.929-34.885-44.066-49.574-17.137-14.689-36.721-26.929-58.754-36.721V221.902c24.481-17.137 42.229-37.333 53.246-60.59s16.525-48.35 16.525-75.279V64h-481.05v22.033z m407.607 33.049c-2.448 7.344-6.12 14.689-11.016 22.033l-14.688 18.361c-4.896 4.896-11.016 8.568-18.361 11.016l-18.361 14.689v282.754l22.033 7.344c29.377 9.792 53.858 25.705 73.443 47.738 9.792 9.792 18.361 23.869 25.705 42.229s12.24 34.885 14.689 49.574H271.475c2.448-14.689 7.956-31.213 16.525-49.574s17.749-32.437 27.541-42.229c19.585-22.033 42.842-37.945 69.77-47.738l25.705-7.344V185.18l-22.033-14.689c-12.24-7.344-23.257-17.137-33.049-29.377l-11.016-22.033h334.164z" p-id="6811"></path></svg>
    </div>

    <!-- Menu -->
    <transition name="scale-fade">
      <TabHeaderMenu
        v-if="isShowMenu"
        ref="menuRef"
        :style="menuStyle"
        @close-menu="closePopMenu"
        @click.stop
        @copy-path="(type) => $emit('copy-path', type, tab)"
        @open-in-local="$emit('open-in-local', tab)"
        @close-item="(type) => $emit('close-item', type, tab)"
        @pin-tab="$emit('pin-tab', tab)"
      />
    </transition>
  </div>
</template>

<script setup lang="ts">
import { nextTick, ref } from 'vue'
import TabHeaderMenu from './TabHeaderMenu.vue'
import { getSupportFileSVG } from '../../../../store/globalData'

interface TabItem {
  tabKey: string
  title: string
  saved?: boolean
  status?: string
  pinned?: boolean
}

defineProps<{
  tab: TabItem
  active: boolean
}>()

defineEmits<{
  (e: 'change-tab', tab: TabItem): void
  (e: 'middle-click', tab: TabItem): void
  (e: 'drag-start'): void
  (e: 'drop'): void
  (e: 'close-tab', tab: TabItem): void
  (e: 'copy-path', type: string, tab: TabItem): void
  (e: 'open-in-local', tab: TabItem): void
  (e: 'close-item', tab: TabItem): void
  (e: 'pin-tab', tab: TabItem): void
}>()

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
/* Tab item */
.editor-tab {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;

  height: 38px;
  min-width: 100px;
  max-width: 220px;
  flex-shrink: 0;

  padding: 0 3px 0 8px;

  overflow: hidden;
  background-color: var(--apix-panel-layer-2-background);
  border: none;
  border-right: 1px solid var(--apix-default-light-color);
  color: var(--apix-secondary-dark-color);

  border-radius: 0;
  user-select: none;
  cursor: pointer;

  transition: none;
  animation: scaleFade-tab-wrapper 0.4s var(--apix-cubic-bezier);
}

.editor-tab:hover {
  background-color: var(--apix-panel-layer-0-background);
}

.editor-tab.active {
  background-color: var(--apix-panel-layer-5-background);
  color: var(--apix-primary-active);
}

.editor-tab.deleted .tab-title {
  text-decoration: line-through;
  opacity: 0.65;
}

.editor-tab.outdated .tab-title {
  opacity: 0.75;
  color: var(--apix-warning-button-active);
}

/* Title */
.tab-title {
  min-width: 0;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

/* Unsaved dot */
.tab-unsaved-dot {  
  width: 7px;
  height: 7px;
  margin-right: 6px;
  border-radius: 999px;
  background: var(--apix-primary-active);
  flex-shrink: 0;
}

.icon-wrapper {
  display: flex;
  width: 18px;

  margin-right: 4px;

  text-align: center;
  justify-content: center;

  font-size: 13px;
}

.icon-wrapper:deep(.icon) {
  width: 15px;
  height: 15px;
}

/* Close button */
.tab-close {
  display: flex;
  align-items: center;
  justify-content: center;

  width: 18px;
  height: 18px;
  margin-left: 6px;

  border-radius: 4px;
  opacity: 0;
  transition: none;
  flex-shrink: 0;
}

.tab-pinned {
  opacity: 0.6;
}

.editor-tab:hover .tab-close {
  opacity: 1;
}

.tab-close:hover {
  background-color: var(--apix-lightest-color);
}

.tab-close:deep(.icon) {
  width: 10px;
  height: 10px;
  fill: var(--apix-secondary-dark-color);
}

.tab-pinned:deep(.icon) {
  width: 16px;
  height: 16px;
}

/* Optional drag state */
.editor-tab:active {
  cursor: grabbing;
}

/* Content area */
.editor-tabs-content {
  flex: 1;
  min-height: 0;
}

.editor-tab-pane {
  height: 100%;
}

/* Tab enter animation */
@keyframes scaleFade-tab-wrapper {
  0% {
    opacity: 0;
  }

  100% {
    opacity: 1;
  }
}
/* --- */

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