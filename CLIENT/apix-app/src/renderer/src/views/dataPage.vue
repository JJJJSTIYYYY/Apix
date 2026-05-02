<template>
  <el-container>
    <el-aside style="width: var(--apix-left-side-bar-width); transition: width 0.28s cubic-bezier(0.23, 1, 0.32, 1);">
      <HomePage />
    </el-aside>

    <el-main class="main-area">
        <!-- 左侧菜单 -->
        <el-aside class="menu-aside">
          <el-menu
            default-active="0"
            class="el-menu-vertical-data"
            @select="handleSelect"
          >
            <el-menu-item index="0">
              <el-icon><Connection /></el-icon>
              <span>供应商</span>
            </el-menu-item>
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
          <ProviderPage v-if="currentPage==='ProviderPage'" />
          <RagPage v-else-if="currentPage==='RagPage'" />
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
import ProviderPage from './component/provider_card/providerPage.vue'
import RagPage from './component/rag_card/ragPage.vue'
import RolePage from './component/role_card/rolePage.vue'
import SkillPage from './component/skill_card/skillPage.vue'

const authStore = useAuthStore()
const store = useAppCacheData()



// 当前显示的页面
const currentPage = ref('ProviderPage')

// 菜单选择事件
const handleSelect = (key: string) => {
  console.log('dataPage detect: ', key)
  switch (key) {
    case '0':
      currentPage.value = 'ProviderPage'
      break
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
  height: calc(100% - 24px); 
  padding: 16px 3px;
  margin: 12px;
  border-radius: 24px;
  background-color: rgba(255, 255, 255, 0.5);
  box-shadow: 
    inset 0 0 0 2px rgba(255, 255, 255, 0.8),
    0 0px 26px rgba(218, 218, 218, 0.206),
    0 0px 6px rgba(218, 218, 218, 0.09);
  transition: all 0.28s ease;
}

.menu-aside:hover {
  box-shadow: 
    inset 0 0 0 2px rgba(255, 255, 255, 0.8),
    0 0px 26px rgba(218, 218, 218, 0.452),
    0 0px 6px rgba(218, 218, 218, 0.237);
  transform: scale(1.01);
}

.el-menu {
  background-color: rgba(255, 255, 255, 0);
  padding: 2px;
  padding-left: 4px;
}

.el-menu-vertical-data {
  height: 100%;
}

.el-menu-item {
  border-radius: 16px;
}

.el-menu-item:hover {
  background: rgba(0, 173, 156, 0.142);
}

.el-menu-item.is-active {
  color: rgb(0, 173, 155);
  /* 核心：中心到四周减淡的圆形泛光背景 */
  background: radial-gradient(
    circle at center,
    rgba(0, 231, 208, 0.2) 0%,      /* 中心最亮 */
    rgba(0, 231, 208, 0.08) 10%,    /* 中间过渡 */
    rgba(0, 231, 208, 0) 30%        /* 边缘完全透明 */
  );
}
</style>