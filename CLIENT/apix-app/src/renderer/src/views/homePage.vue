<template>
  <div>
  <el-menu
    router
    :default-active="$route.path"
    class="el-menu-vertical"
    :collapse-transition="false"
    :collapse="true"
    @open="handleOpen"
    @close="handleClose"
    @select="handleSelect"
    ref="leftMenu"
  >
    <el-menu-item
      v-for="page in pageRegistry"
      :key="page.path"
      :index="page.path"
      class="menu-item"
      :show-tooltip="false"
      :title="page.title"
    >
      <el-icon>
        <component :is="page.icon" />
      </el-icon>
    </el-menu-item>
  </el-menu>
  
  <button
    class="menu-buttom-item"
    :class="{ rotated: !is_side_show }"
    @click="setSideWidth"
  >
    <svg t="1777795521468" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="5007" width="20" height="20"><path d="M243.2 512m-83.2 0a1.3 1.3 0 1 0 166.4 0 1.3 1.3 0 1 0-166.4 0Z" p-id="5008" fill="var(--apix-default-dark-color)"></path><path d="M512 512m-83.2 0a1.3 1.3 0 1 0 166.4 0 1.3 1.3 0 1 0-166.4 0Z" p-id="5009" fill="var(--apix-secondary-dark-color)"></path><path d="M780.8 512m-83.2 0a1.3 1.3 0 1 0 166.4 0 1.3 1.3 0 1 0-166.4 0Z" p-id="5010" fill="var(--apix-tertiary-dark-color)"></path></svg>
  </button>
  </div>
</template>

<script lang="ts" setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useAppCacheData } from '../store/app'
import { pageRegistry } from '@router/pageRegistry'

const store = useAppCacheData()
const handleOpen = (key: string, keyPath: string[]) => {
  console.log(key, keyPath)
}
const handleClose = (key: string, keyPath: string[]) => {
  console.log(key, keyPath)
}
const handleSelect = (key: string, keyPath: string[]) => {
  console.log(key, keyPath)
  
}

const is_side_show = ref(true)

const setSideWidth = () => {
  if (is_side_show.value) {
    document.documentElement.style.setProperty('--apix-left-side-bar-width', '0px')
    document.documentElement.style.setProperty('--apix-left-side-bar-margin', '3px')
  } else {
    document.documentElement.style.setProperty('--apix-left-side-bar-width', '66px')
    document.documentElement.style.setProperty('--apix-left-side-bar-margin', '6px')
  }
  is_side_show.value = !is_side_show.value
}

const menuHeight = ref(window.innerHeight - 30) // 减去自定义标题栏高度

const updateHeight = () => {
  menuHeight.value = window.innerHeight - 30
}


onMounted(() => {
  window.addEventListener('resize', updateHeight)
  document.documentElement.style.setProperty('--apix-left-side-bar-width', '66px')
  document.documentElement.style.setProperty('--apix-left-side-bar-margin', '6px')
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', updateHeight)
})

</script>

<style scoped>
.el-menu-vertical {
  padding-top: 5px !important;
  left: calc(var(--apix-left-side-bar-width, 66px) - 66px);
}

.el-menu-vertical:not(.el-menu--collapse) {
  width: 140px;
  min-height: 400px;
}

.el-menu-vertical {
  background: transparent;
  width: 66px;
  min-height: 400px;
  user-select: none;
}

.el-menu {
  background-color: transparent;
  padding: 2px;
  padding-left: 4px;
  border: none !important;
  box-sizing: border-box;
}

.menu-buttom-item {
  opacity: 0.4;
  bottom: 0px;
  left: 22px;
  width: 32px;
  height: 32px;
  border: none;
  position: fixed;
  z-index: 999;
  font-size: 12px;
  font-weight: 20;
  background-color: transparent;
}

.menu-buttom-item:hover {
  opacity: 1;
}

.menu-buttom-item {
  transition: transform 0.3s var(--apix-cubic-bezier);
  transform-origin: 50% 50%;
}

.menu-buttom-item.rotated {
  transform: rotate(180deg);
}

.el-menu-item {
  color: var(--apix-primary-dark) !important;
}

.el-menu-item:hover {
  color: var(--apix-primary-hover) !important;
  background-color: transparent;
}

.el-menu-item.is-active {
  color: rgb(0, 173, 155) !important;
}

.el-menu-vertical :deep(.el-icon:hover svg path) {
  fill: currentColor !important;
}
</style>

<style scoped>
.el-icon {
  justify-content: flex-start;
}
</style>