<template>
  <el-container>
    <el-aside class="aside-area">
      <HomePage />
    </el-aside>

    <el-main class="main-area">
        <!-- 左侧菜单 -->
        <el-aside class="menu-aside">
          <el-menu
            default-active="1"
            class="el-menu-vertical-data"
            @select="handleSelect"
          >
            <el-menu-item index="1">
              <el-icon><Cpu /></el-icon>
              <span>后台代理</span>
            </el-menu-item>
            <el-menu-item index="2">
              <el-icon><Timer /></el-icon>
              <span>定时任务</span>
            </el-menu-item>
          </el-menu>
        </el-aside>

        <!-- 右侧内容 -->
        <el-main style="width: auto; height: 100%; padding: 0px;">
          <TaskPage v-if="currentPage==='TaskPage'" />
          <CronPage v-else-if="currentPage==='CronPage'" />
        </el-main>
  </el-main>
</el-container>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import HomePage from './homePage.vue'
import { useAppCacheData } from '../store/app'
import { useAuthStore } from '../store/auth'
import TaskPage from './component/task_card/taskPage.vue'
import CronPage from './component/cron_card/cronPage.vue'

const authStore = useAuthStore()
const store = useAppCacheData()



// 当前显示的页面
const currentPage = ref('TaskPage')

// 菜单选择事件
const handleSelect = (key: string) => {
  console.log('dataPage detect: ', key)
  switch (key) {
    case '1':
      currentPage.value = 'TaskPage'
      break
    case '2':
      currentPage.value = 'CronPage'
      break
  }
  
  console.log('currentPage is: ', currentPage.value)
}
</script>

<style scoped>
.main-area {
  position: relative;
  align-items: center;
  display: flex;
  justify-content: center;
  align-items: center;
}

.menu-aside {
  width: 130px; 
  height: calc(100vh - 36px);
  background-color: var(--apix-panel-layer-2-background) !important;
  padding: 12px 12px 0 12px !important;
  box-shadow: inset -1px 0 0 0 var(--apix-border-disabled);

  border-radius: var(--apix-border-radius-base) 0 0 var(--apix-border-radius-base);
}


.el-menu-vertical {
  padding-top: 5px !important;
  left: calc(var(--apix-left-side-bar-width, 66px) - 66px);
}

.el-menu-vertical:not(.el-menu--collapse) {
  width: 140px;
  min-height: 400px;
}

.el-menu-vertical {
  position: relative;
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
}

.el-menu-item {
  padding: 0px 3px !important;
  min-width: 100%;
  color: var(--apix-primary-dark);
  transition: background 0.2s var(--apix-cubic-bezier) !important;
  border-radius: var(--apix-button-border-radius);
}

.el-menu-item:hover {
  color: var(--apix-primary-hover) !important;
  background-color: color-mix(in srgb, var(--apix-primary-color) 10%, transparent);
}

.el-menu-vertical :deep(.el-icon:hover svg path) {
  fill: var(--apix-primary-hover) !important;
}

.el-menu-item.is-active {
  color: rgb(0, 173, 155);
}
</style>