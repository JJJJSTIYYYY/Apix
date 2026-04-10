<template>
  <div class="popup-menu-wrapper" ref="wrapperRef">
    <div class="popup-content" :style="popupStyle">
      <div class="title-btn"></div>
      <el-button @click="rename" class="action-btn">重新命名</el-button>
      <el-button @click="deleteRecord" class="action-btn">删除记录</el-button>
      <el-button @click="connectProject" class="action-btn">关联项目</el-button>
      <!-- <el-button @click="reGenerate">重新生成</el-button>
      <el-button @click="copyValue">选择文本</el-button>
      <el-button @click="copyValue">详细信息</el-button> -->
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
  z-index: 99999;
  overflow: hidden;
  background: rgba(242, 242, 243, 0.8);
  border-radius: 12px;
  box-shadow: 0 4px 20px rgba(8, 25, 43, 0.182); /* 添加阴影 */
  backdrop-filter: blur(24px);
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
    0 8px 24px rgba(103, 104, 126, 0.15),
    inset 0 4px 16px rgba(255, 255, 255, 0.25);
}

.action-btn {
  height: 32px;
  width: 100%;
  color: rgba(16, 61, 71, 0.661);
  border-radius: 6px;
    /* 液态玻璃核心背景 */
  background: rgba(211, 211, 211, 0.361);
  backdrop-filter: blur(6px) saturate(180%);
  -webkit-backdrop-filter: blur(6px) saturate(180%);

  border: 1px solid rgba(255, 255, 255, 0.6);
  box-shadow: 
    0 8px 24px rgba(94, 97, 133, 0.15),
    inset 0 4px 16px rgba(255, 255, 255, 0.25);

  transition: all 300ms cubic-bezier(0.8, 0.8, 0.2, 1);
}

.action-btn:hover {
  transform: scale(1.05);
  transition: all 300ms cubic-bezier(0.8, 3.8, 0.2, 1);
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
