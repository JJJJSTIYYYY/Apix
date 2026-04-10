<template>
  <el-container>
  <el-aside style="width: auto;">
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
