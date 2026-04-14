<template>
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
</template>

<script lang="ts" setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useAppCacheData } from '../store/app'
import { pageRegistry } from '@router/pageRegistry'

// Inject at runtime (plugin / backend / electron main)
// pageRegistry.push({
//   path: '/pluginExample',
//   name: 'plugin-example',
//   title: '插件示例',
//   icon: 'House',
//   component: () => import('@/plugins/example/Page.vue')
// })

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

const menuHeight = ref(window.innerHeight - 30) // 减去自定义标题栏高度

const updateHeight = () => {
  menuHeight.value = window.innerHeight - 30
}


onMounted(() => {
  window.addEventListener('resize', updateHeight)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', updateHeight)
})

</script>

<style>
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
  transform: translateY(-2px); /* 轻微上浮 */
  background: rgba(255, 255, 255, 0.347);
  border: 1px solid rgba(255, 255, 255, 0.25);
  box-shadow:
    0 3px 10px rgba(31, 38, 135, 0.15), /* 柔和外阴影 */
    inset 0 1px 2px rgba(255, 255, 255, 0.1), /* 内部微亮 */
    inset 0 -1px 2px rgba(0, 0, 0, 0.08);      /* 内部微暗 */
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
  transform: scale(1.05); /* 稍微放大一点 */
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