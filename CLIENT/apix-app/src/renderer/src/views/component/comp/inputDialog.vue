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

          <div class="cd-content">
            <div class="cd-message">{{ message }}</div>

            <!-- input area -->
            <textarea
              ref="inputRef"
              v-model="inputValue"
              class="cd-input"
              rows="3"
              :placeholder="options.placeholder || ''"
              @keyup.enter="handleConfirm"
            >
            </textarea>
          </div>

          <div class="cd-actions">
            <button class="btn cancel" @click="handleCancel">
              {{ options.cancelButtonText || '取消' }}
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
import { ref, onMounted, nextTick } from 'vue'

const props = defineProps<{
  title: string
  message: string
  options: {
    confirmButtonText?: string
    cancelButtonText?: string
    placeholder?: string
    defaultValue?: string
    type?: 'warning' | 'info'
  }
}>()

const emit = defineEmits<{
  (e: 'confirm', value: string): void
  (e: 'cancel'): void
}>()

const visible = ref(false)
const inputValue = ref(props.options.defaultValue || '')
const inputRef = ref<HTMLInputElement | null>(null)

let action: 'confirm' | 'cancel' | null = null

onMounted(async () => {
  visible.value = true
  // Focus input after dialog appears
  await nextTick()
  inputRef.value?.focus()
})

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
  if (action === 'confirm') emit('confirm', inputValue.value)
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

/* ===== text ===== */
.cd-title {
  position: relative;
  margin: 0 0 12px;
  font-size: 18px;
  font-weight: 600;
  color: var(--apix-darkest-color);
}

.cd-content {
  margin-bottom: 24px;
}

.cd-message {
  margin-bottom: 12px;
  font-size: 14px;
  line-height: 1.6;
  color: var(--apix-default-dark-color);
}

/* ===== input ===== */
.cd-input {
  width: calc(100% - 24px);
  color: var(--apix-default-dark-color);
  padding: 8px 10px;
  border-radius: var(--apix-button-border-radius);
  border: 1px solid var(--apix-default-light-color);
  font-size: 14px;
  outline: none;
  background-color: color-mix(in srgb, var(--apix-lightest-color) 50.7%, transparent);
  resize: none;
  transition: all 0.3s var(--apix-cubic-bezier);
  scrollbar-width: none;
}

.cd-input:focus {
  background-color: color-mix(in srgb, var(--apix-lightest-color) 84%, transparent);
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

.btn.confirm:hover {
  background-color: color-mix(in srgb, var(--apix-lightest-color) 44.6%, transparent);
}

.btn.confirm.warning {
  color: var(--apix-danger-color);
}

.btn.confirm.warning:hover {
  background-color: color-mix(in srgb, var(--apix-danger-color) 20.4%, transparent);
}

/* ===== transition ===== */
.cd-enter-active,
.cd-leave-active {
  transition: opacity 0.25s var(--apix-cubic-bezier);
}

.cd-enter-from,
.cd-leave-to {
  opacity: 0;
}

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
