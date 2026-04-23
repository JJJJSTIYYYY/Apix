<template>
  <div>
  <el-menu
    router
    :default-active="$route.path"
    class="el-menu-vertical"
    :collapse-transition="false"
    :collapse="true"
    :style="{ height: menuHeight + 'px' }"
    @open="handleOpen"
    @close="handleClose"
    @select="handleSelect"
    ref="leftMenu"
  >
    <div style="height: 5px; background-color: transparent;"></div>

    <el-menu-item
      v-for="page in pageRegistry"
      :key="page.path"
      :index="page.path"
      class="menu-item"
      :show-tooltip="false"
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
    <svg t="1776518156313" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="6410" width="16" height="16"><path d="M414.037333 695.210667a42.666667 42.666667 0 1 1-60.373333 60.330666l-213.205333-213.504a42.666667 42.666667 0 0 1 0-60.288L353.706667 268.501333a42.666667 42.666667 0 0 1 60.373333 60.330667L273.493333 469.333333H554.666667a341.333333 341.333333 0 0 1 341.162666 330.666667L896 810.666667a42.666667 42.666667 0 1 1-85.333333 0 256 256 0 0 0-246.4-255.829334L554.666667 554.666667H273.664l140.373333 140.544z" fill="#21212188" p-id="6411"></path></svg>
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
  } else {
    document.documentElement.style.setProperty('--apix-left-side-bar-width', '64px')
  }
  is_side_show.value = !is_side_show.value
}

const menuHeight = ref(window.innerHeight - 30) // 减去自定义标题栏高度

const updateHeight = () => {
  menuHeight.value = window.innerHeight - 30
}


onMounted(() => {
  window.addEventListener('resize', updateHeight)
  document.documentElement.style.setProperty('--apix-left-side-bar-width', '64px')
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', updateHeight)
})

</script>

<style>
.el-menu-vertical {
  left: calc(var(--apix-left-side-bar-width, 64px) - 64px);
  transition: all 0.28s cubic-bezier(0.23, 1, 0.32, 1);
}

.el-menu-vertical:not(.el-menu--collapse) {
  width: 140px;
  min-height: 400px;
}

.el-menu-vertical {
  background: #ffffff00;
  width: 64px;
  min-height: 400px;
  border-radius: 0 0 5px 0; /* 左上 右上 左下 右下 */
  border-right: 1px solid #ebeef5;
  -webkit-user-select: none;
  user-select: none;
}

.el-menu {
  background-color: rgba(255, 255, 255, 0);
  padding: 2px;
  padding-left: 4px;
}

.menu-item {
  border-radius: 12px;
  transition: background-color 240ms cubic-bezier(0.2, 0.8, 0.2, 1),
              transform 240ms cubic-bezier(0.2, 0.8, 0.2, 1),
              box-shadow 240ms cubic-bezier(0.2, 0.8, 0.2, 1);
}

.menu-item:hover {
  background-color: #fafafa; /* 浅灰背景 */
  background: rgba(255, 255, 255, 0.347);
  border: 1px solid rgba(255, 255, 255, 0.25);
  box-shadow:
    0 3px 10px rgba(31, 38, 135, 0.15), /* 柔和外阴影 */
    inset 0 1px 2px rgba(255, 255, 255, 0.1), /* 内部微亮 */
    inset 0 -1px 2px rgba(0, 0, 0, 0.08);      /* 内部微暗 */
}

.menu-buttom-item {
  opacity: 0.4;
  border-radius: 12px;
  bottom: 0px;
  left: 4px;
  width: 32px;
  height: 32px;
  border: none;
  position: fixed;
  z-index: 999;
  font-size: 12px;
  font-weight: 20;
  background-color: #00000000; /* 浅灰背景 */
}

.menu-buttom-item:hover {
  opacity: 1;
  background-color: #00000000; /* 浅灰背景 */
}

.menu-buttom-item {
  transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  transform-origin: 50% 50%;
}

.menu-buttom-item.rotated {
  transform: rotate(180deg);
}

/* 按钮 */
.menu-btn {
  background-color: transparent;
  color: #515151;
  border: none;
  margin-left: 16px;
  border-radius: 50%; /* 圆形按钮 */
  transition: background-color 200ms cubic-bezier(0.2, 0.8, 0.2, 1),
              transform 200ms cubic-bezier(0.2, 0.8, 0.2, 1),
              box-shadow 200ms cubic-bezier(0.2, 0.8, 0.2, 1);
}

.menu-btn:hover {
  background-color: #f5f5f5;
  color: #444444;
  box-shadow: 0 6px 18px rgba(0,0,0,0.10);
  border: none;
  
    /* 弱化的玻璃背景 */
  background: rgba(255, 255, 255, 0.347);
  border: 1px solid rgba(255, 255, 255, 0.25);
  box-shadow:
    0 3px 10px rgba(31, 38, 135, 0.15), /* 柔和外阴影 */
    inset 0 1px 2px rgba(255, 255, 255, 0.1), /* 内部微亮 */
    inset 0 -1px 2px rgba(0, 0, 0, 0.08);      /* 内部微暗 */
}

.text-label {
  width: 0px;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

.el-menu-item.is-active {
  color: rgb(0, 173, 155);
}
</style>

<style scoped>
.el-icon {
  justify-content: flex-start;
}
</style>