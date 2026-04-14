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
              <el-icon><DocumentCopy /></el-icon>
              <span>知识库</span>
            </el-menu-item>
            <el-menu-item index="2">
              <el-icon><Box /></el-icon>
              <span>技能包</span>
            </el-menu-item>
            <el-menu-item index="3">
              <el-icon><User /></el-icon>
              <span>角色卡</span>
            </el-menu-item>
            <el-menu-item index="4">
              <el-icon><SetUp /></el-icon>
              <span>MCP</span>
            </el-menu-item>
          </el-menu>
        </el-aside>

        <!-- 右侧内容 -->
        <el-main style="width: auto; height: 100%; padding: 0px;">
          <RagPage v-if="currentPage==='RagPage'" />
          <SkillPage v-else-if="currentPage==='SkillPage'" />
          <RolePage v-else-if="currentPage==='RolePage'" />
        </el-main>
  </el-main>
</el-container>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import HomePage from './homePage.vue'
import { useAppCacheData } from '../store/app'
import { useAuthStore } from '../store/auth'
import RagPage from './component/rag_card/ragPage.vue'
import RolePage from './component/role_card/rolePage.vue'
import SkillPage from './component/skill_card/skillPage.vue'

const authStore = useAuthStore()
const store = useAppCacheData()



// 当前显示的页面
const currentPage = ref('RagPage')

// 菜单选择事件
const handleSelect = (key: string) => {
  console.log('dataPage detect: ', key)
  switch (key) {
    case '1':
      currentPage.value = 'RagPage'
      break
    case '2':
      currentPage.value = 'SkillPage'
      break
    case '3':
      currentPage.value = 'RolePage'
      break
    case '4':
      currentPage.value = 'McpPage'
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