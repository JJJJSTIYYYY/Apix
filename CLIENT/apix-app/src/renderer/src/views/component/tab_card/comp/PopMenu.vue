<template>
  <div class="popup-menu-wrapper" ref="wrapperRef">
    <div class="popup-content" :style="popupStyle">
      <button class="menu-item" @click="saveCard">
        <svg t="1778086407845" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="9974" width="20" height="20"><path d="M512 768l341.333333 149.333333v-213.333333h-58.660571v123.611429L512 703.975619 229.327238 827.66019V165.302857h565.345524v154.672762H853.333333V138.654476c0-17.65181-14.336-31.98781-32.01219-31.987809H202.703238C185.002667 106.666667 170.666667 121.002667 170.666667 138.678857v778.654476L512 768z" p-id="9975" fill="var(--apix-default-dark-color)"></path><path d="M818.663619 362.666667v120.003047H938.666667v58.660572h-120.003048v120.003047h-58.660571v-120.003047H640v-58.660572h120.003048v-120.003047h58.660571z" p-id="9976" fill="var(--apix-default-dark-color)"></path></svg>
        <span>存为预设</span>
      </button>
      <button class="menu-item" @click="markCard">
        <svg t="1778086454896" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="10188" width="20" height="20"><path d="M661.333333 426.666667a149.333333 149.333333 0 1 1-298.666666 0 149.333333 149.333333 0 0 1 298.666666 0z m-58.660571 0a90.672762 90.672762 0 1 0-181.345524 0 90.672762 90.672762 0 0 0 181.345524 0z" p-id="10189" fill="var(--apix-default-dark-color)"></path><path d="M853.333333 426.666667c0 231.18019-341.333333 512-341.333333 512S170.666667 657.846857 170.666667 426.666667c0-188.513524 152.81981-341.333333 341.333333-341.333334s341.333333 152.81981 341.333333 341.333334z m-58.660571 0c0-156.111238-126.537143-282.672762-282.672762-282.672762-156.111238 0-282.672762 126.537143-282.672762 282.672762 0 44.080762 16.579048 94.98819 46.201905 149.504 29.330286 53.906286 69.193143 107.203048 110.250667 154.916571A1537.926095 1537.926095 0 0 0 512 860.598857a1537.926095 1537.926095 0 0 0 126.22019-129.511619c41.057524-47.713524 80.920381-101.010286 110.250667-154.916571 29.622857-54.51581 46.201905-105.423238 46.201905-149.504z" p-id="10190" fill="var(--apix-default-dark-color)"></path></svg>
        <span>标记卡片</span>
      </button>
      <button class="menu-item" @click="markContent">
        <svg t="1778086514515" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="10402" width="20" height="20"><path d="M245.345524 288.01219h287.987809v245.321143H245.321143V287.98781z m58.660571 58.660572v128h170.666667v-128h-170.666667zM576 474.672762h202.678857v58.660571h-202.678857v-58.660571zM778.678857 640H245.345524v58.660571h533.308952V640z" p-id="10403" fill="var(--apix-default-dark-color)"></path><path d="M128 181.345524c0-17.67619 14.336-32.01219 32.01219-32.012191h704c17.65181 0 31.98781 14.336 31.98781 32.012191v661.333333c0 17.65181-14.336 31.98781-32.01219 31.98781H160.036571a31.98781 31.98781 0 0 1-32.01219-32.012191V181.369905z m58.660571 634.63619h650.678858V208.018286H186.660571V816.030476z" p-id="10404" fill="var(--apix-default-dark-color)"></path></svg>
        <span>标记内容</span>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'

// ------------------------
// 触发事件列表
// ------------------------
const emit = defineEmits<{
  (e: "close-menu"): void
  (e: "save-card"): void
  (e: "mark-card"): void
  (e: "mark-content"): void
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

function saveCard() {
  emit('save-card')
  emit('close-menu')
}

function markCard() {
  emit('mark-card')
  emit('close-menu')
}

function markContent() {
  emit('mark-content')
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
