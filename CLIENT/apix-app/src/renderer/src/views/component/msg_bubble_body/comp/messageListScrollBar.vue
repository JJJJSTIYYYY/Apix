<template>
  <div
    ref="containerRef"
    class="message-scrollbar"
    @mouseenter="expanded = true"
    @mouseleave="expanded = false"
  >
    <div
      v-for="item in filteredMsgItems"
      :key="item.msg_id"
      :ref="el => setItemRef(el, item.msg_id)"
      class="scroll-item"
      :class="{
        active: item.msg_id === current_position,
      }"
      @click="handleClick(item.msg_id)"
    >
      <div class="tick-wrapper">
        <div class="tick"></div>
      </div>

      <Transition name="preview-fade">
        <div
          v-if="expanded"
          class="preview"
        >
          {{ item.preview }}
        </div>
      </Transition>
    </div>
  </div>
</template>

<script setup lang="ts">
import { nextTick, ref, watch, computed } from 'vue'

export interface MessagePreviewItem {
  msg_id: string
  preview: string
}

interface Props {
  msg_item: MessagePreviewItem[]
  current_position: string
}

const props = defineProps<Props>()

const filteredMsgItems = computed<MessagePreviewItem[]>(() => {
  return props.msg_item.filter(item => 
    item.preview && item.preview.trim() !== ''
  )
})

const emit = defineEmits<{
  (e: 'scroll-to', msgId: string): void
}>()

const expanded = ref(false)

const containerRef = ref<HTMLElement | null>(null)

const itemRefMap = new Map<string, HTMLElement>()

function setItemRef(
  el: Element | null,
  msgId: string,
) {
  if (el) {
    itemRefMap.set(
      msgId,
      el as HTMLElement,
    )
  } else {
    itemRefMap.delete(msgId)
  }
}

function handleClick(msgId: string) {
  emit('scroll-to', msgId)
}

watch(
  () => props.current_position,
  async (msgId) => {
    if (!msgId) {
      return
    }

    await nextTick()

    const container =
      containerRef.value

    const target =
      itemRefMap.get(msgId)

    if (!container || !target) {
      return
    }

    const visibleTop =
      container.scrollTop

    const visibleBottom =
      visibleTop +
      container.clientHeight

    const targetTop =
      target.offsetTop

    const targetBottom =
      targetTop +
      target.offsetHeight

    const isVisible =
      targetTop >= visibleTop &&
      targetBottom <= visibleBottom

    if (isVisible) {
      return
    }

    container.scrollTo({
      top:
        targetTop -
        container.clientHeight / 2 +
        target.offsetHeight / 2,
      behavior: 'smooth',
    })
  },
)
</script>

<style scoped>
.message-scrollbar {
  position: fixed;
  right: 20px;
  top: 50%;
  transform: translateY(-50%);

  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 16px;

  width: 14px;
  height: fit-content;
  max-height: 500px;

  border-radius: var(--apix-panel-border-radius);
  overflow-y: auto;

  backdrop-filter: saturate(180%) blur(16px);
  background-color: color-mix(
    in srgb,
    var(--apix-panel-layer-1-background) 50%,
    transparent
  ) !important;

  transition:
    width 0.6s var(--apix-cubic-bezier),
    mask-image 0.3s ease;

  z-index: 10;

  scrollbar-width: none;

  /* Top & bottom fade */
  mask-image: linear-gradient(
    to bottom,
    transparent 0%,
    black 20%,
    black 80%,
    transparent 100%
  );
}

.message-scrollbar::-webkit-scrollbar {
  display: none;
}

.message-scrollbar:hover {
  width: 280px;

  box-shadow: var(--apix-shadow-layer-2);

  /* Hover时取消遮罩 */
  mask-image: none;
}

.scroll-item {
  display: flex;
  align-items: center;
  min-height: 20px;
  cursor: pointer;
  /* justify-content: space-between; */
}

.tick-wrapper {
  width: 12px;
  min-width: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.tick {
  flex-shrink: 0;

  width: 8px;
  height: 2px;

  border-radius: 999px;

  background: var(--apix-secondary-light-color);

  transition: all 0.15s ease;
}

.scroll-item:hover .tick {
  width: 12px;
  background: var(--apix-tertiary-dark-color);
}

.scroll-item.active .tick {
  width: 12px;
  background: var(--apix-primary-active);
}

.preview {
  margin-left: 10px;

  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;

  font-size: 12px;
  color: var(--apix-secondary-dark-color);

  user-select: none;
}

.scroll-item.active .preview {
  color: var(--apix-primary-active);
  font-weight: 500;
}

.preview-fade-enter-active,
.preview-fade-leave-active {
  transition: all .6s ease;
}

.preview-fade-enter-from,
.preview-fade-leave-to {
  opacity: 0;
  transform: translateX(-4px);
}
</style>