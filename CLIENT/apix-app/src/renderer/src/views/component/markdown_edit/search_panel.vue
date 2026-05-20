<template>
  <div
    v-show="visible"
    class="search-panel"
    :class="{panel_expanded: expandPanel}"
  >
    <button
      class="expand-btn"
      :class="{panel_expanded: expandPanel}"
      @click="triggerExpand"
    >
      <svg t="1778581397713" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="5886" width="20" height="20"><path d="M121.5 274.8L64 332.3l421.6 416.9h52.7l421.6-416.9-57.5-57.5-388.1 392.9-392.8-392.9z" p-id="5887"></path></svg>
    </button>

    <!-- Search input -->
    <input
      ref="searchInputRef"
      :value="searchText"
      class="search-input"
      type="text"
      placeholder="搜索"
      @input="onSearchInput"
      @keydown.enter.prevent="emitNext"
    >

    <!-- Match case -->
    <button
      class="search-btn case-btn"
      :class="{ active: caseSensitive }"
      title="匹配大小写"
      @click="emit('update:caseSensitive', !caseSensitive)"
    >
      <svg t="1778579208122" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="6312" width="20" height="20"><path d="M357.236 212.655H288L64 799.127h73.309L198.4 636.218h248.436l61.091 162.909h77.382L357.236 212.655zM218.764 575.127l93.673-252.509c2.715-8.145 5.43-20.364 8.145-36.655h4.073c2.715 16.291 5.43 28.509 8.145 36.655l89.6 252.509H218.764zM960 526.255c0-103.176-48.873-154.764-146.618-154.764-54.303 0-101.818 13.576-142.545 40.727v65.164c40.727-32.582 85.527-48.873 134.4-48.873 57.018 0 85.527 35.297 85.527 105.891l-126.255 16.291c-92.315 13.576-138.473 59.733-138.473 138.473 0 38.012 12.218 67.879 36.655 89.6 24.436 21.721 57.018 32.582 97.745 32.582 57.018 0 100.461-25.794 130.327-77.382v65.164H960V526.255z m-69.236 105.89c0 35.297-10.861 64.485-32.582 87.564s-48.873 34.618-81.455 34.618c-24.436 0-44.121-6.788-59.055-20.364s-22.4-29.867-22.4-48.873c0-29.867 8.145-50.23 24.436-61.091 16.291-10.861 40.727-17.648 73.309-20.364l97.745-16.291v44.801z" p-id="6313"></path></svg>
    </button>

    <!-- Match case -->
    <button
      class="search-btn whole-btn"
      :class="{ active: wholeWord }"
      title="全词匹配"
      @click="emit('update:wholeWord', !wholeWord)"
    >
      <svg t="1778589554360" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="6525" width="20" height="20"><path d="M64 822.6h896V655.3h-56.7v113.5H120.7V655.3H64v167.3z m382.3-367.3c0-75.7-35.8-113.5-107.5-113.5s-74.7 9-104.5 26.9v50.8c29.9-23.9 62.7-35.8 98.6-35.8s65.7 25.9 65.7 77.7L306 473.3c-67.7 10-101.5 43.8-101.5 101.5s8.5 47.3 25.4 64.2c16.9 16.9 41.3 25.4 73.2 25.4s72.7-18.9 92.6-56.7h3v47.8h47.8V455.4z m-47.8 74.6c0 27.9-8 50.3-23.9 67.2-15.9 16.9-36.8 25.4-62.7 25.4s-31.9-5-41.8-14.9-14.9-21.9-14.9-35.8c0-21.9 5.5-36.8 16.4-44.8 11-8 28.4-12.9 52.3-14.9l74.7-11.9v29.9z m188.2 80.7c21.9 35.8 53.8 53.8 95.6 53.8s75.2-15.4 100.1-46.3c24.9-30.9 37.3-72.2 37.3-123.9s-11-85.1-32.9-112c-21.9-26.9-52.8-40.3-92.6-40.3s-83.6 19.9-107.5 59.7V201.5h-50.8v454h50.8v-44.8z m0-122.5c0-29.9 8.5-54.8 25.4-74.7 16.9-19.9 39.3-29.9 67.2-29.9s49.8 9.5 65.7 28.4c15.9 18.9 23.9 45.3 23.9 79.1s-8.5 74.2-25.4 97.1-40.3 34.3-70.2 34.3-46.8-9-62.7-26.9c-15.9-17.9-23.9-39.8-23.9-65.7V488z" p-id="6526"></path></svg>
    </button>

    <!-- Regex -->
    <button
      class="search-btn regex-btn"
      :class="{ active: regexp }"
      title="正则表达式"
      @click="emit('update:regexp', !regexp)"
    >
      <svg t="1778579234068" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="6525" width="20" height="20"><path d="M661.3 299L470.2 183.5l-35.8 63.7 191.1 115.5-191.1 119.5 35.8 63.7 191.1-115.5v231H733v-231l191.1 115.5 35.8-63.7-191.1-119.5 191.1-115.5-35.8-63.7L733 299V64h-71.7v235zM64 960h298.7V661.3H64V960z" p-id="6526"></path></svg>
    </button>

    <div class="index-wrapper">
      <span>
        第 {{ currentMatch ?? 'N' }} 项, 共 {{ totalMatch ?? 'N' }} 项
      </span>
    </div>

    <!-- Prev -->
    <button
      class="search-btn prev-btn"
      @click="emitPrev"
      title="上一个"
    >
      <svg t="1778581417449" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="6099" width="20" height="20"><path d="M856.5 494.1L549.9 183.5V960h-75.7V183.5L163.6 494.1l-51.8-55.8L486.1 64h51.8l374.3 374.3-55.8 55.8z" p-id="6100"></path></svg>
    </button>

    <!-- Next -->
    <button
      class="search-btn next-btn"
      @click="emitNext"
      title="下一个"
    >
      <svg t="1778581430132" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="6312" width="20" height="20"><path d="M163.6 533.9l310.6 310.6V64h75.7v780.5l310.6-310.6 51.8 55.8L538 960h-51.8L111.8 589.7l51.8-55.8z" p-id="6313"></path></svg>
    </button>

    <!-- Close -->
    <button
      class="search-btn close-btn"
      @click="emit('close')"
    >
      <svg t="1778579309106" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="7164" width="20" height="20"><path d="M140.5 960L64 883.5 441 512 64 140.5 140.5 64 512 441 883.5 64l76.5 76.5L583 512l377 371.5-76.5 76.5L512 583 140.5 960z" p-id="7165"></path></svg>
    </button>

    <!-- Replace input -->
    <input
      ref="replaceInputRef"
      :value="replaceText"
      class="search-input"
      type="text"
      placeholder="替换"
      @input="onReplaceInput"
      v-if="expandPanel"
    >

    <!-- Replace -->
    <button
      class="search-btn rep-btn"
      @click="emit('replace-one')"
      v-if="expandPanel"
      title="替换选中"
    >
      <svg t="1778579133770" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="5886" width="20" height="20"><path d="M284.6 194l68.4 68.4V159.8c0-27.4 9.1-50.2 27.4-68.4 18.2-18.2 41-27.4 68.4-27.4h95.8v61.6h-99.2c-6.8 0-13.7 3.4-20.5 10.3-6.8 6.8-10.3 14.8-10.3 23.9v102.6l65-65 44.5 44.5-140.2 143.6-147.1-147.1 47.9-44.5z m379.6 184.6h-54.7V64h54.7l3.4 133.4c13.7-25.1 33.1-37.6 58.1-37.6s43.9 9.7 56.4 29.1 18.8 46.2 18.8 80.4-7.4 61.6-22.2 82.1c-14.8 20.5-34.2 31.3-58.1 32.5s-41.6-8.5-53-29.1h-3.4v23.9z m0-92.3c0 11.4 3.4 22.2 10.3 32.5 6.8 10.3 16.5 15.4 29.1 15.4s22.2-5.7 29.1-17.1c6.8-11.4 10.3-26.8 10.3-46.2s-3.4-34.2-10.3-44.5c-6.8-10.3-16.5-15.4-29.1-15.4s-22.2 4.6-29.1 13.7c-6.8 9.1-10.3 21.7-10.3 37.6v23.9z m-54.7 471.9c-18.2 11.4-37 17.1-56.4 17.1s-34.8-6.3-46.2-18.8c-11.4-12.5-17.1-29.6-17.1-51.3s6.3-38.8 18.8-51.3 28.5-18.8 47.9-18.8 37 5.7 53 17.1v-65c-13.7-6.8-34.2-10.3-61.6-10.3-38.8 0-70.7 12-95.8 35.9-25.1 23.9-36.5 56.4-34.2 97.5 0 36.5 10.8 66.1 32.5 88.9 21.7 22.8 50.7 34.2 87.2 34.2s55.9-5.7 71.8-17.1v-58.1zM736 447l65 65v383l-65 65H288l-65-65V512l65-65h448zM288 895h448V512H288v383z" p-id="5887"></path></svg>
    </button>

    <!-- Replace all -->
    <button
      class="search-btn rep-all-btn"
      @click="emit('replace-all')"
      v-if="expandPanel"
      title="全部替换"
    >
      <svg t="1778579156997" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="6099" width="20" height="20"><path d="M708.6 64H671v253.1h37.6l3.4-20.5c6.8 16 18.2 23.9 34.2 23.9s29.1-8.5 39.3-25.6c10.3-17.1 15.4-39.3 15.4-66.7s-4.6-49-13.7-65-21.7-23.9-37.6-23.9-28.5 10.3-37.6 30.8l-3.4-106z m0 160.7c0-11.4 2.8-21.7 8.5-30.8s12.5-13.7 20.5-13.7 13.7 4 17.1 12 5.1 19.9 5.1 35.9-2.3 28.5-6.8 37.6-10.8 13.7-18.8 13.7-14.2-4-18.8-12-6.8-16.5-6.8-25.6v-17.1zM363.2 358.1l-41-41-61.6 61.6v-99.2c0-6.8 2.8-13.7 8.5-20.5s13.1-10.3 22.2-10.3h150.5v-58.1H291.3c-25.1 0-46.2 9.1-63.3 27.4-17.1 18.2-25.6 38.8-25.6 61.6v99.2l-65-65-41 41 133.4 136.8 133.4-133.4zM565 289.7c-9.1 20.5-22.8 30.8-41 30.8s-24.5-5.1-32.5-15.4-12-23.4-12-39.3c0-36.5 16-58.1 47.9-65l37.6-3.4c2.3-20.5-5.1-30.8-22.2-30.8s-33.6 5.7-49.6 17.1v-41c6.8-4.6 15.4-8.5 25.6-12 10.3-3.4 19.9-5.1 29.1-5.1 41 0 61.6 26.2 61.6 78.7v109.4H565v-23.9z m0-61.5l-23.9 3.4c-13.7 2.3-20.5 11.4-20.5 27.4s1.7 9.1 5.1 13.7 8.5 6.8 15.4 6.8 13.1-4 18.8-12c5.7-8 8.5-16.5 8.5-25.6v-13.7H565z m-150.5 489c0-52.4-19.4-78.7-58.1-78.7-9.1 2.3-18.8 4.6-29.1 6.8-10.3 2.3-18.8 5.7-25.6 10.3v41c16-11.4 31.9-17.1 47.9-17.1s23.9 10.3 23.9 30.8l-37.6 3.4c-31.9 6.8-47.9 28.5-47.9 65s4 29.1 12 39.3c8 10.3 18.8 15.4 32.5 15.4s31.9-10.3 41-30.8v23.9h41V717.1z m-41 37.6c0 11.4-2.3 20.5-6.8 27.4s-10.3 10.3-17.1 10.3-12-2.3-15.4-6.8c-3.4-4.6-5.1-9.1-5.1-13.7 0-16 6.8-25.1 20.5-27.4l23.9-3.4v13.7z m188.1 78.7c-25.1 0-45-8.5-59.8-25.6-14.8-17.1-22.2-40.5-22.2-70.1s8-53.6 23.9-71.8c16-18.2 37.6-27.4 65-27.4 18.2 2.3 30.8 5.7 37.6 10.3v47.9c-9.1-9.1-19.9-13.7-32.5-13.7s-23.4 5.1-32.5 15.4-13.7 23.4-13.7 39.3 4 28.5 12 37.6c8 9.1 18.8 13.7 32.5 13.7s26.2-4.6 37.6-13.7v47.9c-11.4 6.8-27.4 10.3-47.9 10.3zM96.5 895l61.6 65h578l65-65V577l-65-65H158l-61.6 65v318zM736 577v318H158V577h578z m130-130v386.4l61.6-65V446.9l-61.6-65H414.6l-61.6 65h513z" p-id="6100"></path></svg>
    </button>
  </div>
</template>

<script setup lang="ts">
import {
  ref,
  watch,
  nextTick
} from 'vue'

const props = defineProps<{
  visible: boolean
  searchText: string
  replaceText: string
  caseSensitive: boolean
  wholeWord: boolean
  regexp: boolean
  totalMatch: number
  currentMatch: number
}>()

const emit = defineEmits<{
  (e: 'update:searchText', value: string): void
  (e: 'update:replaceText', value: string): void
  (e: 'update:caseSensitive', value: boolean): void
  (e: 'update:wholeWord', value: boolean): void
  (e: 'update:regexp', value: boolean): void
  (e: 'next'): void
  (e: 'prev'): void
  (e: 'replace-one'): void
  (e: 'replace-all'): void
  (e: 'close'): void
}>()

const searchInputRef = ref<HTMLInputElement>()
const replaceInputRef = ref<HTMLInputElement>()

function onSearchInput(e: Event) {
  emit('update:searchText', (e.target as HTMLInputElement).value)
}

function onReplaceInput(e: Event) {
  emit('update:replaceText', (e.target as HTMLInputElement).value)
}

function emitNext() {
  emit('next')
}

function emitPrev() {
  emit('prev')
}

// Auto focus
watch(
  () => props.visible,
  async visible => {
    if (!visible) return
    await nextTick()
    searchInputRef.value?.focus()
    searchInputRef.value?.select()
    emit("next")
  }
)

const expandPanel = ref(false)

async function triggerExpand() {
  expandPanel.value = !expandPanel.value
  if (expandPanel.value) {
    await nextTick
    replaceInputRef.value?.focus()
    replaceInputRef.value?.select()
  }
}
</script>

<style scoped>
.search-panel {
  position: absolute;
  top: 46px !important;
  right: 12px !important;
  left: unset !important;
  bottom: unset !important;
  padding: 6px 8px;
  height: 24px;
  overflow: hidden;
  z-index: 999;

  border: none !important;
  backdrop-filter: saturate(300%) blur(16px);
  background-color: color-mix(in oklab, var(--apix-panel-layer-5-background) 50%, transparent);
  box-shadow: var(--apix-shadow-md);
  border-radius: var(--apix-default-border-radius);
  animation: scaleFadeIn 0.3s var(--apix-cubic-bezier);

  display: grid;
  grid-template-columns: 8fr 52fr 8fr 8fr 8fr 40fr 8fr 8fr 8fr;
  row-gap: 6px;
  column-gap: 3px;

  transition: box-shadow 0.3s var(--apix-cubic-bezier);
}

.search-panel.panel_expanded {
  max-height: 54px;
  height: fit-content;
}

@keyframes scaleFadeIn {
  0% {
    opacity: 0.3;
    transform: scale(1.05);
  }
  100% {
    opacity: 1;
    transform: scale(1);
  }
}

/* ============================================
   展开/折叠按钮
   ============================================ */
.expand-btn {
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: transparent;
  border: 1px solid transparent;
  box-shadow: none;
  border-radius: 6px;
  cursor: pointer;
  color: var(--apix-tertiary-dark-color);
}

.expand-btn:deep(.icon) {
  fill: var(--apix-secondary-dark-color);
}

.expand-btn:hover:deep(.icon) {
  fill: var(--apix-primary-active);
}

.expand-btn:active {
  border: none;
  box-shadow: none;
}

.expand-btn.panel_expanded {
  border-color: var(--apix-primary-active);
  color: var(--apix-primary-text);
}

.expand-btn.panel_expanded:deep(.icon) {
  fill: var(--apix-primary-active);
}

/* ============================================
   功能按钮（搜索/替换操作）
   ============================================ */
.search-btn {
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: transparent;
  border: 1px solid transparent;
  border-radius: 6px;
  padding: 2px;
  cursor: pointer;
  color: var(--apix-secondary-dark-color);
}

.search-btn:hover {
  background-color: var(--apix-default-button-hover);
  color: var(--apix-default-button-text-hover);
  border-color: var(--apix-default-button-border);
}

.search-btn:active {
  background-color: var(--apix-default-button-active);
}

.search-btn.active {
  border-color: var(--apix-primary-active);
  color: var(--apix-primary-text);
}

.search-btn:deep(.icon) {
  width: 18px;
  height: 18px;
  fill: var(--apix-secondary-dark-color);
}

.search-btn:hover:deep(.icon) {
  fill: var(--apix-primary-active);
}

.search-btn.active:deep(.icon) {
  fill: var(--apix-primary-active);
}

.regex-btn:deep(.icon),
.prev-btn:deep(.icon),
.next-btn:deep(.icon) {
  width: 15px;
  height: 15px;
}

.whole-btn:deep(.icon) {
  width: 20px;
  height: 20px;
}

.close-btn:deep(.icon) {
  width: 13px;
  height: 13px;
}

.index-wrapper {
  color: var(--apix-secondary-dark-color);
  display: flex;
  align-items: center;
}

/* ============================================
   输入框（搜索 & 替换）
   ============================================ */
.search-input::placeholder {
  color: var(--apix-input-placeholder-color);
}

.search-input {
  height: 24px;
  grid-column: 2;
  outline: none;
  background: transparent;
  font-family: inherit;
  color: inherit;
  -webkit-appearance: none;
  appearance: none;
  color: var(--apix-secondary-dark-color);
  
  flex: 1;
  font-size: 13px;
  box-sizing: border-box;
  border: 1px solid var(--apix-default-light-color);
  border-radius: 6px;
  background-color: transparent;
}

.search-input:focus {
  outline: none;
  border: 1px solid var(--apix-primary-color);
}
</style>