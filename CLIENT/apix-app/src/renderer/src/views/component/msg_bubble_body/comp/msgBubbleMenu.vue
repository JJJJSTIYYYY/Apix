<template>
  <div class="popup-menu-wrapper" ref="wrapperRef">
    <div class="popup-content" :style="popupStyle">
      <button 
        v-if="type === 'ai' || type === 'human' || type === 'tool'" 
        class="menu-item"
        @click="copyValue"
        tabindex="0"
      >
        <svg t="1776756262130" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="10157" width="20" height="20"><path d="M585.142857 365.714286a73.142857 73.142857 0 0 1 73.142857 73.142857v390.095238a73.142857 73.142857 0 0 1-73.142857 73.142857H195.047619a73.142857 73.142857 0 0 1-73.142857-73.142857V438.857143a73.142857 73.142857 0 0 1 73.142857-73.142857h390.095238z m0 73.142857H195.047619v390.095238h390.095238V438.857143z m-73.142857 219.428571v73.142857H268.190476v-73.142857h243.809524zM828.952381 121.904762a73.142857 73.142857 0 0 1 73.142857 73.142857v390.095238a73.142857 73.142857 0 0 1-73.142857 73.142857h-121.904762v-73.142857h121.904762V195.047619H438.857143v121.904762h-73.142857V195.047619a73.142857 73.142857 0 0 1 73.142857-73.142857h390.095238zM512 536.380952v73.142858H268.190476v-73.142858h243.809524z" p-id="10158" fill="var(--apix-default-dark-color)"></path></svg>
        <span>复制文本</span>
      </button>

      <button 
        v-if="type === 'human'" 
        class="menu-item"
        @click="reEdit"
      >
        <svg t="1776756230407" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="9832" width="20" height="20"><path d="M720.042667 170.666667v73.142857H195.047619v536.380952h585.142857V512h73.142857v268.190476a73.142857 73.142857 0 0 1-73.142857 73.142857H195.047619a73.142857 73.142857 0 0 1-73.142857-73.142857V243.809524a73.142857 73.142857 0 0 1 73.142857-73.142857h524.995048z m156.281904 27.696762l51.541334 51.882666-392.825905 390.046476-53.101714 1.950477 1.511619-54.028191 392.874666-389.851428z" p-id="9833" fill="var(--apix-default-dark-color)"></path></svg>
        <span>编辑消息</span>
      </button>

      <button 
        v-if="type === 'ai'" 
        class="menu-item"
        @click="reGenerate"
      >
        <svg t="1776756159421" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="9391" width="20" height="20"><path d="M899.072 463.238095c1.999238 15.969524 3.023238 32.256 3.023238 48.761905 0 215.454476-174.640762 390.095238-390.095238 390.095238-103.862857 0-198.265905-40.594286-268.190476-106.788571V902.095238H170.666667l0.024381-170.666667L170.666667 658.285714h243.809523v73.142857h-131.169523c57.685333 60.123429 138.825143 97.52381 228.693333 97.52381 175.055238 0 316.952381-141.897143 316.952381-316.952381a319.390476 319.390476 0 0 0-3.730286-48.761905h73.874286zM853.333333 121.904762l-0.024381 170.666667L853.333333 365.714286H609.52381v-73.142857h131.193904A316.025905 316.025905 0 0 0 512 195.047619C336.944762 195.047619 195.047619 336.944762 195.047619 512c0 16.579048 1.26781 32.889905 3.730286 48.761905h-73.874286A393.947429 393.947429 0 0 1 121.904762 512c0-215.454476 174.640762-390.095238 390.095238-390.095238 103.862857 0 198.290286 40.618667 268.190476 106.812952V121.904762h73.142857z" p-id="9392" fill="var(--apix-default-dark-color)"></path></svg>
        <span>重新生成</span>
      </button>

      <button 
        v-if="type === 'ai' || type === 'human' || type === 'tool'" 
        class="menu-item"
        @click="selectText"
      >
        <svg t="1776756072764" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="9118" width="20" height="20"><path d="M755.809524 182.857143V316.952381h-73.142857v-60.952381h-207.238096V804.571429H560.761905v73.142857H316.952381v-73.142857h85.333333V256h-219.428571V316.952381h-73.142857V182.857143H755.809524zM902.095238 804.571429v73.142857H609.52381v-73.142857h292.571428z m0-146.285715v73.142857H609.52381v-73.142857h292.571428z m0-146.285714v73.142857H609.52381v-73.142857h292.571428z" p-id="9119" fill="var(--apix-default-dark-color)"></path></svg>
        <span>选择文本</span>
      </button>

      <button 
        v-if="type === 'ai' || type === 'human' || type === 'tool'" 
        class="menu-item danger-item"
        @click="deleteItem"
      >
        <svg t="1776755725116" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="8731" width="20" height="20"><path d="M328.777143 377.904762l31.719619 449.657905h310.662095l31.695238-449.657905h73.264762L744.106667 832.707048a73.142857 73.142857 0 0 1-72.94781 67.998476H360.496762a73.142857 73.142857 0 0 1-72.94781-68.022857L255.488 377.904762h73.289143z m159.207619 22.649905v341.333333h-73.142857v-341.333333h73.142857z m133.729524 0v341.333333h-73.142857v-341.333333h73.142857zM146.285714 256h731.428572v73.142857H146.285714v-73.142857z m518.265905-121.904762v73.142857h-292.571429v-73.142857h292.571429z" p-id="8732" fill="var(--apix-danger-color)"></path></svg>
        <span>删除记录</span>
      </button>

      <button 
        v-if="type === 'tool'" 
        class="menu-item"
        @click="showDetail"
      >
        <svg t="1776756287595" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="10490" width="20" height="20"><path d="M512 97.52381c228.912762 0 414.47619 185.563429 414.47619 414.47619s-185.563429 414.47619-414.47619 414.47619S97.52381 740.912762 97.52381 512 283.087238 97.52381 512 97.52381z m0 73.142857C323.486476 170.666667 170.666667 323.486476 170.666667 512s152.81981 341.333333 341.333333 341.333333 341.333333-152.81981 341.333333-341.333333S700.513524 170.666667 512 170.666667z m36.571429 268.190476v292.571428h-73.142858V438.857143h73.142858z m0-121.904762v73.142857h-73.142858v-73.142857h73.142858z" p-id="10491" fill="var(--apix-default-dark-color)"></path></svg>
        <span>详细信息</span>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'

const props = defineProps<{
  type: string // ai | human | tool
}>()

const emit = defineEmits<{
  (e: "close-menu"): void
  (e: "copy-value"): void
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
.popup-menu-wrapper :deep(*:focus-visible) {
  outline: 2px solid var(--apix-primary-color) !important;
  outline-offset: 2px;
}

.popup-menu-wrapper {
  z-index: 999999;
  position: relative;
}

.popup-content {
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 105px;
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