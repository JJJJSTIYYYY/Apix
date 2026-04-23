<template>
  <Teleport to="body">
    <div class="md-displayer-mask" @click.self="close">
      <div class="md-displayer-dialog">
        <!-- Header -->
        <header class="md-displayer-header">
          <span class="md-displayer-title">{{ title }}</span>
          <div class="btn-area">
            <div class="mode-switch">
              <div class="slider" :class="{ right: !isPlain }" />
              <button @click="switchMode('plain')" class="plain-select" :class="{ right: !isPlain }">Plain</button>
              <button @click="switchMode('highlight')" class="highlight-select" :class="{ right: !isPlain }">Light</button>
            </div>
            <button class="md-displayer-close" @click="close">×</button>
          </div>
        </header>

        <!-- Content -->
        <section class="md-displayer-content selectable">
          <div
            class="markdown-body"
            v-html="result"
          ></div>
        </section>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import MarkdownIt from 'markdown-it'
import hljs from 'highlight.js'

import 'github-markdown-css/github-markdown.css'
import 'highlight.js/styles/github.css'

// ------------------------
// Props
// ------------------------
const props = defineProps<{
  title: string
  content: string
  options?: Record<string, any>
}>()

const emit = defineEmits<{
  (e: 'close'): void
}>()

function close() {
  emit('close')
}

// ------------------------
// Markdown instance
// ------------------------
const md = new MarkdownIt({
  html: true,
  linkify: true,
  highlight(code, lang) {
    const raw = md.utils.escapeHtml(code)

    let highlighted = ''

    try {
      // ------------------------
      // Plain mode: force plaintext
      // ------------------------
      if (isPlain.value) {
        highlighted = hljs.highlight(code, {
          language: 'plaintext',
          ignoreIllegals: true
        }).value
      }
      // ------------------------
      // Highlight mode
      // ------------------------
      else if (lang && hljs.getLanguage(lang)) {
        highlighted = hljs.highlight(code, {
          language: lang,
          ignoreIllegals: true
        }).value
      } else {
        highlighted = hljs.highlightAuto(code).value
      }
    } catch {
      highlighted = raw
    }

    return `<div class="code-block"><button class="code-copy-btn" type="button" data-code="${raw}">复制</button><pre class="hljs"><code>${highlighted}</code></pre></div>`
  }
})

// ------------------------
// Render result
// ------------------------
const result = computed(() => {
  return md.render(props.content)
})

const isPlain = computed(() => mode.value === "plain")
const mode = ref("plain") // plain | highlight
const switchMode = (target) => {
  if (mode.value === target) return
  mode.value = target
}

// ------------------------
// Code copy handler (delegated)
// ------------------------
function onCodeCopyClick(e: Event) {
  const target = e.target as HTMLElement
  const btn = target.closest('.code-copy-btn') as HTMLButtonElement | null
  if (!btn) return

  const code = btn.getAttribute('data-code')
  if (!code) return

  navigator.clipboard.writeText(code)

  btn.textContent = '复制了'
  btn.style.width = '55px'
  btn.style.background = 'rgba(94, 214, 200, 0.36)'

  setTimeout(() => {
    btn.textContent = '复制'
    btn.style.width = '44px'
    btn.style.background = 'rgba(207, 212, 212, 0.36)'
  }, 1000)
}

onMounted(() => {
  document.addEventListener('click', onCodeCopyClick)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', onCodeCopyClick)
})
</script>

<style scoped>
.markdown-body :deep(pre) {
  margin: 0 !important;
  padding: 0px 6px;
}

.markdown-body :deep(pre > code) {
  display: block;
  padding: 0;
  margin: 0;
  line-height: 1.5;
}

:deep(.code-block) {
  position: relative;
  margin: 12px 0; /* 只在这里控制 */
}

/* ------------------------
   Mask
------------------------- */
.md-displayer-mask {
  position: absolute;
  width: 100vw;
  height: 100vh;
  inset: 0;
  z-index: 9999;

  display: flex;
  align-items: center;
  justify-content: center;

  background: rgba(0, 0, 0, 0.35);
  backdrop-filter: blur(6px);
  animation: opacityFadeIn .5s cubic-bezier(0.22, 1, 0.36, 1);
}

@keyframes opacityFadeIn {
  0% { 
    opacity: 0.3; 
  }
  100% { 
    opacity: 1; 
  }
}

/* ------------------------
   Dialog
------------------------- */
.md-displayer-dialog {
  width: min(900px, 92vw);
  max-height: 86vh;

  background: rgba(255, 255, 255, 0.92);
  border-radius: 16px;

  display: flex;
  flex-direction: column;
  overflow: hidden;
  animation: scaleFadeIn .5s cubic-bezier(0.22, 1, 0.36, 1);
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

/* ------------------------
   Header
------------------------- */
.md-displayer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;

  padding: 20px 18px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
}

.md-displayer-title {
  font-size: 16px;
  font-weight: 600;
}

.md-displayer-close {
  width: 28px;
  height: 28px;
  border-radius: 8px;

  border: none;
  cursor: pointer;
  font-size: 18px;
  line-height: 1;

  background: rgba(0, 0, 0, 0.05);
}

.md-displayer-close:hover {
  color: #be0e0e;
  background: rgba(255, 47, 0, 0.196);
}

.md-displayer-close:active {
  transform: scale(0.9);
}

/* ------------------------
   Content
------------------------- */
.md-displayer-content {
  padding: 16px 18px;
  overflow: auto;
}

/* ------------------------
   Markdown
------------------------- */
.markdown-body {
  background: transparent;
}

/* ------------------------
   Code block
------------------------- */
:deep(.code-block) {
  position: relative;
  margin: 14px 0;
}

:deep(.hljs) {
  padding: 16px !important;
  border-radius: 12px;
  margin: 0;
  background-color: rgba(208, 208, 208, 0.1);
}

/* ------------------------
   Copy button
------------------------- */
:deep(.code-copy-btn) {
  position: absolute;
  top: 8px;
  right: 8px;

  width: 44px;
  height: 24px;
  font-size: 12px;

  border-radius: 8px;
  border: none;
  cursor: pointer;

  background: rgba(207, 212, 212, 0.36);
  color: #0000009b;

  opacity: 0;
  transition:
    opacity 0.15s ease,
    width 0.15s cubic-bezier(0.34, 2.5, 0.64, 1),
    background-color 0.05s ease;
}

:deep(.code-block:hover .code-copy-btn) {
  opacity: 1;
}

.btn-area {
  display: flex;
  align-items: center;
  gap: 24px;
}

.mode-switch {
  position: relative;
  display: flex;
  background: rgba(226, 226, 226, 0.32);
  border-radius: 999px;
  border: 1px solid rgba(213, 213, 213, 0.318);
  box-shadow: inset 1px -1px 16px rgba(117, 187, 248, 0.083);
}

.mode-switch button {
  flex: 1;
  height: 24px;
  border: none;
  background-color: transparent;
  cursor: pointer;
  z-index: 1;
  font-size: 12px;
  color: #4040409A;
  transition: color 0.25s ease;
}

.mode-switch button.active {
  color: #0000009A;
}

.mode-switch:active:deep(.slider) {
  z-index: 999;
  box-shadow:
    0 8px 24px rgba(62, 67, 66, 0.12),
    0 0 0 2px color-mix(in srgb, rgba(136, 202, 196, 0.567) 25%, transparent);
  -webkit-backdrop-filter: saturate(180%) blur(16px);
  backdrop-filter: saturate(180%) blur(3px);
  -webkit-transition: all 0.3s cubic-bezier(0.215, 0.61, 0.355, 1);
  transition: all 0.3s cubic-bezier(0.215, 0.61, 0.355, 1);
  background-color: color-mix(in srgb, #ebebeb83 1%, transparent);
}

.highlight-select {
  color: #4040409A;
  transition: color 0.25s ease;
}

.highlight-select.right {
  color: #0000009A;
  transition: color 0.25s ease;
}

/* Slider */
.slider {
  position: absolute;
  width: calc(50% + 4px);
  height: calc(100% + 2px);
  margin-top: -1px;
  margin-left: -1px;
  border-radius: 32px;
  transition: all 0.3s cubic-bezier(0.215, 0.61, 0.355, 1);
  box-shadow:
    0 8px 24px rgba(62, 67, 66, 0.12),
    0 0 0 2px rgba(136, 202, 196, 0.471);
  background-color: #ffffff2c;
}

.slider.right {
  transform: translateX(88%);
}

.mode-switch:active:deep(.slider) {
  z-index: 999;
  box-shadow:
    0 8px 24px rgba(62, 67, 66, 0.12),
    0 0 0 2px color-mix(in srgb, rgba(136, 202, 196, 0.567) 25%, transparent);
  -webkit-backdrop-filter: saturate(180%) blur(16px);
  backdrop-filter: saturate(180%) blur(3px);
  -webkit-transition: all 0.3s cubic-bezier(0.215, 0.61, 0.355, 1);
  transition: all 0.3s cubic-bezier(0.215, 0.61, 0.355, 1);
  background-color: color-mix(in srgb, #ebebeb83 1%, transparent);
}
</style>
