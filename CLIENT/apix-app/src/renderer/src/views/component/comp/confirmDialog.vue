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
  position: absolute;
  width: 100vw;
  height: 100vh;
  inset: 0;
  z-index: 9999;

  display: flex;
  align-items: center;
  justify-content: center;

  background: var(--apix-mask-background);
  backdrop-filter: saturate(180%) blur(6px);
  animation: opacityFadeIn 0.5s var(--apix-cubic-bezier);
}

@keyframes opacityFadeIn {
  0% { 
    opacity: 0.3; 
  }
  100% { 
    opacity: 1; 
  }
}

/* ===== dialog ===== */
.cd-wrapper {
  width: 420px;
  padding: 24px;

  background: var(--apix-lightest-color);
  border-radius: var(--apix-panel-border-radius);

  display: flex;
  flex-direction: column;
  overflow: hidden;
  animation: scaleFadeIn 0.5s var(--apix-cubic-bezier);
  box-shadow: var(--apix-shadow-lg);
}

@keyframes scaleFadeIn {
  0% { 
    opacity: 0.3; 
    transform: scale(0.8); 
  }
  100% { 
    opacity: 1; 
    transform: scale(1); 
  }
}

/* ===== title ===== */
.cd-title {
  margin: 0 0 12px;
  font-size: 18px;
  font-weight: 600;
  color: var(--apix-darkest-color);
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
  color: var(--apix-default-dark-color);
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
  color: var(--apix-darkest-color);
}

.cd-content:deep(.section-body) {
  padding-left: 6px;
  word-break: break-word;
}

.cd-content:deep(.section-body a) {
  color: var(--apix-info-color);
  text-decoration: none;
}

.cd-content:deep(.section-body a:hover) {
  text-decoration: underline;
}

.cd-content:deep(.section-empty) {
  color: var(--apix-tertiary-dark-color);
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
  border-radius: var(--apix-button-border-radius);
  border: none;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s var(--apix-cubic-bezier);
}

.btn.cancel {
  background: transparent;
  color: var(--apix-default-dark-color);
}

.btn.cancel:hover {
  color: var(--apix-primary-dark);
}

.btn.confirm {
  background: color-mix(in srgb, var(--apix-lightest-color) 85%, transparent);
  color: var(--apix-darkest-color);
  box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--apix-darkest-color) 8%, transparent);
}

.btn.confirm.warning {
  color: var(--apix-danger-color);
}

.btn.confirm:hover {
  background-color: color-mix(in srgb, var(--apix-lightest-color) 44.6%, transparent);
}

.btn.confirm.warning:hover {
  background-color: color-mix(in srgb, var(--apix-danger-color) 20.4%, transparent);
}

/* ===== transition: mask ===== */
.cd-enter-active,
.cd-leave-active {
  transition: opacity 0.25s var(--apix-cubic-bezier);
}

.cd-enter-from,
.cd-leave-to {
  opacity: 0;
}

/* ===== transition: dialog ===== */
.cd-enter-active .cd-wrapper {
  transition:
    transform 0.25s var(--apix-cubic-bezier),
    opacity 0.25s var(--apix-cubic-bezier);
}

.cd-leave-active .cd-wrapper {
  transition:
    transform 0.25s var(--apix-cubic-bezier),
    opacity 0.25s var(--apix-cubic-bezier);
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
