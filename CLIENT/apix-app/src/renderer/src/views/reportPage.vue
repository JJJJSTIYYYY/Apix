<template>
  <el-container class="report-page">
    <el-aside style="width: var(--apix-left-side-bar-width); transition: width 0.28s cubic-bezier(0.23, 1, 0.32, 1);">
      <HomePage />
    </el-aside>
    <el-main class="main-area">
      <div class="page-wrapper">
        <!-- 页面标题 -->
        <div class="page-header">
          <h1 class="page-title">任务日志审查</h1>
          <p class="page-subtitle">查看任务执行详情与结果</p>
        </div>

        <!-- 统计栏 -->
        <div class="stats-bar">
          <div class="stat-chip">
            <span class="stat-dot" style="background: #909399;"></span>
            <span class="stat-label">等待中</span>
            <span class="stat-count">{{ statusCount.pending }}</span>
          </div>
          <div class="stat-chip">
            <span class="stat-dot" style="background: rgb(136, 202, 197);"></span>
            <span class="stat-label">运行中</span>
            <span class="stat-count">{{ statusCount.running }}</span>
          </div>
          <div class="stat-chip">
            <span class="stat-dot" style="background: #67c23a;"></span>
            <span class="stat-label">已完成</span>
            <span class="stat-count">{{ statusCount.finished }}</span>
          </div>
        </div>

        <!-- 子任务列表 -->
        <div class="subtask-list">
          <transition-group name="subtask-fade" tag="div">
            <div
              v-for="(item, index) in subtaskList"
              :key="item.id"
              class="subtask-card"
              :class="{ 
                'is-expanded': expandedIds.includes(item.id),
                'status-pending': item.status === 'pending',
                'status-running': item.status === 'running',
                'status-finished': item.status === 'finished'
              }"
              :style="{ '--stagger-index': index }"
              @click="toggleExpand(item.id)"
            >
              <!-- 卡片头部（常态显示） -->
              <div class="card-header">
                <div class="header-left">
                  <div class="task-type">{{ item.type }}</div>
                  <div class="task-name selectable">{{ item.name }}</div>
                </div>
                <div class="header-right">
                  <div class="task-status" :class="'status-' + item.status">
                    <el-icon v-if="item.status === 'running'" class="rotating"><Loading /></el-icon>
                    <el-icon v-else-if="item.status === 'finished'"><CircleCheck /></el-icon>
                    <el-icon v-else><Timer /></el-icon>
                    <span>{{ statusText[item.status] }}</span>
                  </div>
                  <el-icon class="expand-icon" :class="{ 'is-expanded': expandedIds.includes(item.id) }">
                    <ArrowDown />
                  </el-icon>
                </div>
              </div>

              <!-- 展开内容（详情） -->
              <transition name="expand">
                <div v-if="expandedIds.includes(item.id)" class="card-body" @click.stop>
                  <div class="body-grid selectable">
                    <!-- 基础信息 -->
                    <div class="info-section">
                      <div class="section-title">基础信息</div>
                      <div class="info-grid">
                        <div class="info-item">
                          <span class="info-label">子任务 ID</span>
                          <span class="info-value mono">{{ item.id }}</span>
                        </div>
                        <div class="info-item">
                          <span class="info-label">任务 ID</span>
                          <span class="info-value mono">{{ item.task_id }}</span>
                        </div>
                        <div class="info-item">
                          <span class="info-label">Mock</span>
                          <span class="info-value">{{ item.mock || '-' }}</span>
                        </div>
                        <div class="info-item full-width">
                          <span class="info-label">目标地址</span>
                          <span class="info-value mono">{{ item.address }}</span>
                        </div>
                      </div>
                    </div>

                    <!-- 脚本内容 -->
                    <div class="info-section" v-if="item.script">
                      <div class="section-title">执行脚本</div>
                      <div class="code-block">
                        <pre><code>{{ item.script }}</code></pre>
                      </div>
                    </div>

                    <!-- 任务描述 -->
                    <div class="info-section" v-if="item.description">
                      <div class="section-title">任务描述</div>
                      <div class="description-text">{{ item.description }}</div>
                    </div>

                    <!-- 执行结果 -->
                    <div class="info-section result-section" v-if="item.result">
                      <div class="section-title">执行结果</div>
                      <div class="result-content" :class="{ 'is-error': item.result.includes('error') || item.result.includes('失败') }">
                        {{ item.result }}
                      </div>
                    </div>
                  </div>
                </div>
              </transition>
            </div>
          </transition-group>
        </div>

        <!-- 空状态 -->
        <el-empty v-if="subtaskList.length === 0" description="暂无子任务数据" />
      </div>
    </el-main>
  </el-container>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import HomePage from './homePage.vue'
import { Loading, CircleCheck, Timer, ArrowDown } from '@element-plus/icons-vue'

// ----------------------------------------------------------------------
// Types
// ----------------------------------------------------------------------
interface SubtaskItem {
  id: string
  task_id: string
  mock: string
  name: string
  type: string
  address: string
  script: string
  description: string
  status: 'pending' | 'running' | 'finished'
  result: string
}

// ----------------------------------------------------------------------
// State
// ----------------------------------------------------------------------
const subtaskList = ref<SubtaskItem[]>([])
const expandedIds = ref<string[]>([])
const statusText = {
  pending: '等待中',
  running: '运行中',
  finished: '已完成'
}

// ----------------------------------------------------------------------
// Mock Data
// ----------------------------------------------------------------------
const generateMockData = (): SubtaskItem[] => {
  const types = ['HTTP', 'SQL', 'SSH', 'Docker', 'K8s', 'Script']
  const names = [
    '获取用户列表接口测试',
    '数据库备份检查',
    '服务器磁盘清理',
    '容器镜像构建',
    'Pod状态检查',
    '日志文件归档',
    '配置文件更新',
    '服务健康检查',
    '数据同步任务',
    '缓存刷新操作'
  ]
  const statuses: ('pending' | 'running' | 'finished')[] = ['pending', 'running', 'finished']
  
  return Array.from({ length: 20 }, (_, i) => {
    const status = statuses[Math.floor(Math.random() * statuses.length)]
    const type = types[Math.floor(Math.random() * types.length)]
    
    return {
      id: `SUB-${Date.now()}-${i.toString().padStart(3, '0')}`,
      task_id: `TASK-${Math.floor(Math.random() * 10000)}`,
      mock: Math.random() > 0.5 ? `mock-${i}` : '',
      name: names[i % names.length],
      type,
      address: type === 'HTTP' ? `https://api.example.com/v1/resource${i}` : 
                type === 'SQL' ? `mysql://db-server:3306/db_${i}` :
                `server-${i}.internal.local`,
      script: Math.random() > 0.3 ? `#!/bin/bash\necho "Starting task ${i}"\ncurl -X GET ${type}://endpoint${i}\nif [ $? -eq 0 ]; then\n  echo "Success"\nelse\n  echo "Failed"\nfi` : '',
      description: `这是第 ${i + 1} 个子任务的详细描述，用于说明该步骤的具体执行内容和预期目标。`,
      status,
      result: status === 'finished' 
        ? (Math.random() > 0.8 ? 'error: 连接超时' : '执行成功，返回 200 OK\n耗时: 1.23s\n数据大小: 45KB')
        : status === 'running' ? '正在执行中...' : ''
    }
  })
}

// ----------------------------------------------------------------------
// Computed
// ----------------------------------------------------------------------
const statusCount = computed(() => {
  return {
    pending: subtaskList.value.filter(s => s.status === 'pending').length,
    running: subtaskList.value.filter(s => s.status === 'running').length,
    finished: subtaskList.value.filter(s => s.status === 'finished').length
  }
})

// ----------------------------------------------------------------------
// Methods
// ----------------------------------------------------------------------
const toggleExpand = (id: string) => {
  const index = expandedIds.value.indexOf(id)
  if (index > -1) {
    expandedIds.value.splice(index, 1)
  } else {
    expandedIds.value.push(id)
  }
}

onMounted(() => {
  subtaskList.value = generateMockData()
})
</script>

<style scoped>
.report-page {
  height: 100vh;
}

.main-area {
  padding: 0;
  overflow-y: auto;
}

.page-wrapper {
  max-width: 900px;
  margin: 0 auto;
  padding: 40px 20px;
  min-height: 100vh;
}

/* 页面标题 */
.page-header {
  text-align: center;
  margin-bottom: 32px;
}

.page-title {
  font-size: 24px;
  font-weight: 600;
  color: #303133;
  margin: 0 0 8px 0;
  letter-spacing: -0.5px;
}

.page-subtitle {
  font-size: 14px;
  color: #909399;
  margin: 0;
}

/* 统计栏 */
.stats-bar {
  display: flex;
  justify-content: center;
  gap: 16px;
  margin-bottom: 32px;
  flex-wrap: wrap;
}

.stat-chip {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  background: rgba(255, 255, 255, 0.7);
  backdrop-filter: blur(10px);
  border-radius: 20px;
  border: 1px solid rgba(136, 202, 197, 0.2);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}

.stat-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.stat-label {
  font-size: 13px;
  color: #606266;
}

.stat-count {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  font-family: 'SF Mono', Monaco, monospace;
  min-width: 20px;
  text-align: center;
}

/* 子任务列表 */
.subtask-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* 子任务卡片 */
.subtask-card {
  margin: 3px;
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(10px);
  border-radius: 16px;
  border: 1px solid rgba(136, 202, 197, 0.2);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.04);
  overflow: hidden;
  transition: all 0.3s cubic-bezier(0.215, 0.61, 0.355, 1);
  cursor: pointer;
}

.subtask-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(136, 202, 197, 0.12);
  border-color: rgba(136, 202, 197, 0.4);
}

.subtask-card.is-expanded {
  border-color: rgba(136, 202, 197, 0.5);
  box-shadow: 0 12px 32px rgba(136, 202, 197, 0.15);
}

/* 状态色彩 */
.subtask-card.status-pending {
  border-left: 4px solid #c1c1c1;
}

.subtask-card.status-running {
  border-left: 4px solid rgb(136, 202, 197);
}

.subtask-card.status-finished {
  border-left: 4px solid #67c23a;
}

/* 卡片头部 */
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 16px;
  min-height: 60px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
  min-width: 0;
}

.task-type {
  padding: 4px 10px;
  background: rgba(136, 202, 197, 0.15);
  color: rgb(100, 180, 170);
  font-size: 11px;
  font-weight: 600;
  border-radius: 6px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  flex-shrink: 0;
}

.task-name {
  font-size: 15px;
  font-weight: 500;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}

.task-status {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 500;
}

.task-status.status-pending {
  background: rgba(135, 135, 135, 0.15);
  color: #7e7e7e;
}

.task-status.status-running {
  background: rgba(136, 202, 197, 0.2);
  color: rgb(80, 160, 150);
}

.task-status.status-finished {
  background: rgba(103, 194, 58, 0.15);
  color: #67c23a;
}

.rotating {
  animation: rotating 2s linear infinite;
}

@keyframes rotating {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.expand-icon {
  font-size: 16px;
  color: #c0c4cc;
  transition: transform 0.3s ease;
}

.expand-icon.is-expanded {
  transform: rotate(180deg);
  color: rgb(136, 202, 197);
}

/* 卡片内容体 */
.card-body {
  border-top: 1px solid rgba(136, 202, 197, 0.1);
  background: rgba(136, 202, 197, 0.02);
}

.body-grid {
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* 信息区块 */
.info-section {
  background: rgba(255, 255, 255, 0.6);
  border-radius: 12px;
  padding: 16px;
  border: 1px solid rgba(136, 202, 197, 0.1);
}

.section-title {
  font-size: 12px;
  font-weight: 600;
  color: rgb(136, 202, 197);
  text-transform: uppercase;
  letter-spacing: 0.8px;
  margin-bottom: 12px;
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.info-item.full-width {
  grid-column: 1 / -1;
}

.info-label {
  font-size: 11px;
  color: #909399;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.info-value {
  font-size: 13px;
  color: #606266;
  word-break: break-all;
}

.info-value.mono {
  font-family: 'SF Mono', Monaco, monospace;
  font-size: 12px;
  background: rgba(136, 202, 197, 0.08);
  padding: 4px 8px;
  border-radius: 4px;
  color: #303133;
}

/* 代码块 */
.code-block {
  background: #2d2d2d;
  border-radius: 8px;
  padding: 16px;
  overflow-x: auto;
}

.code-block pre {
  margin: 0;
  white-space: pre-wrap;
  word-wrap: break-word;
}

.code-block code {
  font-family: 'SF Mono', Monaco, monospace;
  font-size: 12px;
  line-height: 1.6;
  color: #e6e6e6;
}

/* 描述文本 */
.description-text {
  font-size: 13px;
  color: #606266;
  line-height: 1.6;
}

/* 结果区域 */
.result-section .section-title {
  color: #67c23a;
}

.result-content {
  padding: 12px 16px;
  background: rgba(103, 194, 58, 0.08);
  border-radius: 8px;
  font-family: 'SF Mono', Monaco, monospace;
  font-size: 12px;
  line-height: 1.6;
  color: #606266;
  white-space: pre-wrap;
}

.result-content.is-error {
  background: rgba(245, 108, 108, 0.08);
  color: #f56c6c;
}

/* 展开动画 */
.expand-enter-active,
.expand-leave-active {
  transition: all 0.3s ease;
  max-height: 1000px;
  opacity: 1;
  overflow: hidden;
}

.expand-enter-from,
.expand-leave-to {
  max-height: 0;
  opacity: 0;
}

/* 列表入场动画 */
.subtask-fade-enter-active {
  transition: all 0.4s cubic-bezier(0.215, 0.61, 0.355, 1);
  transition-delay: calc(var(--stagger-index, 0) * 50ms);
}

.subtask-fade-enter-from {
  opacity: 0;
  transform: translateY(20px);
}

.subtask-fade-enter-to {
  opacity: 1;
  transform: translateY(0);
}

/* 滚动条美化 */
.main-area::-webkit-scrollbar {
  width: 6px;
}

.main-area::-webkit-scrollbar-track {
  background: transparent;
}

.main-area::-webkit-scrollbar-thumb {
  background: rgba(136, 202, 197, 0.3);
  border-radius: 3px;
}

.main-area::-webkit-scrollbar-thumb:hover {
  background: rgba(136, 202, 197, 0.5);
}

/* 响应式 */
@media (max-width: 768px) {
  .info-grid {
    grid-template-columns: 1fr;
  }
  
  .stats-bar {
    gap: 8px;
  }
  
  .stat-chip {
    padding: 6px 12px;
  }
}
</style>