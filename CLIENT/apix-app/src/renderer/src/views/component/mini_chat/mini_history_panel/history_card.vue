<template>
  <transition name="card-slide-fade">
    <div class="q-card-wrapper">
      <div class="q-card">
        <!-- Left: preview content -->
        <div class="q-card-body">
          <transition name="star-pop">
            <div class="q-card-status">
              <span
                v-if="history.star"
                class="q-star-badge-inline"
              >
                <svg t="1777123727784" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="9432" width="20" height="20"><path d="M170.666667 138.678857c0-17.67619 14.336-32.01219 32.01219-32.01219h618.642286c17.67619 0 32.01219 14.336 32.01219 32.01219v778.654476L512 768 170.666667 917.333333V138.654476z" p-id="9433" fill="currentColor"></path></svg>
              </span>
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
          </transition>
          <span class="q-preview-text">{{ history.preview || '暂无对话内容' }}</span>
        </div>

        <!-- Right: actions -->
        <div class="q-card-actions">
          <button
            type="text"
            size="small"
            class="q-icon-btn-star"
            @click.stop="onStarClick"
          >
            <svg v-if="history.star" t="1777123999522" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="10995" width="20" height="20"><path d="M956 398.496q-8-23.488-26.496-39.008t-42.496-19.488l-204.992-31.008-92-195.008q-11.008-24-32.992-36.992Q536.032 64 512.032 64t-44.992 12.992q-22.016 12.992-32.992 36.992l-92 195.008-204.992 31.008q-24 4-42.496 19.488t-26.496 39.008-2.496 47.008 22.496 41.504l151.008 154.016-36 218.016q-6.016 40 20 70.496t66.016 30.496q22.016 0 42.016-11.008l180.992-100 180.992 100q20 11.008 42.016 11.008 40 0 66.016-30.496t20-70.496l-36-218.016 151.008-154.016q16.992-18.016 22.496-41.504t-2.496-47.008z" p-id="10996" fill="#cccccc"></path></svg>
            <svg v-else t="1777124070437" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="3097" width="20" height="20"><path d="M512 136q8.992 0 12.992 8.992l104.992 222.016q3.008 7.008 11.008 8.992l235.008 35.008q8.992 2.016 12 10.496t-4 14.496l-171.008 176q-4.992 4.992-4 12l40.992 247.008q0.992 7.008-3.488 12t-11.488 4.992q-4 0-7.008-2.016l-208.992-115.008q-3.008-2.016-7.008-2.016t-7.008 2.016L296 885.984q-3.008 2.016-7.008 2.016-7.008 0-11.488-4.992t-3.488-12L315.008 624q0.992-7.008-4-12l-171.008-176q-7.008-6.016-4-14.496t12-9.504l235.008-36q8-0.992 11.008-8.992l104.992-222.016q4-8.992 12.992-8.992zM512 64q-24 0-44.992 12.992-22.016 12.992-32.992 36.992l-92 195.008-204.992 31.008q-24 4-42.496 19.488t-26.496 39.008-2.496 47.008 22.496 41.504l151.008 154.016-36 218.016q-6.016 40 20 70.496t66.016 30.496q22.016 0 42.016-11.008l180.992-100 180.992 100q20 11.008 42.016 11.008 40 0 66.016-30.496t20-70.496l-36-218.016 151.008-154.016q16.992-18.016 22.496-41.504t-2.496-47.008-26.496-39.008-42.496-19.488l-204.992-31.008-92-195.008q-11.008-24-32.992-36.992Q536.128 64 512.128 64z" p-id="3098" fill="#cccccc"></path></svg>
          </button>

          <button
            type="text"
            size="small"
            class="q-icon-btn-more"
            @click.stop="onMoreClick"
          >
            <svg t="1777124236767" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="12444" width="20" height="20"><path d="M243.2 512m-83.2 0a1.3 1.3 0 1 0 166.4 0 1.3 1.3 0 1 0-166.4 0Z" p-id="12445" fill="#cccccc"></path><path d="M512 512m-83.2 0a1.3 1.3 0 1 0 166.4 0 1.3 1.3 0 1 0-166.4 0Z" p-id="12446" fill="#cccccc"></path><path d="M780.8 512m-83.2 0a1.3 1.3 0 1 0 166.4 0 1.3 1.3 0 1 0-166.4 0Z" p-id="12447" fill="#cccccc"></path></svg>
          </button>
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
import HistoryCardMenu from '../../dialog_history/comp/historyCardMenu.vue'
import { useAuthStore } from '../../../../store/auth'
import { useAppCacheData } from '../../../../store/app'
import { InputDialog } from '../../comp/inputDialog'
import { ElMessage } from 'element-plus'

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
    console.error("[closePopMenu error]:" + err)
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
  ElMessage({ type: 'warning', message: '当前不允许修改工作目录', plain: true })
}
</script>

<style scoped>
.q-card-wrapper {
  z-index: 1000;
  width: 100%;
  position: relative;
  max-width: 100%;
  overflow: hidden;
}

.q-card {
  z-index: 1000;
  width: calc(100% + 42px);
  min-width: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  box-sizing: border-box;
  padding: 2px 4px;
  position: relative;
  border-radius: 6px;
  transition: background-color 0.2s ease;
}

.q-card:hover {
  width: 100%;
}

/* ------------------------
   Left: preview content
------------------------- */
.q-card-body {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  padding: 0px 3px;
  gap: 6px;
  font-size: 0.85rem;
  line-height: 1.35;
  color: var(--apix-secondary-dark-color);
  overflow: hidden;
}
.q-card-body.is_active {
  color: var(--apix-default-dark-color);
}
.q-card-body:hover:not(.is_active) {
  color: var(--apix-default-dark-color);
}

.q-preview-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  width: 380px;
}

.q-card:hover .q-preview-text {
  width: 360px;
}

.q-star-badge-inline {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  width: 14px;
  height: 14px;
}

.q-card-status {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

/* ------------------------
   Right: actions
------------------------- */
.q-card-actions {
  display: flex;
  align-items: center;
  gap: 2px;
  flex-shrink: 0;
  opacity: 0;
  transition: opacity 0.18s ease;
}

.q-card:hover .q-card-actions {
  opacity: 1;
  pointer-events: auto;
}

.q-icon-btn-more,
.q-icon-btn-star {
  border-radius: 999px;
  padding: 0;
  width: 20px;
  height: 20px;
  color: rgba(60, 60, 67, 0.323);
  background-color: transparent;
  border: none;
}

.q-icon-btn-star {
  transform: scale(0.8);
}

/* ------------------------
   Labels
------------------------- */
.q-label {
  font-size: 11px;
  font-weight: 500;
  padding: 3px 6px;
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

.q-label.generating {
  color: #87879f;
  background: transparent;
  min-width: 16px;
}

.q-label.new {
  color: var(--apix-primary-color);
  background: var(--apix-primary-light);
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
  position: absolute;
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
</style>
