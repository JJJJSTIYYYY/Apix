<template>
  <el-container>
    <el-aside class="aside-area">
      <HomePage />
    </el-aside>

    <el-main class="main-area">
      
    </el-main>
  </el-container>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import HomePage from './homePage.vue'


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
  padding: 0 12px 0 12px !important;
  box-shadow: inset -1px 0 0 0 var(--apix-border-disabled);

  border-radius: var(--apix-border-radius-base) 0 0 var(--apix-border-radius-base);
}


.el-menu-vertical {
  padding-top: 5px !important;
  left: calc(var(--apix-left-side-bar-width, 66px) - 66px);
}

.el-menu-vertical :deep(.el-icon svg path) {
  fill: var(--apix-primary-dark) !important;
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
  padding: 0 0 0 12px !important;
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
  background: radial-gradient(
    circle at center,
    rgba(79, 223, 208, 0.16) 0%, 
    rgba(79, 223, 208, 0.08) 20%, 
    rgba(79, 223, 208, 0) 40% 
  );
}
</style>