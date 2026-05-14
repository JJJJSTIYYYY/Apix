<template>
  <div class="popup-menu-wrapper" ref="wrapperRef">
    <div class="popup-content" :style="popupStyle">
      <button 
        class="menu-item"
        @click="copyValue('absolute')"
      >
        <span>复制路径</span>
      </button>

      <button 
        class="menu-item"
        @click="copyValue('relative')"
      >
        <span>复制相对路径</span>
      </button>

      <button 
        class="menu-item"
        @click="reEdit"
      >
        <span>打开文件的本地位置</span>
      </button>

      <button 
        class="menu-item"
        @click="reGenerate"
      >
        <span>新建文件</span>
      </button>

      <button 
        class="menu-item"
        @click="selectText"
      >
        <span>新建文件夹</span>
      </button>

      <button 
        class="menu-item danger-item"
        @click="deleteItem"
      >
        <span>删除</span>
      </button>

      <button 
        class="menu-item"
        @click="showDetail"
      >
        <span>压缩为技能包归档</span>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'

const props = defineProps<{
}>()

const emit = defineEmits<{
  (e: "close-menu"): void
  (e: "copy-value", type: string): void
  (e: "re-edit"): void
  (e: "re-generate"): void
  (e: "select-text"): void
  (e: "delete-item"): void
  (e: "show-detail"): void
}>()

const wrapperRef = ref<HTMLElement | null>(null)
const popupStyle = ref({})

const handleClickOutside = (e: MouseEvent) => {
  if (wrapperRef.value && !wrapperRef.value.contains(e.target as Node)) {
    emit('close-menu')
  }
}

onMounted(() => {
  window.addEventListener('mousedown', handleClickOutside)
})

onBeforeUnmount(() => {
  window.removeEventListener('mousedown', handleClickOutside)
})

function copyValue(type: string) {
  emit('copy-value', type)
  emit('close-menu')
}

function reEdit() {
  emit('re-edit')
  emit('close-menu')
}

function reGenerate() {
  emit('re-generate')
  emit('close-menu')
}

function selectText() {
  emit('select-text')
  emit('close-menu')
}

function deleteItem() {
  emit('delete-item')
  emit('close-menu')
}

function showDetail() {
  emit('show-detail')
  emit('close-menu')
}
</script>

<style scoped>
.popup-menu-wrapper {
  z-index: 999999;
  position: relative;
  transform-origin: left top;
}

.popup-content {
  display: flex;
  flex-direction: column;
  gap: 1px;
  padding: 6px;
  background: var(--apix-panel-layer-5-background);
  border-radius: var(--apix-border-radius-base);
  border: 1px solid var(--apix-default-light-color);
  box-shadow: var(--apix-shadow-layer-3);
  animation: menuEnter 0.18s var(--apix-cubic-bezier);
}

@keyframes menuEnter {
  from {
    opacity: 0;
    transform: scale(0.96) translateY(-2px);
  }
  to {
    opacity: 1;
    transform: scale(1) translateY(0);
  }
}

.menu-item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 8px 10px;
  border: none;
  border-radius: 7px;
  background: transparent;
  color: var(--apix-default-dark-color);
  font-size: 13px;
  font-weight: 450;
  cursor: pointer;
  transition: all 0.12s var(--apix-cubic-bezier);
  text-align: left;
  letter-spacing: 0.01em;
}

.menu-item:hover {
  background: var(--apix-default-light-color);
  color: var(--apix-default-dark-color);
}

.menu-item:active {
  background: var(--apix-secondary-light-color);
  transform: scale(0.985);
}

.danger-item {
  color: var(--apix-danger-color);
}

.danger-item:hover {
  background: color-mix(in srgb, var( --apix-danger-hover) 15%, transparent);
  color: var(--apix-danger-color);
}

.danger-item:active {
  background: color-mix(in srgb, var( --apix-danger-hover) 20%, transparent);
  transform: scale(0.985);
}

.icon {
  width: 15px;
  height: 15px;
  flex-shrink: 0;
  color: var(--apix-default-dark-color);
}

.menu-item:hover .icon {
  color: var(--apix-default-dark-color);
}
</style>