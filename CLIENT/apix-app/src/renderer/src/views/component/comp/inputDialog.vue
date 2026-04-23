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
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.12);
}

/* ===== text ===== */
.cd-title {
  position: relative;
  margin: 0 0 12px;
  font-size: 18px;
  font-weight: 600;
  color: #333;
}

.cd-content {
  margin-bottom: 24px;
}

.cd-message {
  margin-bottom: 12px;
  font-size: 14px;
  line-height: 1.6;
  color: #555;
}

/* ===== input ===== */
.cd-input {
  width: calc(100% - 24px);
  padding: 8px 10px;
  border-radius: 8px;
  border: none;
  font-size: 14px;
  outline: none;
  background-color: rgba(255, 255, 255, 0.507);
  resize: none;
  transition: all 0.3s ease;
  scrollbar-width: none;
}

.cd-input:focus {
  background-color: rgba(255, 255, 255, 0.84);
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

.btn.confirm:hover {
  background-color: rgba(255, 255, 255, 0.446);
}

.btn.confirm.warning {
  color: #c0392b;
}

.btn.confirm.warning:hover {
  background-color: #c03a2b34;
}

/* ===== transition ===== */
.cd-enter-active,
.cd-leave-active {
  transition: opacity 0.25s ease;
}

.cd-enter-from,
.cd-leave-to {
  opacity: 0;
}

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
