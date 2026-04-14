<template>
  <transition name="card-slide-fade">
    <div class="q-card">
      <div class="q-card-body">
        {{ history.preview || '暂无对话内容' }}
      </div>

      <div class="q-card-header">
        <!-- Left: star + time -->
        <div class="q-header-left">
          <transition name="star-pop">
            <span
              v-if="history.star"
              class="q-star-badge"
            >
              <el-icon><StarFilled /></el-icon>
            </span>
          </transition>

          <span class="q-time">{{ history.time }}</span>

          <span v-if="history.isGenerating" class="q-label generating">
            <span class="loading-dots">
              <span></span>
              <span></span>
              <span></span>
            </span>
          </span>

          <span v-if="showNewMessage" class="q-label new">
            新消息
          </span>
        </div>

        <!-- Right: actions -->
        <div class="q-cell-actions">
          <el-button
            type="text"
            size="small"
            class="q-icon-btn-more"
            @click.stop="onMoreClick"
          >
            <el-icon><More /></el-icon>
          </el-button>

          <el-button
            type="text"
            size="small"
            class="q-icon-btn-star"
            @click.stop="onStarClick"
          >
            <el-icon v-if="history.star"><StarFilled /></el-icon>
            <el-icon v-else><Star /></el-icon>
          </el-button>
        </div>
      </div>
    </div>
  </transition>

  <Teleport to="body">
    <transition name="scale-fade">
      <HistoryCardMenu
        v-if="isShowMenu"
        ref="menuRef"
        type="ai"
        :style="menuStyle"
        @close-menu="closePopMenu"
        @delete-history="handleDeleteCard"
        @rename-history="handleReEditPreview"
        @connect-project="handleConnectProject"
      />
    </transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, nextTick, onMounted, onBeforeUnmount, computed } from 'vue'
import HistoryCardMenu from './comp/historyCardMenu.vue'
import { useAuthStore } from '../../../store/auth'
import { useAppCacheData } from '../../../store/app'
import { InputDialog } from '../comp/inputDialog'

export interface ChatHistory {
  id: number | string
  sid?: number | string
  preview: string
  time: string
  date: string
  tokens?: number
  createTime: number
  star: boolean
  isGenerating?: boolean   // 当前是否正在生成
  hasNewMessage?: boolean  // 是否有未读新消息
}

const showNewMessage = computed(() => {
  return !!props.history.hasNewMessage && !props.history.isGenerating
})

const props = defineProps<{ history: ChatHistory }>()

const emit = defineEmits<{
  (e: "rename-history", history_id: string, new_title: string): void
  (e: "delete-history", history_id: string): void
  (e: "star-history", history_id: string): void
  (e: "connect-project", path: string): void
}>()

const authStore = useAuthStore()
const store = useAppCacheData()
const cid = ref("")

const isShowMenu = ref(false)
const menuStyle = ref<Record<string, string>>({})
const menuRef = ref<any>(null)

const menuWidthGuess = 180
const menuHeightGuess = 160

function onMoreClick(e: MouseEvent) {
  console.log("history card more clicked.")
  showPopMenu(e.clientX, e.clientY)
}

function showPopMenu(positionX: number, positionY: number) {
  isShowMenu.value = true
  menuStyle.value = {
    position: 'fixed',
    top: `${positionY}px`,
    left: `${positionX}px`,
    zIndex: '1000',
  }

  nextTick(() => {
    const menuEl = menuRef.value?.$el || menuRef.value
    if (!menuEl) return

    const viewportWidth = window.innerWidth
    const viewportHeight = window.innerHeight

    const realW = menuEl.offsetWidth || menuWidthGuess
    const realH = menuEl.offsetHeight || menuHeightGuess

    let left = positionX
    let top = positionY

    if (left + realW > viewportWidth) left = positionX - realW
    if (top + realH > viewportHeight) top = positionY - realH

    left = Math.min(Math.max(8, left), viewportWidth - realW - 8)
    top = Math.min(Math.max(8, top), viewportHeight - realH - 8)

    menuStyle.value = {
      position: 'fixed',
      top: `${top}px`,
      left: `${left}px`,
      zIndex: '1000',
    }
  })
}

function closePopMenu() {
  isShowMenu.value = false
}

async function onStarClick() {
  props.history.star = !props.history.star
  if (props.history.star) emit('star-history', props.history.id)
  try {
    await window.api.updateConversation(
      cid.value,
      props.history.sid ?? "",
      props.history.id,
      { star: props.history.star }
    )
  } catch (err) {
    console.log("对话收藏失败："+err)
  }
}

function onDocumentClick(e: MouseEvent) {
  if (!isShowMenu.value) return
  const menuEl = menuRef.value?.$el || menuRef.value
  if (!menuEl) return
  if (menuEl === e.target || menuEl.contains(e.target as Node)) return
  closePopMenu()
}

function onResize() {
  if (isShowMenu.value) closePopMenu()
}

onMounted(async () => {
  document.addEventListener('click', onDocumentClick)
  window.addEventListener('resize', onResize)
  await authStore.restore()
  cid.value = authStore.user.user_uid
})

onBeforeUnmount(() => {
  document.removeEventListener('click', onDocumentClick)
  window.removeEventListener('resize', onResize)
})

const handleDeleteCard = async (data) => {
  emit('delete-history', props.history.id)
}

const handleReEditPreview = async (data) => {
  InputDialog.open('请输入新的标题', '新标题', {
    placeholder: props.history.preview,
    defaultValue: props.history.preview,
  }).then(value => {
    props.history.preview = value
    emit('rename-history', props.history.id, value)
  }).catch(() => {
  })
}

const handleConnectProject = async () => {
  const result = await window.api.openFileDialog()
  if (result.canceled || result.filePaths.length === 0) {
      return
    }
  store.setWorkDir(props.history.id, result.filePaths[0])
  store.currentWorkDir=result.filePaths[0]
}
</script>

<style scoped>
.q-card {
  z-index: 1000;
  width: 100%;
  min-width: 0;
  display: flex;
  flex-direction: column;
  position: relative;
}

.q-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-width: 0;
  height: 30px;
}

/* ------------------------
   Left header (star + time)
------------------------- */
.q-header-left {
  display: flex;
  align-items: center;
  gap: 4px;
  min-width: 0;
  margin-left: 3px;
}

.q-star-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 14px;
  height: 14px;
  color: #ffb300e0;
  margin-top: -1px;
}

.q-card-body {
  flex: 1;
  min-width: 0;
  font-size: 0.85rem;
  padding-left: 4px;
  padding-right: 1px;
  line-height: 1.35;
  color: rgba(60, 60, 67, 0.78);
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
}

.q-time {
  font-size: 11px;
  color: rgba(60, 60, 67, 0.55);
}

/* ------------------------
   Right actions
------------------------- */
.q-cell-actions {
  margin-left: -8px;
}

.q-cell-actions * {
  flex: 0 0 auto;
  transition: opacity 0.18s ease;
  vertical-align: middle;
  opacity: 0;
  width: 0 !important;
}

.q-card:hover .q-cell-actions * {
  opacity: 1;
  pointer-events: auto;
  width: 16px !important;
}

:deep(.q-icon-btn-more.el-button),
:deep(.q-icon-btn-star.el-button) {
  border-radius: 999px;
  padding: 0;
  color: rgba(60, 60, 67, 0.323);
  transition: all 0.22s cubic-bezier(0.34, 1.56, 0.64, 1);
}
:deep(.q-icon-btn-star.el-button) {
  margin-left: 4px;
}

:deep(.q-icon-btn-more.el-button:hover),
:deep(.q-icon-btn-star.el-button:hover) {
  color: rgba(60, 60, 67, 0.564);
}

:deep(.q-icon-btn-star.el-button:active) {
  transform: scale(0.8);
}

/* ------------------------
   Star appear animation
------------------------- */
.star-pop-enter-active {
  animation: starPopIn 0.26s cubic-bezier(0.34, 1.56, 0.64, 1);
}
.star-pop-leave-active {
  animation: starPopOut 0.18s ease-in;
}

@keyframes starPopIn {
  0% { opacity: 0; transform: scale(0.4); }
  70% { opacity: 1; transform: scale(1.15); }
  100% { opacity: 1; transform: scale(1); }
}

@keyframes starPopOut {
  0% { opacity: 1; transform: scale(1); }
  100% { opacity: 0; transform: scale(0.6); }
}

/* ------------------------
   Menu animation
------------------------- */
.scale-fade-enter-active {
  animation: scaleFadeIn .25s cubic-bezier(0.22, 1, 0.36, 1);
}
.scale-fade-leave-active {
  animation: scaleFadeOut .2s cubic-bezier(0.4, 0, 0.2, 1);
}
@keyframes scaleFadeIn {
  0% { opacity: 0; transform: scale(0.9) translateY(6px); }
  60% { opacity: 1; transform: scale(1.03) translateY(0); }
  100% { opacity: 1; transform: scale(1); }
}
@keyframes scaleFadeOut {
  0% { opacity: 1; transform: scale(1); }
  100% { opacity: 0; transform: scale(0.95) translateY(6px); }
}

/* ------------------------
   Card enter / leave animation
------------------------- */
.card-slide-fade-enter-active {
  animation: cardIn 0.28s cubic-bezier(0.22, 1, 0.36, 1);
}

.card-slide-fade-leave-active {
  animation: cardOut 0.22s cubic-bezier(0.4, 0, 0.2, 1);
  position: absolute; /* prevent layout collapse */
  width: 100%;
}

@keyframes cardIn {
  0% {
    opacity: 0;
    transform: translateY(6px) scale(0.98);
  }
  60% {
    opacity: 1;
    transform: translateY(0) scale(1.01);
  }
  100% {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

@keyframes cardOut {
  0% {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
  100% {
    opacity: 0;
    transform: translateY(4px) scale(0.97);
  }
}

.q-label {
  margin-left: 8px;
  font-size: 12px;
  font-weight: 500;
  padding: 2px 8px;
  border-radius: 12px;
  line-height: 1;
  white-space: nowrap;
  letter-spacing: 0.02em;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

/* 加载动画 */
.loading-dots {
  display: flex;
  align-items: center;
  gap: 3px;
  height: 12px;
}

.loading-dots span {
  width: 4px;
  height: 4px;
  background: currentColor;
  border-radius: 50%;
  animation: bounce 1.4s infinite ease-in-out both;
}

.loading-dots span:nth-child(1) { animation-delay: -0.32s; }
.loading-dots span:nth-child(2) { animation-delay: -0.16s; }

@keyframes bounce {
  0%, 80%, 100% { transform: scale(0); opacity: 0.5; }
  40% { transform: scale(1); opacity: 1; }
}

/* 配色微调 - 让加载动画更低调 */
.q-label.generating {
  color: #87879f;
  background: #f5f5f7;
  min-width: 32px; /* 固定宽度避免跳动 */
}

.q-label.new {
  color: #1ad0b2;
  background: #e6faf7;
}
</style>
