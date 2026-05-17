<template>
  <div class="popup-menu-wrapper" ref="wrapperRef">
    <div class="popup-content" :style="popupStyle">
      <button 
        class="menu-item"
        @click="deleteItem('self')"
      >
        <span>关闭</span>
      </button>

      <button 
        class="menu-item"
        @click="deleteItem('others')"
      >
        <span>关闭其它</span>
      </button>

      <button 
        class="menu-item"
        @click="deleteItem('left')"
      >
        <span>关闭左侧标签页</span>
      </button>

      <button 
        class="menu-item"
        @click="deleteItem('right')"
      >
        <span>关闭右侧标签页</span>
      </button>

      <button 
        class="menu-item"
        @click="deleteItem('saved')"
      >
        <span>关闭已保存</span>
      </button>

      <div class="hr"></div>

      <button 
        class="menu-item"
        @click="copyPath('name')"
      >
        <span>复制文件名</span>
      </button>

      <button 
        class="menu-item"
        @click="copyPath('absolute')"
      >
        <span>复制路径</span>
      </button>

      <button 
        class="menu-item"
        @click="copyPath('relative')"
      >
        <span>复制相对路径</span>
      </button>

      <div class="hr"></div>

      <button 
        class="menu-item"
        @click="openInlocal"
      >
        <span>打开文件的本地位置</span>
      </button>

      <div class="hr"></div>

      <button 
        class="menu-item"
        @click="pinTab"
      >
        <span>固定标签页</span>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'

const props = defineProps<{
}>()

const emit = defineEmits<{
  (e: "close-menu", type): void
  (e: "copy-path", type: string): void
  (e: "open-in-local"): void
  (e: "close-item"): void
  (e: "pin-tab"): void
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

function copyPath(type: string) {
  emit('copy-path', type)
  emit('close-menu')
}

function openInlocal() {
  emit('open-in-local')
  emit('close-menu')
}

function pinTab() {
  emit('pin-tab')
  emit('close-menu')
}

function deleteItem(type: string) {
  emit('close-item', type)
  emit('close-menu')
}

function compressToSkill() {
  emit('compress-skill')
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
  background: color-mix(in srgb, var(--apix-danger-hover) 15%, transparent);
  color: var(--apix-danger-color);
}

.danger-item:active {
  background: color-mix(in srgb, var(--apix-danger-hover) 20%, transparent);
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

.hr {
  align-self: center;
  height: 1px;
  width: 95%;
  background-color: var(--apix-default-light-color);
}
</style>