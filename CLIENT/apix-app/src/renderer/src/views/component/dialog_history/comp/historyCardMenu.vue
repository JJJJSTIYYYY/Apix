<template>
  <div class="popup-menu-wrapper" ref="wrapperRef">
    <div class="popup-content" :style="popupStyle">
      <button @click="rename" class="menu-item">重新命名</button>
      <button @click="connectProject" class="menu-item">工作目录</button>
      <button @click="deleteRecord" class="menu-item danger-item">删除记录</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'

const props = defineProps<{
  type: string
}>()



// ------------------------
// 触发事件列表
// ------------------------
const emit = defineEmits<{
  (e: "rename-history"): void
  (e: "delete-history"): void
  (e: "connect-project"): void
  (e: "close-menu"): void
}>()

const wrapperRef = ref(null)
const popupStyle = ref({})

const handleClickOutside = (e) => {
  if (!wrapperRef.value.contains(e.target)) {
    emit('close-menu')
  }
}

onMounted(() => {
  window.addEventListener('mousedown', handleClickOutside)
})

onBeforeUnmount(() => {
  window.removeEventListener('mousedown', handleClickOutside)
})

function rename() {
  emit('rename-history')
  emit('close-menu')
}

function deleteRecord() {
  emit('delete-history')
  emit('close-menu')
}

const connectProject = async () => {
  emit('connect-project')
  emit('close-menu')
}
</script>

<style scoped>
.popup-menu-wrapper {
  z-index: 999999;
  position: relative;
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