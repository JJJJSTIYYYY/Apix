<template>
  <Teleport to="body">
    <Transition name="cd">
      <div 
        v-if="visible"
        class="md-displayer-mask" 
        @click.self="close"
      >
        <div class="md-displayer-dialog">
          <!-- Header -->
          <header class="md-displayer-header">
            <span class="md-displayer-title">{{ title }}</span>
            <div class="btn-area">
              <button class="md-displayer-close" @click="close">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1024 1024"><path fill="currentColor" d="M764.288 214.592 512 466.88 259.712 214.592a31.936 31.936 0 0 0-45.12 45.12L466.752 512 214.528 764.224a31.936 31.936 0 1 0 45.12 45.184L512 557.184l252.288 252.288a31.936 31.936 0 0 0 45.12-45.12L557.12 512.064l252.288-252.352a31.936 31.936 0 1 0-45.12-45.184z"></path></svg>
              </button>
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
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import MarkdownIt from 'markdown-it'
import hljs from 'highlight.js'

import 'github-markdown-css/github-markdown.css'
// import 'highlight.js/styles/github.css'

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

async function close() {
  visible.value = false
  await nextTick()
  emit('close')
}

const visible = ref(false)

// ------------------------
// Markdown instance
// ------------------------
const md = new MarkdownIt({
  html: true,
  linkify: true,
  highlight(code, lang) {
    let highlighted = ''
    let languageClass = ''

    try {
      if (lang && hljs.getLanguage(lang)) {
        highlighted = hljs.highlight(code, {
          language: lang,
          ignoreIllegals: true,
        }).value
        languageClass = `language-${lang}`
      } else {
        const auto = hljs.highlightAuto(code)
        highlighted = auto.value
        languageClass = auto.language ? `language-${auto.language}` : ''
      }
    } catch {
      highlighted = md.utils.escapeHtml(code)
      languageClass = ''
    }

    const raw = md.utils.escapeHtml(code)

    return `<div class="code-block"><button class="code-copy-btn" data-code="${raw}" type="button">${copy_svg.value}</button><code class="hljs ${languageClass}">${highlighted}</code></div>`
  },
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

const copy_svg = ref(
  `<svg t="1772102283255" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="11499" width="200" height="200"><path d="M624.5 786.3c92.9 0 168.2-75.3 168.2-168.2V309c0-92.4-75.3-168.2-168.2-168.2H303.6c-92.4 0-168.2 75.3-168.2 168.2v309.1c0 92.4 75.3 168.2 168.2 168.2h320.9zM178.2 618.1V309c0-69.4 56.1-125.5 125.5-125.5h320.9c69.4 0 125.5 56.1 125.5 125.5v309.1c0 69.4-56.1 125.5-125.5 125.5h-321c-69.4 0-125.4-56.1-125.4-125.5z" p-id="11500"></path><path d="M849.8 295.1v361.5c0 102.7-83.6 186.3-186.3 186.3H279.1v42.7h384.4c126.3 0 229.1-102.8 229.1-229.1V295.1h-42.8zM307.9 361.8h312.3c11.8 0 21.4-9.6 21.4-21.4 0-11.8-9.6-21.4-21.4-21.4H307.9c-11.8 0-21.4 9.6-21.4 21.4 0 11.9 9.6 21.4 21.4 21.4zM307.9 484.6h312.3c11.8 0 21.4-9.6 21.4-21.4 0-11.8-9.6-21.4-21.4-21.4H307.9c-11.8 0-21.4 9.6-21.4 21.4 0 11.9 9.6 21.4 21.4 21.4z" p-id="11501"></path><path d="M620.2 607.4c11.8 0 21.4-9.6 21.4-21.4 0-11.8-9.6-21.4-21.4-21.4H307.9c-11.8 0-21.4 9.6-21.4 21.4 0 11.8 9.6 21.4 21.4 21.4h312.3z" p-id="11502"></path></svg>`
)

function onCodeCopyClick(e: Event) {
  const target = e.target as HTMLElement
  const btn = target.closest('.code-copy-btn')
  if (!btn) return

  const code = btn.getAttribute('data-code')
  if (!code) return

  navigator.clipboard.writeText(code)
  copy_svg.value =
    `<svg t="1772103245365" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="12505" width="200" height="200"><path d="M911.075556 192.796444a45.511111 45.511111 0 0 1 5.518222 64.113778l-455.111111 540.444445a45.511111 45.511111 0 0 1-68.835556 0.910222l-227.555555-256a45.511111 45.511111 0 0 1 68.039111-60.472889l192.625777 216.689778 421.205334-500.224a45.511111 45.511111 0 0 1 64.113778-5.461334z" p-id="12506"></path></svg>`

  setTimeout(() => {
    copy_svg.value =
      `<svg t="1772102283255" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="11499" width="200" height="200"><path d="M624.5 786.3c92.9 0 168.2-75.3 168.2-168.2V309c0-92.4-75.3-168.2-168.2-168.2H303.6c-92.4 0-168.2 75.3-168.2 168.2v309.1c0 92.4 75.3 168.2 168.2 168.2h320.9zM178.2 618.1V309c0-69.4 56.1-125.5 125.5-125.5h320.9c69.4 0 125.5 56.1 125.5 125.5v309.1c0 69.4-56.1 125.5-125.5 125.5h-321c-69.4 0-125.4-56.1-125.4-125.5z" p-id="11500"></path><path d="M849.8 295.1v361.5c0 102.7-83.6 186.3-186.3 186.3H279.1v42.7h384.4c126.3 0 229.1-102.8 229.1-229.1V295.1h-42.8zM307.9 361.8h312.3c11.8 0 21.4-9.6 21.4-21.4 0-11.8-9.6-21.4-21.4-21.4H307.9c-11.8 0-21.4 9.6-21.4 21.4 0 11.9 9.6 21.4 21.4 21.4zM307.9 484.6h312.3c11.8 0 21.4-9.6 21.4-21.4 0-11.8-9.6-21.4-21.4-21.4H307.9c-11.8 0-21.4 9.6-21.4 21.4 0 11.9 9.6 21.4 21.4 21.4z" p-id="11501"></path><path d="M620.2 607.4c11.8 0 21.4-9.6 21.4-21.4 0-11.8-9.6-21.4-21.4-21.4H307.9c-11.8 0-21.4 9.6-21.4 21.4 0 11.8 9.6 21.4 21.4 21.4h312.3z" p-id="11502"></path></svg>`
  }, 2000)
}

onMounted(() => {
  visible.value = true
  document.addEventListener('click', onCodeCopyClick)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', onCodeCopyClick)
})
</script>

<style scoped>
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

/* ------------------------
   Dialog
------------------------- */
.md-displayer-dialog {
  width: min(900px, 92vw);
  max-height: 86vh;

  background: var(--apix-lightest-color);
  border-radius: var(--apix-panel-border-radius);
  color: var(--apix-default-dark-color);

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

/* ------------------------
   Header
------------------------- */
.md-displayer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;

  padding: 20px 18px;
  border-bottom: 1px solid var(--apix-border-light);
}

.md-displayer-title {
  font-size: 16px;
  font-weight: 600;
}

.md-displayer-close {
  width: 28px;
  height: 28px;
  border-radius: var(--apix-button-border-radius);
  color: var(--apix-default-dark-color);

  border: none;
  cursor: pointer;
  font-size: 18px;
  line-height: 1;

  background: var(--apix-default-light-color);
}

.md-displayer-close:hover {
  color: var(--apix-danger-color);
  background: var(--apix-danger-light);
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
.md-displayer-content::-webkit-scrollbar {
  width: 6px;
}
.md-displayer-content::-webkit-scrollbar-track {
  background: transparent;
}
.md-displayer-content::-webkit-scrollbar-thumb {
  background-color: rgba(156, 163, 175, 0.5);
  border-radius: 3px;
}
.md-displayer-content::-webkit-scrollbar-thumb:hover {
  background-color: rgba(156, 163, 175, 0.8);
}
.md-displayer-content::-webkit-scrollbar-horizontal {
  display: none;
  height: 0;
}

/* ------------------------
   Copy button
------------------------- */
:deep(.code-copy-btn) {
  position: absolute;
  top: 1px;
  right: 1px;

  width: 44px;
  height: 24px;
  font-size: 12px;

  border-radius: var(--apix-button-border-radius);
  border: none;
  cursor: pointer;

  background: var(--apix-default-light-color);
  color: var(--apix-default-dark-color);

  opacity: 0;
  transition:
    opacity 0.15s ease,
    width 0.15s var(--apix-cubic-bezier),
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
</style>

<style scoped>
/* ==================== Markdown 通用表格/代码块增强 ==================== */
.markdown-body {
  background-color: transparent;
  color: var(--apix-default-dark-color)
}

.markdown-body:deep(table) {
  position: relative;
  /* margin: auto; */
  /* margin-bottom: 12px; */
  /* border-radius: var(--apix-panel-border-radius) !important; */
  background-color: var(--apix-panel-layer-2-background) !important;
  /* box-shadow: inset 0 0 0 1px var(--apix-tertiary-dark-color); */
  /* border: 1px solid var(--apix-tertiary-dark-color); */
}
.markdown-body:deep(thead) {
  width: auto;
  background-color: var(--apix-default-light-color) !important;
}
.markdown-body:deep(th) {
  width: auto;
  background-color: transparent !important;
  border: 1px solid var(--apix-tertiary-light-color);
}
.markdown-body:deep(tbody) {
  width: auto !important;
  background-color: transparent !important;
}
.markdown-body:deep(tr) {
  width: auto;
  background-color: transparent !important;
}
.markdown-body:deep(td) {
  width: auto;
  background-color: transparent !important;
  border: 1px solid var(--apix-tertiary-light-color);
}

.markdown-body:deep(pre) {
  scrollbar-width: none;
  background-color: var(--apix-panel-layer-2-background);
  /* border-radius: var(--apix-panel-border-radius); */
  padding: 16px;
  /* margin-bottom: 0; */
}

.markdown-body:deep(blockquote) {
  border-left: .25em solid var(--apix-border-hover);
  color: var(--apix-tertiary-dark-color);
}

.markdown-body:deep(hr) {
  background-color: var(--apix-border-hover);
  opacity: 0.6;
}

.markdown-body:deep(h2) {
  border-bottom: 1px solid color-mix(in srgb, var(--apix-border-hover) 50%, transparent);
}

/* ==================== 代码块相关 ==================== */
:deep(.code-block) {
  position: relative !important;
  height: fit-content !important;
}

:deep(.code-copy-btn) {
  position: absolute;
  top: 8px;
  right: 8px;
  padding: 0px;
  font-size: 12px;
  border-radius: 8px;
  width: 24px;
  height: 24px;
  background: transparent;
  color: var(--apix-secondary-dark-color);
  border: none;
  cursor: pointer;
  opacity: 0;
  z-index: 999;
}

:deep(.code-copy-btn .icon) {
  width: 24px;
  height: 24px;
  fill: var(--apix-secondary-dark-color);
}

:deep(.code-block:hover .code-copy-btn) {
  opacity: 1;
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