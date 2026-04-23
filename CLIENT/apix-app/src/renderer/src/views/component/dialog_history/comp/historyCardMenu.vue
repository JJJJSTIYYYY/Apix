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
  z-index: 9999;
  position: relative;
}

.popup-content {
  display: flex;
  flex-direction: column;
  gap: 1px;
  padding: 6px;
  background: #ffffff;
  border-radius: 10px;
  border: 1px solid rgba(0, 0, 0, 0.06);
  box-shadow: 
    0 1px 3px rgba(0, 0, 0, 0.04),
    0 8px 24px rgba(0, 0, 0, 0.06);
  animation: menuEnter 0.18s cubic-bezier(0.16, 1, 0.3, 1);
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
  color: #4b5563;
  font-size: 13px;
  font-weight: 450;
  cursor: pointer;
  transition: all 0.12s ease;
  text-align: left;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  letter-spacing: 0.01em;
}

.menu-item:hover {
  background: #f3f4f6;
  color: #1f2937;
}

.menu-item:active {
  background: #e5e7eb;
  transform: scale(0.985);
}

.danger-item {
  color: #d81e06;
}

.danger-item:hover {
  background: #ffe7e7;
  color: #c10808;
}

.danger-item:active {
  background: #f4c6c6;
  transform: scale(0.985);
}

.icon {
  width: 15px;
  height: 15px;
  flex-shrink: 0;
  color: #9ca3af;
  transition: color 0.12s ease;
}

.menu-item:hover .icon {
  color: #6b7280;
}
</style>