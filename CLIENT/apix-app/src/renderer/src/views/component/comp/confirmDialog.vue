<template>
  <Teleport to="body">
    <Transition name="cd" @after-leave="afterLeave">
      <div
        v-if="visible"
        class="cd-mask"
        @click="handleCancel"
      >
        <div class="cd-wrapper" @click.stop>
          <h3 class="cd-title">{{ title }}</h3>

          <!-- enhanced content -->
          <div class="cd-content selectable" v-html="normalizeHtml(message)"></div>

          <div class="cd-actions">
            <button
              class="btn cancel"
              v-if="options.cancelButtonText?.length > 0"
              @click="handleCancel"
            >
              {{ options.cancelButtonText }}
            </button>

            <button
              class="btn confirm"
              :class="options.type"
              @click="handleConfirm"
            >
              {{ options.confirmButtonText || '确定' }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'

const props = defineProps<{
  title: string
  message: string
  options: {
    confirmButtonText?: string
    cancelButtonText?: string
    type?: 'warning' | 'info'
  }
}>()

const emit = defineEmits<{
  (e: 'confirm'): void
  (e: 'cancel'): void
}>()

const visible = ref(false)
let action: 'confirm' | 'cancel' | null = null

onMounted(() => {
  // Trigger enter animation
  visible.value = true
})

const normalizeHtml = (html: string) =>
  html.replace(/[\r\n]+/g, '')

function handleConfirm() {
  action = 'confirm'
  visible.value = false
}

function handleCancel() {
  action = 'cancel'
  visible.value = false
}

function afterLeave() {
  // Emit AFTER leave animation
  if (action === 'confirm') emit('confirm')
  else emit('cancel')
}
</script>

<style scoped>
/* ===== mask ===== */
.cd-mask {
  position: fixed;
  inset: 0;
  background: rgba(255, 255, 255, 0.35);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
}

/* ===== dialog ===== */
.cd-wrapper {
  width: 420px;
  padding: 24px;
  border-radius: 16px;
  border: 1px solid rgb(255, 255, 255);
  background: rgba(243, 243, 243, 0.637);
  backdrop-filter: blur(14px);
  box-shadow:
    0 10px 40px rgba(0, 0, 0, 0.12),
    inset 0 0 0 1px rgba(255, 255, 255, 0.6);
}

/* ===== title ===== */
.cd-title {
  margin: 0 0 12px;
  font-size: 18px;
  font-weight: 600;
  color: #333;
}

/* ===== content enhanced ===== */
.cd-content {
  margin-bottom: 24px;
  max-height: 320px;          /* prevent dialog from growing too tall */
  overflow: auto;
  scrollbar-width: none;
  background-color: transparent;
}

/* ===== html content ===== */
.cd-content {
  max-height: 360px;
  overflow: auto;
  font-size: 14px;
  line-height: 1.6;
  color: #444;
}

.cd-content:deep(.section) {
  margin-bottom: 16px;
}

.cd-content:deep(.section:last-child) {
  margin-bottom: 0;
}

.cd-content:deep(.section-title) {
  font-weight: 600;
  margin-bottom: 6px;
  color: #333;
}

.cd-content:deep(.section-body) {
  padding-left: 6px;
  word-break: break-word;
}

.cd-content:deep(.section-body a) {
  color: #1a73e8;
  text-decoration: none;
}

.cd-content:deep(.section-body a:hover) {
  text-decoration: underline;
}

.cd-content:deep(.section-empty) {
  color: #888;
  font-style: italic;
}


/* ===== buttons ===== */
.cd-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.btn {
  min-width: 80px;
  padding: 6px 16px;
  border-radius: 8px;
  border: none;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.btn.cancel {
  background: rgba(255, 255, 255, 0);
  color: #555;
}

.btn.cancel:hover {
  color: #185d56;
}

.btn.confirm {
  background: rgba(255, 255, 255, 0.85);
  color: #333;
  box-shadow: inset 0 0 0 1px rgba(0, 0, 0, 0.08);
}

.btn.confirm.warning {
  color: #c0392b;
}

.btn.confirm:hover {
  background-color: rgba(255, 255, 255, 0.446);
}

.btn.confirm.warning:hover {
  background-color: #c03a2b34;
}

/* ===== transition: mask ===== */
.cd-enter-active,
.cd-leave-active {
  transition: opacity 0.25s ease;
}

.cd-enter-from,
.cd-leave-to {
  opacity: 0;
}

/* ===== transition: dialog ===== */
.cd-enter-active .cd-wrapper {
  transition:
    transform 0.25s ease-out,
    opacity 0.25s ease-out;
}

.cd-leave-active .cd-wrapper {
  transition:
    transform 0.25s ease-in,
    opacity 0.25s ease-in;
}

.cd-enter-from .cd-wrapper {
  opacity: 0;
  transform: scale(0.96);
}

.cd-leave-to .cd-wrapper {
  opacity: 0;
  transform: scale(0.92);
}
</style>
