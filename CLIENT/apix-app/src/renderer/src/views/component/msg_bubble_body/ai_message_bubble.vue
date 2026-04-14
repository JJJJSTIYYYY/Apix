<template>
  <div class="ai-bubble-wrapper">
    <!-- Think -->
    <div class="think-block" v-if="hasThink">
      <div class="think-border-point">
        <svg
          t="1772097763053"
          class="icon"
          viewBox="0 0 1024 1024"
          version="1.1"
          xmlns="http://www.w3.org/2000/svg"
          p-id="6531"
          width="200"
          height="200"
        >
          <path d="M717.12 274H762c82.842 0 150 67.158 150 150v200c0 82.842-67.158 150-150 150H262c-82.842 0-150-67.158-150-150V424c0-82.842 67.158-150 150-150h44.88l-18.268-109.602c-4.086-24.514 12.476-47.7 36.99-51.786 24.514-4.086 47.7 12.476 51.786 36.99l20 120c0.246 1.472 0.416 2.94 0.516 4.398h228.192c0.1-1.46 0.27-2.926 0.516-4.398l20-120c4.086-24.514 27.272-41.076 51.786-36.99 24.514 4.086 41.076 27.272 36.99 51.786L717.12 274zM262 364c-33.138 0-60 26.862-60 60v200c0 33.138 26.862 60 60 60h500c33.138 0 60-26.862 60-60V424c0-33.138-26.862-60-60-60H262z m50 548c-24.852 0-45-20.148-45-45S287.148 822 312 822h400c24.852 0 45 20.148 45 45S736.852 912 712 912H312z m-4-428c0-24.852 20.148-45 45-45S398 459.148 398 484v40c0 24.852-20.148 45-45 45S308 548.852 308 524v-40z m318 0c0-24.852 20.148-45 45-45S716 459.148 716 484v40c0 24.852-20.148 45-45 45S626 548.852 626 524v-40z" fill="#325effcf" p-id="6532"></path>
        </svg>
      </div>

      <button
        class="expend-think-btn"
        :class="{ breath: msg.label === '思考中...' && !hasError }"
        @click="triggerThinkVisiable"
      >
        <svg
          t="1768987348872"
          class="icon"
          v-if="msg.label !== '思考中...'"
          viewBox="0 0 1024 1024"
          version="1.1"
          xmlns="http://www.w3.org/2000/svg"
          p-id="5007"
          width="200"
          height="200"
        >
          <path d="M526.464 85.717333L512 170.624a256 256 0 0 0-199.936 415.957333c3.669333 4.522667 34.389333 36.394667 39.125333 41.557334 42.538667 46.250667 68.693333 88.576 74.325334 139.861333h172.970666c5.632-51.285333 31.786667-93.610667 74.24-139.818667 4.821333-5.248 35.413333-36.949333 39.125334-41.514666A254.549333 254.549333 0 0 0 768 426.666667l84.906667-14.506667c0.213333 4.821333 0.426667 9.642667 0.426666 14.506667a339.882667 339.882667 0 0 1-74.922666 213.333333c-26.453333 33.024-95.744 85.333333-95.744 149.333333V896a85.333333 85.333333 0 0 1-85.333334 85.333333h-170.666666a85.333333 85.333333 0 0 1-85.333334-85.333333v-106.666667c0-64-69.333333-116.352-95.829333-149.376a341.333333 341.333333 0 0 1 280.96-554.24zM426.666667 895.957333h170.666666v-42.666666h-170.666666v42.666666zM747.946667 14.08a21.632 21.632 0 0 1 40.106666 0l10.837334 26.026667a186.325333 186.325333 0 0 0 96 99.285333l30.634666 13.610667a22.613333 22.613333 0 0 1 0 41.088l-32.426666 14.421333a186.154667 186.154667 0 0 0-94.634667 96l-10.538667 24.149333a21.589333 21.589333 0 0 1-39.850666 0l-10.496-24.106666a186.197333 186.197333 0 0 0-94.72-96.042667l-32.426667-14.421333a22.613333 22.613333 0 0 1 0-41.088l30.634667-13.653334A186.282667 186.282667 0 0 0 737.109333 40.106667l10.794667-26.026667z" p-id="5008"></path>
        </svg>
        <svg
          t="1769187199002"
          class="icon-thinking"
          v-else
          viewBox="0 0 1024 1024"
          version="1.1"
          xmlns="http://www.w3.org/2000/svg"
          p-id="7536"
          width="200"
          height="200"
        >
          <path d="M554.688 377.6A199.232 199.232 0 0 0 673.28 490.24l180.032 64.448-197.12 78.528a213.312 213.312 0 0 0-121.6 125.44l-65.28 180.032-45.184-137.408a305.536 305.536 0 0 0-189.44-193.728L85.312 554.688 193.28 522.24A337.28 337.28 0 0 0 411.776 320l57.536-149.312L554.688 377.6z m-85.376-1.28A418.176 418.176 0 0 1 307.2 554.688 384 384 0 0 1 469.312 714.24a290.176 290.176 0 0 1 157.056-152.32l8.064-3.392a277.76 277.76 0 0 1-152.32-151.488l-12.8-30.72zM896 334.528a34.56 34.56 0 0 0 19.2 19.584l31.168 11.136-34.176 13.632a36.416 36.416 0 0 0-20.864 21.76l-11.52 31.552-7.68-23.872a53.824 53.824 0 0 0-32.896-33.664l-25.984-9.408L832 359.68a59.392 59.392 0 0 0 38.016-35.008l9.792-25.984L896 334.528zM768 141.632a56.896 56.896 0 0 0 32.448 29.888l49.024 17.472-53.76 21.376a58.56 58.56 0 0 0-33.28 34.112l-17.472 49.088L732.544 256a85.312 85.312 0 0 0-49.856-51.648L640 190.272l29.44-7.232A92.736 92.736 0 0 0 729.216 128l15.744-42.688 23.04 56.32z" fill="#1A5EFF" p-id="7537"></path>
        </svg>
        <div>{{ hasError ? '已停止思考' : msg.label }}</div>
      </button>

      <div class="think-border-line" :class="{ thinkVisiable: isThinkVisiable }"></div>

      <div style="display: flex; flex-direction: column;">
        <transition name="scale-fade-height">
          <div v-if="isThinkVisiable" class="think-render-list">
            <template v-for="item in thinkRenderItems" :key="item.key">
              <ToolLabelCard
                v-if="item.kind === 'tool' && store.config.showToolLabels"
                :tool_call_id="item.tool.tool_call_id"
                :content="item.tool.content"
                :status="item.tool.status"
              />
              <div
                v-else
                v-html="item.html"
                class="markdown-body think selectable"
              ></div>
            </template>
          </div>
        </transition>
      </div>
    </div>

    <!-- Todos -->
    <div class="expend-todos-btn-wrapper">
      <button
        class="expend-todos-btn"
        @click="triggerTodosVisiable"
        v-if="msg.todos && msg.todos.length > 0"
      >
        <svg
          t="1772267075760"
          class="icon"
          viewBox="0 0 1024 1024"
          version="1.1"
          xmlns="http://www.w3.org/2000/svg"
          p-id="5085"
          width="200"
          height="200"
        >
          <path d="M0.831169 345.766234c0 109.252156 88.566026 197.818182 197.818182 197.818182 109.252156 0 197.818182-88.566026 197.818181-197.818182 0-109.252156-88.566026-197.818182-197.818181-197.818182C89.397195 147.948052 0.831169 236.514078 0.831169 345.766234z" fill="#68df78" p-id="5086" data-spm-anchor-id="a313x.search_index.0.i4.78ef3a811GNESF" class="selected"></path>
          <path d="M273.255065 960.831169H1023.168831v-99.351273H273.255065V960.831169z m0-317.476572H1023.168831v-99.351272H273.255065v99.351272zM2.493506 332.284675l72.76052-66.912415 103.726545 114.948987L455.749818 64.831169l73.844364 65.821922-349.529766 398.296104L2.493506 332.284675z m626.835949-6.458181H1023.168831V226.476883H629.329455v99.349611z" fill="#2b7af2" p-id="5087" data-spm-anchor-id="a313x.search_index.0.i3.78ef3a811GNESF" class=""></path>
        </svg>
        <div style="display: flex; align-items: center;">已生成执行计划（{{ msg.todos.length }}）</div>
      </button>
    </div>

    <transition name="fade">
      <div class="todos-block" v-if="msg.todos && msg.todos.length > 0 && isTodosVisiable">
        <div v-for="item in displayTodos" class="todo-card" :key="`${item.content}-${item.status}`">
          <TodoCard :content="item.content" :status="item.status" :pending="msg.pending" />
        </div>
      </div>
    </transition>

    <!-- Response -->
    <div
      class="ai-bubble selectable"
      @contextmenu.prevent="onContextMenu"
      v-if="hasContent"
    >
      <template v-for="item in contentRenderItems" :key="item.key">
        <ToolLabelCard
          v-if="item.kind === 'tool' && store.config.showToolLabels"
          :tool_call_id="item.tool.tool_call_id"
          :content="item.tool.content"
          :status="item.tool.status"
        />
        <div
          v-else
          v-html="item.html"
          class="markdown-body content"
          style="background: transparent;"
        ></div>
      </template>
    </div>

    <!-- Images -->
    <div class="ai-images-wrapper" v-if="imageItems.length > 0">
      <div class="ai-images-scroller">
        <div class="ai-images">
          <div class="ai-image-card" v-for="item in imageItems" :key="item.fileId">
            <div v-if="item.loading" class="ai-image-loading">
              Loading...
            </div>

            <div v-else-if="item.error" class="ai-image-error">
              Load Failed
            </div>

            <template v-else-if="item.src">
              <img
                class="ai-image"
                :src="item.src"
                :alt="`image-${item.fileId}`"
                loading="lazy"
                @click="previewImage(item)"
              />

              <div class="ai-image-hover-preview">
                <img
                  class="ai-image-preview"
                  :src="item.src"
                  :alt="`preview-${item.fileId}`"
                />
              </div>
            </template>
          </div>
        </div>
      </div>
    </div>

    <!-- Info tag -->
    <div class="info-tag" :class="{ show: !msg.pending }">
      <div class="tag-wrapper">
        <div class="tag-name">Provider:</div>
        <div>{{ msg.info?.model_provider }}</div>
      </div>
      <div class="tag-wrapper">
        <div class="tag-name">Model:</div>
        <div>{{ msg.info?.model }}</div>
      </div>
      <div class="tag-wrapper">
        <div class="tag-name">Tokens:</div>
        <div>{{ msg.info?.total_tokens ?? 'N/A' }}</div>
      </div>
      <div class="tag-wrapper">
        <div class="tag-name">Duration:</div>
        <div>{{ msg.info?.total_duration ?? 'N/A' }}</div>
      </div>
      <div
        class="tag-wrapper"
        v-if="msg.extra?.link_provider?.length > 0 || msg.extra?.content_provider?.length > 0 || msg.extra?.key_word?.length > 0 || msg.extra?.urls?.length > 0"
      >
        <button class="tag-name online-info-btn" @click="showLinks">
          🔍 查看访问的链接
        </button>
      </div>
    </div>

    <!-- Error card -->
    <div class="error-card selectable" v-if="msg.errors && msg.errors?.length > 0">
      <div>
        <svg
          t="1769388840058"
          class="icon"
          viewBox="0 0 1024 1024"
          version="1.1"
          xmlns="http://www.w3.org/2000/svg"
          p-id="5640"
          width="200"
          height="200"
        >
          <path d="M928.894 511.026c0 230.527-187.552 418.077-418.077 418.077s-418.075-187.55-418.075-418.077c0-230.525 187.552-418.077 418.075-418.077s418.077 187.552 418.077 418.077zM850.505 511.026c0-187.298-152.376-339.684-339.687-339.684s-339.686 152.386-339.686 339.684c0 187.3 152.376 339.688 339.687 339.688s339.686-152.389 339.686-339.689zM563.079 354.25l0 156.775c0 28.86-23.399 52.26-52.26 52.26-28.86 0-52.26-23.399-52.26-52.26l0-156.775c0-28.86 23.399-52.26 52.26-52.26 28.86 0 52.26 23.399 52.26 52.26zM563.079 667.804c0 28.863-23.399 52.263-52.26 52.263-28.86 0-52.26-23.399-52.26-52.263 0-28.858 23.399-52.257 52.26-52.257 28.86 0 52.26 23.399 52.26 52.257z" fill="#ffffffc8" p-id="5641"></path>
        </svg>
      </div>
      <div>{{ msg.errors }}</div>
    </div>

    <!-- Right button Menu -->
    <transition name="scale-fade">
      <msgBubbleMenu
        v-if="isShowMenu"
        ref="menuRef"
        type="ai"
        :style="menuStyle"
        @close-menu="closePopMenu"
        @copy-value="copyContextValue"
        @re-edit="reEditContext"
        @re-generate="reGenerateContext"
      />
    </transition>
  </div>
</template>

<script setup lang="ts">
import { nextTick, ref, onMounted, onBeforeUnmount, computed, watch } from 'vue'
import msgBubbleMenu from './comp/msgBubbleMenu.vue'
import ToolLabelCard from './comp/toolLabelCard.vue'
import MarkdownIt from 'markdown-it'
import 'github-markdown-css/github-markdown.css'
import hljs from 'highlight.js'
import 'highlight.js/styles/github.css'
import { ConfirmDialog } from '../comp/confirmDialog.js'
import TodoCard from './comp/todoCard.vue'
import { useAppCacheData } from '../../../store/app'

const store = useAppCacheData()

type ToolLabel = {
  tool_call_id: string
  content: string
  status: 'pending' | 'in_progress' | 'completed' | 'error' | "outdated"
}

type MessageChunk = string | ToolLabel

type InfoTag = {
  id?: string
  model?: string
  model_provider?: string
  total_tokens?: number
  total_duration?: number
}

type TodoItem = {
  content: string
  status: 'pending' | 'in_progress' | 'completed' | 'error'
}

type ImageItem = {
  fileId: string
  src: string
  base64: string
  contentType?: string
  loading: boolean
  error: boolean
}

type MsgBubbleData = {
  id: string
  cid: string
  hid: string
  role: 'ai'
  label: string
  content: string | MessageChunk[]
  think?: string | MessageChunk[]
  todos?: TodoItem[]
  images?: string[]
  info?: InfoTag
  extra?: any
  pending?: boolean
  errors?: string
}

const props = defineProps<{
  msg: MsgBubbleData
}>()

const md = new MarkdownIt({
  html: true,
  linkify: true,
  highlight(code, lang) {
    let highlighted = ''

    try {
      if (lang && hljs.getLanguage(lang)) {
        highlighted = hljs.highlight(code, {
          language: lang,
          ignoreIllegals: true,
        }).value
      } else {
        highlighted = hljs.highlightAuto(code).value
      }
    } catch {
      highlighted = md.utils.escapeHtml(code)
    }

    const raw = md.utils.escapeHtml(code)
    return `<div class="code-block"><button class="code-copy-btn" data-code="${raw}" type="button">${copy_svg.value}</button><pre class="hljs"><code>${highlighted}</code></pre></div>`
  },
})

type RenderItem =
  | { kind: 'text'; key: string; html: string }
  | { kind: 'tool'; key: string; tool: ToolLabel }

function toChunks(input?: string | MessageChunk[]): MessageChunk[] {
  if (!input) return []
  return Array.isArray(input) ? input : [input]
}

function normalizeToString(input?: string | MessageChunk[]) {
  if (!input) return ''
  if (typeof input === 'string') return input

  return input
    .map((chunk) => (typeof chunk === 'string' ? chunk : ''))
    .join('')
}

function buildRenderItems(
  input?: string | MessageChunk[],
  items: RenderItem[] = []
): RenderItem[] {
  const chunks = toChunks(input)

  const prevLen = items.length
  const currLen = chunks.length

  for (let i = prevLen; i < currLen; i++) {
    const chunk = chunks[i]

    if (typeof chunk === 'string') {
      let html = chunk.length ? md.render(chunk) : ''
      html = postProcessHtml(html)

      items[i] = {
        kind: 'text',
        key: `text-${i}`,
        html,
      }
    } else {
      items[i] = {
        kind: 'tool',
        key: `tool-${chunk.tool_call_id || i}`,
        tool: chunk,
      }
    }
  }

  if (currLen === prevLen && currLen > 0) {
    const lastIndex = currLen - 1
    const chunk = chunks[lastIndex]

    if (typeof chunk === 'string') {
      let html = chunk.length ? md.render(chunk) : ''
      html = postProcessHtml(html)

      items[lastIndex] = {
        kind: 'text',
        key: `text-${lastIndex}`,
        html,
      }
    } else {
      items[lastIndex] = {
        kind: 'tool',
        key: `tool-${chunk.tool_call_id || lastIndex}`,
        tool: chunk,
      }
    }
  }

  return items
}

const thinkCache = ref<RenderItem[]>([])
const contentCache = ref<RenderItem[]>([])
const thinkRenderItems = computed(() => {
  thinkCache.value = buildRenderItems(props.msg.think, thinkCache.value)
  return thinkCache.value
})

const contentRenderItems = computed(() => {
  contentCache.value = buildRenderItems(props.msg.content, contentCache.value)
  return contentCache.value
})

const hasThink = computed(() => thinkRenderItems.value.length > 0)
const hasContent = computed(() => contentRenderItems.value.length > 0)

const hasError = computed(() => {
  return !!(props.msg.errors && props.msg.errors.length > 0)
})

const displayTodos = computed(() => {
  if (!props.msg.todos) return []

  if (hasError.value) {
    return props.msg.todos.map((todo) => {
      if (todo.status === 'in_progress') {
        return {
          ...todo,
          status: 'error' as const,
        }
      }
      return todo
    })
  }

  return props.msg.todos
})

const imageItems = ref<ImageItem[]>([])
const imageObjectUrls = new Set<string>()

function base64ToBlob(base64: string, contentType = 'application/octet-stream') {
  const byteCharacters = atob(base64)
  const byteArrays: Uint8Array[] = []

  const sliceSize = 1024
  for (let offset = 0; offset < byteCharacters.length; offset += sliceSize) {
    const slice = byteCharacters.slice(offset, offset + sliceSize)
    const byteNumbers = new Array(slice.length)

    for (let i = 0; i < slice.length; i++) {
      byteNumbers[i] = slice.charCodeAt(i)
    }

    byteArrays.push(new Uint8Array(byteNumbers))
  }

  return new Blob(byteArrays, { type: contentType })
}

function revokeAllImageObjectUrls() {
  for (const url of imageObjectUrls) {
    URL.revokeObjectURL(url)
  }
  imageObjectUrls.clear()
}

async function loadImages() {
  revokeAllImageObjectUrls()

  const fileIds = props.msg.images ?? []
  if (!fileIds.length) {
    imageItems.value = []
    return
  }

  imageItems.value = fileIds.map((fileId) => ({
    fileId,
    src: '',
    loading: true,
    error: false,
  }))

  await Promise.all(
    fileIds.map(async (fileId, index) => {
      try {
        const result = await window.api.loadResource(props.msg.cid, fileId)

        if (!result?.ok) {
          throw new Error(
            typeof result?.detail === 'string'
              ? result.detail
              : JSON.stringify(result?.detail ?? 'load resource failed')
          )
        }

        const blob = base64ToBlob(
          result.buffer,
          result.contentType || 'application/octet-stream'
        )

        const objectUrl = URL.createObjectURL(blob)
        imageObjectUrls.add(objectUrl)

        imageItems.value[index] = {
          fileId,
          src: objectUrl,
          base64: result.buffer,
          contentType: result.contentType,
          loading: false,
          error: false,
        }
      } catch (err) {
        console.error('[loadImages] error:', err)
        imageItems.value[index] = {
          fileId,
          src: '',
          loading: false,
          error: true,
        }
      }
    })
  )
}

async function previewImage(item: ImageItem) {
  if (!item.base64) return

  try {
    const ext = getExtFromType(item.contentType)

    await window.api.openImageTemp(item.base64, `${item.fileId}.${ext}`)
  } catch (err) {
    console.error('previewImage error:', err)
  }
}

function getExtFromType(type?: string) {
  if (!type) return 'png'
  if (type.includes('png')) return 'png'
  if (type.includes('jpeg')) return 'jpg'
  if (type.includes('webp')) return 'webp'
  if (type.includes('gif')) return 'gif'
  return 'png'
}

const isShowMenu = ref(false)
const menuStyle = ref<Record<string, string>>({})
const menuRef = ref<any>(null)

const menuWidthGuess = 144
const menuHeightGuess = 120

const showLinks = async () => {
  const e = props.msg.extra ?? {}
  const sections: string[] = []

  if (e.key_word?.trim()) {
    sections.push(`
      <div class="section">
        <div class="section-title">[关键词]</div>
        <div class="section-body">
          ${e.key_word.split('\n').join(' ')}
        </div>
      </div>
    `)
  }

  if (Array.isArray(e.urls) && e.urls.length > 0) {
    sections.push(`
      <div class="section">
        <div class="section-title">[链接]</div>
        <div class="section-body">
          ${e.urls
            .map(
              (url: string) =>
                `<div><a href="${url}" target="_blank" rel="noopener noreferrer">${url}</a></div>`
            )
            .join('')}
        </div>
      </div>
    `)
  }

  if (e.link_provider?.trim()) {
    sections.push(`
      <div class="section">
        <div class="section-title">[关键词引擎]</div>
        <div class="section-body">
          ${e.link_provider.split('\n').join(' ')}
        </div>
      </div>
    `)
  }

  if (e.content_provider?.trim()) {
    sections.push(`
      <div class="section">
        <div class="section-title">[内容引擎]</div>
        <div class="section-body">
          ${e.content_provider.split('\n').join(' ')}
        </div>
      </div>
    `)
  }

  const message =
    sections.length > 0
      ? sections.join('')
      : '<div class="section-empty">暂无搜索详情</div>'

  await ConfirmDialog.confirm(message, '搜索详情', {
    confirmButtonText: '确定',
    type: 'info',
  })
}

function onContextMenu(e: MouseEvent) {
  showPopMenu(e.clientX, e.clientY)
}

function showPopMenu(position_x: number, position_y: number) {
  isShowMenu.value = true

  menuStyle.value = {
    position: 'fixed',
    top: `${position_y}px`,
    left: `${position_x}px`,
  }

  nextTick(() => {
    const menuEl = menuRef.value?.$el || menuRef.value
    const viewportWidth = window.innerWidth
    const viewportHeight = window.innerHeight

    const realW = menuEl?.offsetWidth ?? menuWidthGuess
    const realH = menuEl?.offsetHeight ?? menuHeightGuess

    let left = position_x
    let top = position_y

    if (left + realW > viewportWidth) left = position_x - realW
    if (top + realH > viewportHeight) top = position_y - realH

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

function copyContextValue() {
  const text = normalizeToString(props.msg.content)
  window.api?.copyToClipboard({ type: 'text', data: text })
}

function reEditContext() {
  console.log('Note: reEditContext: msg.id = ' + props.msg.id)
}

function reGenerateContext() {
  console.log('Note: reGenerateContext: msg.id = ' + props.msg.id)
}

function onDocumentClick(e: MouseEvent) {
  const menuEl = menuRef.value?.$el || menuRef.value
  if (!menuEl) return
  if (e.target === menuEl || menuEl.contains(e.target as Node)) return
  closePopMenu()
}

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

const isThinkVisiable = ref(false)
const triggerThinkVisiable = () => {
  isThinkVisiable.value = !isThinkVisiable.value
}

const isTodosVisiable = ref(true)
const triggerTodosVisiable = () => {
  isTodosVisiable.value = !isTodosVisiable.value
}

function onResize() {
  closePopMenu()
}

const abortLabel = '<div style="-webkit-user-select: none !important; -webkit-app-region: no-drag !important; user-select: none !important; color: #dc3545; border: 1px solid #dc3545; padding: 3px 6px; border-radius: 8px; width: fit-content; font-size: 12px;">流式传输终止</div>'

function postProcessHtml(html: string): string {
  if (!html) return html

  if (html.includes('[Conversation Abort]')) {
    html = html.replace('[Conversation Abort]', abortLabel)
  }

  return html
}

watch(
  () => [props.msg.cid, props.msg.images],
  async () => {
    await loadImages()
  },
  {
    immediate: true,
    deep: true,
  }
)

onMounted(() => {
  document.addEventListener('click', onDocumentClick)
  document.addEventListener('click', onCodeCopyClick)
  window.addEventListener('resize', onResize)

  console.log(props.msg)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', onDocumentClick)
  document.removeEventListener('click', onCodeCopyClick)
  window.removeEventListener('resize', onResize)
  revokeAllImageObjectUrls()
})
</script>

<style scoped>
.ai-bubble-wrapper {
  position: relative;
  display: flex;
  flex-direction: column;
  width: 100%;
  max-width: 100%;
  padding: 0px 16px;
  transition: height 0.25s ease;
} 

.think {
  background-color: transparent !important;
  font-size: 14px;
  width: calc(100% - 32px);
  padding: 6px 16px 6px 16px;
  color: #000000a2;
}

.content {
  padding: 6px 0px 6px 0px;
  color: #000000a2;
}

.markdown-body:deep(table) {
  border-radius: 12px !important;
  background-color: rgba(255, 255, 255, 0.431) !important;
  box-shadow: 
    inset 0 1px 0 1px var(--borderColor-default),  /* 顶部边框 */
    inset 1px 0 0 1px var(--borderColor-default), /* 右侧边框 */
    inset 0 -1px 0 1px var(--borderColor-default), /* 底部边框 */
    inset -1px 0 0 1px var(--borderColor-default); /* 左侧边框 */
}
.markdown-body:deep(thead) {
  background-color: rgba(178, 194, 199, 0.256) !important;
}
.markdown-body:deep(th) {
  background-color: rgba(255, 255, 255, 0) !important;
}
.markdown-body:deep(tbody) {
  background-color: rgba(255, 255, 255, 0) !important;
}
.markdown-body:deep(tr) {
  background-color: rgba(255, 255, 255, 0) !important;
}
.markdown-body:deep(td) {
  background-color: rgba(234, 234, 234, 0) !important;
}

.markdown-body:deep(pre) {
  padding: 0px;
  margin-bottom: 0px;
  margin-top: 14px;
  margin-bottom: 14px;
  scrollbar-width: none;
  border-radius: 24px !important;
}

.think-block {
  position: relative;
  overflow: hidden;
  align-self: center;
  align-items: center;

  display: grid;
  grid-template-columns: 6px auto;

  width: calc(100% - 16px);
  min-height: 24px;
  padding: 8px 32px 0px 4px;

  transition: all 0.25s ease;
}

.think-border-point {
  width: 24px;
  height: 24px;
  border-radius: 50%;
}

.think-border-point:deep(.icon) {
  width: 24px;
  height: 24px;
}

/* 默认状态：线缩放为0 */
.think-border-line:not(.thinkVisiable) {
  transform: scaleY(0);
}

/* 可见状态：线正常显示 */
.think-border-line.thinkVisiable{
  transform: scaleY(1);
}

.think-render-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 500px;
  overflow: scroll;
}

.expend-think-btn {
  height: 28px !important;
  width: fit-content;
  padding: 2px 14px 2px 8px;
  margin-left: 24px;
  display: flex;
  flex-direction: row;
  gap: 6px;
  font-size: 14px;
  align-items: center;
  background-color: transparent;
  border: none;
  border-radius: 12px;
  color: #515151a2;
}

.expend-think-btn.breath {
  animation: breath 1.5s infinite ease-in-out;
}

.expend-think-btn:hover {
  background-color: #c8c8c868;
  border: none;
  color: #242424;
}

.expend-think-btn:deep(.icon) {
  height: 20px;
  width: fit-content;
  background-color: transparent;
  border: none;
  fill: #515151a2;
}

.expend-think-btn:hover:deep(.icon) {
  height: 20px;
  width: fit-content;
  background-color: transparent;
  border: none;
  fill: #515151;
}

.expend-think-btn:deep(.icon-thinking) {
  height: 20px;
  width: fit-content;
  background-color: transparent;
  border: none;
  fill: #1a5fffb1;
}

.expend-think-btn:hover:deep(.icon-thinking) {
  height: 20px;
  width: fit-content;
  background-color: transparent;
  border: none;
  fill: #1A5EFF;
}

@keyframes breath {
  0%, 100% {
    opacity: 0.5;
  }
  50% {
    opacity: 1;
  }
}

.expend-think-btn {
  height: 16px;
  background-color: transparent;
  border: none;
}

.expend-todos-btn-wrapper {
  padding: 12px 4px 0px 3px;
}

.expend-todos-btn {
  border-radius: 8px;
  border: 1px solid #325eff76;
  color: #2545b7bd;
  background: #ffffffc8;
  height: 28px;
  padding-left: 14px;
  display: flex;
  flex-direction: row;
  gap: 8px;
  transition: all 0.20s ease;
}

.expend-todos-btn:deep(.icon) {
  padding-top: 1px;
  width: 18px;
  height: 18px;
}

.expend-todos-btn:hover {
  transform: scale(1.03);
}

.expend-todos-btn:active {
  transform: scale(1.01);
}

.todos-block {
  padding: 10px 0px 6px 0px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.ai-bubble {
  position: relative;
  overflow: hidden;
  align-self: center;
  display: flex;
  flex-direction: column;

  width: 100%;
  padding: 8px 16px;
  gap: 6px;
  border-radius: 12px;
  line-height: 1.6;
  color: rgba(0, 0, 0, 0.657);

  /* background: linear-gradient(90deg, rgba(92, 155, 144, 0.026) 60%, transparent); */
  /* background: rgba(248, 250, 250, 0.053); */
  /* backdrop-filter: blur(16px); */

  transition: all 0.25s ease;
}

/* pending 状态下（占位骨架） */
.ai-bubble:has(.shine) {
  padding: 10px 14px;
  opacity: 0.8;
  max-height: 48px;
}

/* ------------------------
   Shine 动画（修复位置和大小）
------------------------- */
.shine {
  position: absolute;
  top: 0;
  left: -100%;
  width: 80%;
  height: 100%;
  background: linear-gradient(
    120deg,
    transparent,
    rgba(200, 200, 200, 0.22),
    transparent
  );
  animation: shining 1.3s infinite;
}
@keyframes shining {
  0% { left: -100%; }
  100% { left: 120%; }
}

/* ------------------------
   Todo动画
------------------------- */
.fade-enter-active {
  animation: fadeIn .25s linear;
}
.fade-leave-active {
  animation: fadeOut .2s linear;
}
@keyframes fadeIn {
  0% { opacity: 0;}
  100% { opacity: 1;}
}
@keyframes fadeOut {
  0% { opacity: 1;}
  100% { opacity: 0;}
}

/* ------------------------
   菜单动画
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
   思考动画
------------------------- */
.scale-fade-height-enter-active,
.scale-fade-height-leave-active {
  transition: 
    opacity 0.25s ease,
    transform 0.25s ease;
  transform-origin: top center;
  overflow: hidden;
}

.scale-fade-height-enter-from {
  opacity: 0;
}

.scale-fade-height-enter-to {
  opacity: 1;
}

.scale-fade-height-leave-from {
  opacity: 1;
}

.scale-fade-height-leave-to {
  opacity: 0;
}

:deep(.code-block) {
  position: relative !important;
  height: fit-content !important;;
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
  color: #0000009b;
  border: none;
  cursor: pointer;

  opacity: 0;
  transition: 
    width 0.15s cubic-bezier(0.34, 2.5, 0.64, 1),
    background-color 0.05s ease,
    opacity 0.15s ease;
  z-index: 999;
}

:deep(.code-copy-btn .icon) {
  width: 24px;
  height: 24px;
  fill: #515151bc;
}

:deep(.code-block:hover .code-copy-btn) {
  opacity: 1;
}

:deep(.hljs) {
  padding: 16px !important;
  margin: 0px !important;
  border-radius: 24px !important;
  background-color: #f9f9f9 !important;
  border: 1px solid #0d0d0d0d;
}

.info-tag {
  display: flex;
  flex-direction: row;
  font-size: 12px;
  gap: 16px;
  padding: 8px 4px;
  color: #5050504b;
  transition: color 0.15s ease;
  width: inherit;
  height: 20px;
  overflow: scroll;
  scrollbar-width:none
}

.info-tag:hover {
  color: #505050d6;
}

.info-tag.show {
  opacity: 1;
}

.info-tag:not(.show) {
  opacity: 0;
}

.tag-wrapper {
  display: flex;
  flex-direction: row;
  gap: 4px;
  white-space: nowrap;
}

.tag-name {
  padding: 0px 4px;
  border-radius: 4px;
  border: none;
  background-color: #5050500a;
  transition: background 0.15s ease;
}

.online-info-btn {
  color: inherit;
  font-size: 12px;
  -webkit-transition: all 0.3s cubic-bezier(0.215, 0.61, 0.355, 1);
  transition: all 0.3s cubic-bezier(0.215, 0.61, 0.355, 1);
}

.online-info-btn:active {
  transform: scale(0.95);
}

.info-tag:hover:deep(.tag-name) {
  background-color: #50505012;
}

.error-card {
  align-self: center;
  align-items: center;
  display: flex;
  width: 100%;
  padding: 6px 12px;
  gap: 6px;
  border-radius: 12px;
  font-size: 14px;
  background-color: #ff101080;
  border: 1px solid #be131384;
  color: #000000a2;
  color: rgba(255, 255, 255, 0.792);
}

.error-card:deep(svg) {
  height: 20px;
  width: 20px;
  padding-bottom: 2px;
}

.error-card:deep(div) {
  align-items: center;
  display: flex;
}

.ai-images-wrapper {
  position: relative;
  overflow: visible;   /* 允许 hover 层溢出 */
  height: 150px;
}

/* 专门负责横向滚动 */
.ai-images-scroller {
  height: 150px;
  padding-bottom: 8px;
  scrollbar-width: thin;
  scrollbar-color: rgba(255, 255, 255, 0.2) transparent;
}

.ai-images-scroller::-webkit-scrollbar {
  height: 6px;
}

.ai-images-scroller::-webkit-scrollbar-track {
  background: transparent;
}

.ai-images-scroller::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.2);
  border-radius: 3px;
}

.ai-images {
  display: flex;
  flex-direction: row;
  gap: 10px;
  margin-top: 10px;
  width: max-content;
}

.ai-image-card {
  position: relative;
  flex-shrink: 0;
  width: 200px;
  height: 150px;
  border-radius: 12px;
  overflow: visible; /* 这里不要再 hidden 了 */
  background: rgba(255, 255, 255, 0.04);
  display: flex;
  align-items: center;
  justify-content: center;
}

/* 缩略图本身 */
.ai-image {
  display: block;
  width: 200px;
  height: 150px;
  object-fit: cover;
  border-radius: 12px;
  cursor: pointer;
  transition: transform 0.25s ease;
  position: relative;
  z-index: 1;
}

/* hover 预览层：默认隐藏 */
.ai-image-hover-preview {
  position: absolute;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%) scale(0.96);
  opacity: 0;
  pointer-events: none;
  z-index: 20;

  padding: 8px;
  border-radius: 14px;
  background: color-mix(in oklch, rgba(26, 205, 181) 80%, transparent);
  backdrop-filter: saturate(300%) blur(3px);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.18);
  transition: opacity 0.25s ease, transform 0.25s ease;
}

/* 放大预览图 */
.ai-image-preview {
  display: block;
  width: auto;
  height: auto;
  max-width: 360px;
  max-height: 400px;
  object-fit: contain;
  border-radius: 10px;
}

/* hover 时显示浮层 */
.ai-image-card:hover {
  z-index: 30;
}

.ai-image-card:hover .ai-image-hover-preview {
  opacity: 1;
  transform: translate(-50%, -50%) scale(1);
}

.ai-image-card:hover .ai-image {
  transform: scale(1.02);
}

.ai-image-loading,
.ai-image-error {
  width: 200px;
  height: 150px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.72);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.04);
}
</style>
