<template>
  <el-container>
    <el-aside style="width: var(--apix-left-side-bar-width); transition: width 0.28s cubic-bezier(0.23, 1, 0.32, 1);">
    <HomePage />
  </el-aside>
  <el-main>
    <el-result
        icon="error"
        title="页面施工中"
        sub-title="当前页面尚未完成"
      >
      </el-result>
  </el-main>
  </el-container>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { NTabPane, NTabs } from 'naive-ui'
import HomePage from './homePage.vue'

</script>

<style scoped>

</style>
