<template>
  <div class="popup-menu-wrapper" ref="wrapperRef">
    <div class="popup-content" :style="popupStyle">
      <div class="title-btn"></div>
      <el-button v-if="type=='ai' || type=='human' || type=='tool'" class="action-btn" @click="copyValue">复制文本</el-button>
      <el-button v-if="type=='human'" class="action-btn" @click="reEdit">编辑消息</el-button>
      <el-button v-if="type=='ai'" class="action-btn" @click="reGenerate">重新生成</el-button>
      <el-button v-if="type=='ai' || type=='human' || type=='tool'" class="action-btn" @click="copyValue">选择文本</el-button>
      <el-button v-if="type=='tool'" class="action-btn" @click="copyValue">详细信息</el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'

const props = defineProps<{
  type: string // ai | human | tool
}>()



// ------------------------
// 触发事件列表
// ------------------------
const emit = defineEmits<{
  (e: "close-menu"): void
  (e: "copy-value"): void
  (e: "re-edit"): void
  (e: "re-generate"): void
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

function copyValue() {
  emit('copy-value')
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
</script>

<style scoped>
.popup-menu-wrapper {
  z-index: 9999;
  overflow: hidden;
  background: rgba(233, 233, 237, 0.081);
  border-radius: 12px;
  backdrop-filter: blur(12px);
  box-shadow: 0 4px 20px rgba(8, 25, 43, 0.182); /* 添加阴影 */
}

.popup-content {
  display: grid;
  gap: 6px;
  margin-top: -38px;
  background: rgba(255, 255, 255, 0.66);
  border-radius: 12px;
  box-shadow: 0 6px 20px rgba(0,0,0,0.08);
  padding: 6px;
  width: 120px;
  height: fit-content;
  overflow: hidden;
}

/* .popup-content::deep(.el-button:hover) {
  color: red;
} */

.title-btn {
  height: 32px;
  width: 100%;
  border-radius: 6px;
    /* 液态玻璃核心背景 */
  background: transparent;
  box-shadow: 
    0 8px 24px rgba(31, 38, 135, 0.15),
    inset 0 4px 16px rgba(255, 255, 255, 0.25);
}

.action-btn {
  height: 32px;
  width: 100%;
  color: rgba(16, 61, 71, 0.661);
  border-radius: 6px;
    /* 液态玻璃核心背景 */
  background: rgba(211, 211, 211, 0.15);
  backdrop-filter: blur(6px) saturate(180%);
  -webkit-backdrop-filter: blur(6px) saturate(180%);

  border: 1px solid rgba(255, 255, 255, 0.6);
  box-shadow: 
    0 8px 24px rgba(31, 38, 135, 0.15),
    inset 0 4px 16px rgba(255, 255, 255, 0.25);

  transition: transform 200ms cubic-bezier(0.2, 0.8, 0.2, 1),
}

.action-btn:hover {
  color: rgba(16, 61, 71, 0.661);
  transform: scale(1.05);
  box-shadow: 0 8px 28px rgba(235, 236, 246, 0.496);
}

.el-button+.el-button{
  margin: 0;
}

/* 针对特定组件或元素 */
.selectable {
  user-select: none !important;        /* 标准写法 */
  -webkit-user-select: text !important; /* Chromium 内核 */
  -moz-user-select: text !important;    /* Firefox */
  -ms-user-select: text !important;     /* IE/Edge */
}

</style>
