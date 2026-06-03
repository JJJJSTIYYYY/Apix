<template>
  <div class="selection-bubble" ref="wrapperRef">
    <button @mousedown.prevent @click="onCpoy" class="selection-bubble-btn">
      <svg t="1776850628571" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="11646" width="14" height="14"><path d="M176.219429 766.994286h79.707428v73.728c0 88.283429 44.580571 132.845714 134.582857 132.845714h457.691429c89.161143 0 134.162286-44.562286 134.162286-132.845714V385.152c0-87.862857-45.001143-132.443429-134.144-132.443429h-79.725715v-69.430857c0-88.283429-44.982857-132.845714-134.582857-132.845714H176.237714c-89.581714 0-134.582857 44.562286-134.582857 132.845714v451.291429c0 88.283429 45.001143 132.425143 134.582857 132.425143z m1.28-68.992c-42.861714 0-66.852571-22.710857-66.852572-67.291429V187.136c0-44.562286 23.990857-67.712 66.852572-67.712h455.570285c42.002286 0 66.432 23.149714 66.432 67.712v65.572571H390.509714c-90.002286 0-134.582857 44.141714-134.582857 132.425143v312.868572z m213.851428 206.573714c-42.843429 0-66.432-23.149714-66.432-67.712V388.992c0-44.562286 23.588571-67.291429 66.432-67.291429h455.570286c42.422857 0 66.432 22.729143 66.432 67.291429V837.302857c0 44.141714-23.990857 67.291429-66.432 67.291429z" fill="var(--apix-default-dark-color)" p-id="11647"></path></svg>
      复制
    </button>
    <div style="width: 1px; background-color: black; height: 22px;"></div>
    <button @mousedown.prevent @click="onAsk" class="selection-bubble-btn">
      <svg t="1776850336751" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="5296" width="16" height="16"><path d="M460.8 460.361143c54.418286 0 99.84-36.425143 99.84-94.281143 0-54.857143-37.284571-90.88-88.283429-90.88-26.148571 0-46.281143 10.294857-58.697142 30.006857 13.275429-60.854857 59.117714-101.12 121.270857-103.698286 16.713143-0.859429 28.708571-12.434286 28.708571-28.708571 0-19.730286-15.853714-30.006857-37.284571-30.006857-96.420571 0-182.125714 82.285714-182.125715 190.72 0 77.129143 51.419429 126.848 116.553143 126.848z m-262.308571 0c54.436571 0 99.858286-36.425143 99.858285-94.281143 0-54.857143-37.705143-90.88-88.704-90.88-25.709714 0-46.281143 10.294857-58.715428 30.006857 13.275429-60.854857 59.574857-100.699429 121.709714-103.698286 16.274286-0.859429 28.708571-12.434286 28.708571-28.708571 0-19.730286-16.274286-30.006857-37.705142-30.006857-96.420571 0-182.144 82.285714-182.144 190.72 0 77.129143 51.858286 126.848 116.992 126.848zM669.074286 207.908571h241.700571c18.432 0 33.005714-14.134857 33.005714-32.566857 0-18.011429-14.573714-32.146286-32.987428-32.146285h-241.737143a31.817143 31.817143 0 0 0-32.128 32.146285c0 18.432 14.134857 32.566857 32.146286 32.566857z m0 224.566858h241.700571c18.432 0 33.005714-14.134857 33.005714-32.548572 0-18.011429-14.573714-32.164571-32.987428-32.164571h-241.737143a31.817143 31.817143 0 0 0-32.128 32.146285c0 18.432 14.134857 32.566857 32.146286 32.566858zM112.786286 657.078857h797.988571a32.658286 32.658286 0 0 0 33.005714-32.585143c0-17.993143-14.573714-32.146286-32.987428-32.146285H112.786286c-18.432 0-32.566857 14.153143-32.566857 32.146285 0 18.011429 14.134857 32.585143 32.548571 32.585143z m0 224.128h797.988571c18.432 0 33.005714-14.134857 33.005714-32.128 0-18.011429-14.573714-32.585143-32.987428-32.585143H112.786286a32.292571 32.292571 0 0 0-32.566857 32.585143c0 17.993143 14.134857 32.128 32.548571 32.128z" fill="var(--apix-default-dark-color)" p-id="5297"></path></svg>
      引用
    </button>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { globalSelection } from '../../../../store/globalData.js'

const emit = defineEmits<{
  closeBubble: void
  copyValue: [content: string]
  quoteContent: [content: string]
}>()

const wrapperRef = ref<HTMLElement | null>(null)

function onAsk() {
  console.log("Ask quated: ", globalSelection.content)
  if (globalSelection.content !== '') {
    emit("quoteContent", globalSelection.content)
  }

  globalSelection.content = ''
  globalSelection.id = ''
  globalSelection.role = ''
  globalSelection.rect = null

  emit("closeBubble")
}

function onCpoy() {
  if (globalSelection.content !== '') {
    window.api?.copyToClipboard({ type: 'text', data: globalSelection.content })
    emit("copyValue", globalSelection.content)
  }

  globalSelection.content = ''
  globalSelection.id = ''
  globalSelection.role = ''
  globalSelection.rect = null

  emit("closeBubble")
}
</script>

<style scoped>
.selection-bubble {
  transform: translate(-50%, -100%);
  position: fixed;
  background: var(--apix-panel-layer-5-background);
  color: var(--apix-default-dark-color);
  padding: 4px;
  border-radius: 8px;
  font-size: 13px;
  cursor: default;
  white-space: nowrap;
  z-index: 2000;
  box-shadow: var(--apix-shadow-layer-3);
  display: flex;
  gap: 4px;
  align-items: center;
  user-select: none;
  animation: opacityFadeIn .25s var(--apix-cubic-bezier);
}

@keyframes opacityFadeIn {
  0% { 
    opacity: 0; 
    transform: translate(-50%, -100%) scale(0.9); 
  }
  60% { 
    opacity: 1; 
    transform: translate(-50%, -100%) scale(1.03); 
  }
  100% { 
    opacity: 1; 
    transform: translate(-50%, -100%) scale(1); 
  }
}

/* 按钮样式 */
.selection-bubble-btn {
  display: flex;
  align-items: center;
  gap: 3px;
  background: transparent;
  color: var(--apix-default-dark-color);
  border: none;
  padding: 4px 12px;
  border-radius: 6px;
  font-size: 13px;
  line-height: 1.5;
  cursor: pointer;
  white-space: nowrap;
  transition: background 0.15s var(--apix-cubic-bezier);
}

.selection-bubble-btn:hover {
  background: var(--apix-default-light-color);
}

.selection-bubble::after {
  content: '';
  position: absolute;
  left: 50%;
  bottom: -5px;
  transform: translateX(-50%);
  width: 0;
  height: 0;
  border-left: 6px solid transparent;
  border-right: 6px solid transparent;
  border-top: 6px solid var(--apix-panel-layer-5-background);
}
</style>