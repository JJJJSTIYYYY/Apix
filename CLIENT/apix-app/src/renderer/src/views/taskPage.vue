<template>
  <el-container>
    <el-aside style="width: auto;">
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
              <span>后台任务</span>
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
      currentPage.value = 'TimedPage'
      break
  }
  
  console.log('currentPage is: ', currentPage.value)
}
</script>

<style scoped>
.main-area {
  position: relative;
  width: 100%;
  height: calc(100vh - 32px) !important;
  padding: 0px;
  align-items: center;
  display: flex;
  justify-content: center;
  align-items: center;
}

.menu-aside {
  width: 130px; 
  align-self: start; 
  height: 100%; 
  padding: 16px 3px;
  box-shadow: 
    0 0px 26px rgba(218, 218, 218, 0.206),
    0 0px 6px rgba(218, 218, 218, 0.09);
}

.el-menu-vertical-data {
  height: 100%;
}
</style>