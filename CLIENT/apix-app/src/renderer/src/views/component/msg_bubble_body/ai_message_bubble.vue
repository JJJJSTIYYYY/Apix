<template>
  <div
    class="message-wrapper"
    :class="{ selected: is_selecting && props.msg.selected }"
    @click="toggleSelectFullArea"
  >
    <div
      v-if="is_selecting && props.msg.pending === false"
      class="message-select-box"
      :class="{ checked: props.msg.selected }"
      @click.stop="toggleSelect"
    ></div>

    <div
      class="ai-bubble-wrapper"
      :class="{ is_selecting: is_selecting }"
      @contextmenu.prevent="onContextMenu"
    >
      <!-- Branch switch -->
      <div
        v-if="(props.msg.pre_node && props.msg.pre_node.length > 0) || (props.msg.next_node && props.msg.next_node.length > 0)"
        class="branch-switch-wrapper"
      >
        <div style="height: 2px; width: 100%; background: linear-gradient(to right, transparent, var(--apix-default-light-color));"></div>
        <div class="branch-switch-label-wrapper">
          <button
            class="branch-switch-btn pre"
            :disabled="!props.msg.pre_node || props.msg.pre_node.length === 0"
            @click="handlePreNodeClick"
          >
            <svg t="1777025380440" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="1147" width="16" height="16">
              <path d="M412.128 512l293.28-285.248c9.312-9.056 14.592-21.6 14.592-34.752 0-26.496-21.056-48-47.008-48-12.064 0-23.68 4.736-32.416 13.248l-317.12 308.416Q304 484.544 304 512q0 27.424 19.456 46.336l317.12 308.384c8.736 8.544 20.352 13.28 32.416 13.28 25.952 0 47.008-21.504 47.008-48 0-13.12-5.28-25.696-14.592-34.752L412.16 512z" fill="#7C8394" p-id="1148"></path>
            </svg>
          </button>

          <div class="branch-page-label">
            {{ (props.msg.pre_node?.length ?? 0) + 1 }}{{ ' / ' }}{{ (props.msg.pre_node?.length ?? 0) + (props.msg.next_node?.length ?? 0) + 1 }}
          </div>

          <button
            class="branch-switch-btn next"
            :disabled="!props.msg.next_node || props.msg.next_node.length === 0"
            @click="handleNextNodeClick"
          >
            <svg t="1777025401907" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="1364" width="16" height="16">
              <path d="M611.872 512L318.592 226.752A48.48 48.48 0 0 1 304 192c0-26.496 21.056-48 47.008-48 12.064 0 23.68 4.736 32.416 13.248l317.12 308.416q19.456 18.88 19.456 46.336 0 27.424-19.456 46.336l-317.12 308.384a46.528 46.528 0 0 1-32.416 13.28c-25.952 0-47.008-21.504-47.008-48 0-13.12 5.28-25.696 14.592-34.752L611.84 512z" fill="#7C8394" p-id="1365"></path>
            </svg>
          </button>
        </div>
        <div style="height: 2px; width: 100%; background: linear-gradient(to left, transparent, var(--apix-default-light-color));"></div>
      </div>

      <!-- Unified chunks -->
      <div
        class="ai-bubble"
        @mousedown="handleMouseDown"
        @mouseup="handleMouseUp"
      >

        <!-- Chunks -->
        <template
          v-for="(item, index) in renderItems"
          :key="item.key"
        >
          <!-- Think -->
          <template
            v-if="item.kind === 'message' && item.label_type === 'think'"
          >
            <div class="think-toggle-row">
              <button
                class="expend-think-btn"
                :class="{expended_think_btn: isThinkExpanded(item.key)}"
                @click="toggleThinkItem(item.key)"
              >
                <svg t="1768788522926" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="9133" width="200" height="200"><path d="M882.176 882.176c-53.8368 53.8368-136.832 59.3408-249.0368 16.4864A705.1008 705.1008 0 0 1 512 837.9136a705.1008 705.1008 0 0 1-121.1392 60.7744c-112.1792 42.8288-195.2 37.3248-249.0112-16.512-53.8368-53.8112-59.3408-136.832-16.512-249.0112A705.1008 705.1008 0 0 1 186.112 512a705.1264 705.1264 0 0 1-60.7744-121.1904c-42.8288-112.1792-37.3248-195.2 16.4864-249.0368 53.8368-53.8112 136.8576-59.3152 249.0368-16.4864A705.1264 705.1264 0 0 1 512 186.112a705.1264 705.1264 0 0 1 121.1648-60.7488c112.1792-42.8544 195.1744-37.3504 249.0112 16.4864 53.8368 53.8368 59.3408 136.832 16.4864 249.0112a705.152 705.152 0 0 1-60.7744 121.1904 705.1264 705.1264 0 0 1 60.7488 121.1392c42.8288 112.1792 37.3504 195.1744-16.4864 249.0112zM194.304 194.304c-31.1552 31.1552-31.0272 87.8336 0.3584 170.0608 10.2656 26.88 22.8864 53.6832 37.888 80.4608a1115.8784 1115.8784 0 0 1 99.3536-112.9472 1115.904 1115.904 0 0 1 112.896-99.328 609.1776 609.1776 0 0 0-80.4608-37.888c-82.2016-31.3856-138.88-31.488-170.0352-0.3584z m635.392 0c-31.1296-31.1296-87.808-31.0272-170.0352 0.384-26.88 10.24-53.6832 22.8864-80.4608 37.888a1115.904 1115.904 0 0 1 112.896 99.328 1115.8784 1115.8784 0 0 1 99.3536 112.896 609.1776 609.1776 0 0 0 37.888-80.4352c31.3856-82.2272 31.5136-138.9056 0.384-170.0608z m-445.2864 190.08c-42.4448 42.4448-78.8224 84.992-109.1328 127.6416 30.3104 42.6496 66.688 85.1712 109.1072 127.5904 42.4192 42.4448 84.992 78.8224 127.616 109.1328 42.6752-30.3104 85.1968-66.688 127.6416-109.1328 42.4192-42.4192 78.7968-84.9408 109.1072-127.5904-30.336-42.6752-66.7136-85.2224-109.1328-127.6416-42.4192-42.4192-84.9664-78.7968-127.616-109.1072-42.624 30.3104-85.1712 66.688-127.5904 109.1072zM435.2 512a76.8 76.8 0 1 1 153.6 0 76.8 76.8 0 0 1-153.6 0z m-202.624 67.2256a609.1776 609.1776 0 0 0-37.888 80.4096c-31.3856 82.2272-31.488 138.9056-0.3584 170.0608 31.1552 31.1552 87.8336 31.0272 170.0608-0.3584 26.8544-10.2656 53.6576-22.8864 80.4096-37.888a1115.8784 1115.8784 0 0 1-112.9216-99.328 1115.9552 1115.9552 0 0 1-99.328-112.896z m597.0944 250.4704c31.1552-31.1552 31.0272-87.8336-0.3584-170.0608a609.1776 609.1776 0 0 0-37.888-80.4096 1115.9296 1115.9296 0 0 1-99.2768 112.896 1115.8784 1115.8784 0 0 1-112.9216 99.328 609.1264 609.1264 0 0 0 80.384 37.888c82.2528 31.36 138.9312 31.488 170.0608 0.3584z" p-id="9134"></path></svg>

                <div class="btn-text" :class="{breath: index >= renderItems.length -1 && props.msg.pending}">
                  {{ index >= renderItems.length -1 ? (props.msg.pending ? msg.label || '正在思考' : '思考中断') : '已思考' }}
                </div>

                <svg t="1777025401907" class="icon expend-icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="1364" width="16" height="16">
                  <path d="M611.872 512L318.592 226.752A48.48 48.48 0 0 1 304 192c0-26.496 21.056-48 47.008-48 12.064 0 23.68 4.736 32.416 13.248l317.12 308.416q19.456 18.88 19.456 46.336 0 27.424-19.456 46.336l-317.12 308.384a46.528 46.528 0 0 1-32.416 13.28c-25.952 0-47.008-21.504-47.008-48 0-13.12 5.28-25.696 14.592-34.752L611.84 512z" p-id="1365"></path>
                </svg>
              </button>
            </div>

            <div
              v-show="isThinkExpanded(item.key)"
              v-html="item.html"
              class="markdown-body think selectable"
            ></div>
          </template>

          <!-- Tool -->
          <ToolLabelCard
            v-else-if="item.kind === 'tool' && store.config.showToolLabels"
            :tool_name="item.tool.tool_name"
            :tool_call_id="item.tool.tool_call_id"
            :content="item.tool.content"
            :status="item.tool.status"
            :obj="item.tool"
          />

          <!-- Content -->
          <div
            v-else
            v-html="item.html"
            class="markdown-body content selectable"
            style="background: transparent;"
          ></div>
        </template>
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
            <path d="M0.831169 345.766234c0 109.252156 88.566026 197.818182 197.818182 197.818182 109.252156 0 197.818182-88.566026 197.818181-197.818182 0-109.252156-88.566026-197.818182-197.818181-197.818182C89.397195 147.948052 0.831169 236.514078 0.831169 345.766234z" fill="var(--apix-success-color)" p-id="5086" data-spm-anchor-id="a313x.search_index.0.i4.78ef3a811GNESF" class="selected"></path>
            <path d="M273.255065 960.831169H1023.168831v-99.351273H273.255065V960.831169z m0-317.476572H1023.168831v-99.351272H273.255065v99.351272zM2.493506 332.284675l72.76052-66.912415 103.726545 114.948987L455.749818 64.831169l73.844364 65.821922-349.529766 398.296104L2.493506 332.284675z m626.835949-6.458181H1023.168831V226.476883H629.329455v99.349611z" fill="var(--apix-info-color)" p-id="5087" data-spm-anchor-id="a313x.search_index.0.i3.78ef3a811GNESF" class=""></path>
          </svg>
          <div style="display: flex; align-items: center;">已生成执行计划（{{ msg.todos.length }}）</div>
        </button>
      </div>

      <transition name="opacity-fade">
        <div
          v-if="msg.todos && msg.todos.length > 0 && isTodosVisiable"
          class="todos-block"
        >
          <div
            v-for="item in (props.msg.todos ?? [])"
            :key="`${item.content}-${item.status}`"
            class="todo-card"
          >
            <TodoCard
              :content="item.content"
              :status="item.status"
              :pending="msg.pending"
            />
          </div>
        </div>
      </transition>

      <transition name="opacity-fade">
        <div
          v-if="msg.questions?.questions && msg.questions?.questions.length > 0"
          class="questions-block"
        >
          <QuestionView
            :questions="msg.questions?.questions"
            :qid="msg.questions?.qid"
            @complete="handleCompleteQuestions"
          />
        </div>
      </transition>

      <!-- Images -->
      <div
        v-if="imageItems.length > 0"
        class="ai-images-wrapper"
      >
        <div class="ai-images-scroller">
          <div class="ai-images">
            <div
              v-for="item in imageItems"
              :key="item.fileId"
              class="ai-image-card"
            >
              <div
                v-if="item.loading"
                class="ai-image-loading"
              >
                Loading...
              </div>

              <div
                v-else-if="item.error"
                class="ai-image-error"
              >
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
      <div
        class="info-tag"
        :class="{ show: !msg.pending }"
      >
        <div class="tag-wrapper">
          <div class="tag-name">供应商:</div>
          <div>{{ msg.info?.model_provider }}</div>
        </div>
        <div class="tag-wrapper">
          <div class="tag-name">已使用模型:</div>
          <div>{{ msg.info?.model }}</div>
        </div>
        <div class="tag-wrapper" title="Token统计仅供参考，实际用量请以控制台为准！">
          <div class="tag-name">令牌数:</div>
          <div>{{ msg.info?.total_tokens ?? 'N/A' }}</div>
        </div>
        <div class="tag-wrapper">
          <div class="tag-name">耗时:</div>
          <div>{{ (msg.info?.total_duration / 1000) ?? 'N/A' }}S</div>
        </div>
        <div
          v-if="msg.extra?.link_provider?.length > 0 || msg.extra?.content_provider?.length > 0 || msg.extra?.key_word?.length > 0 || msg.extra?.urls?.length > 0"
          class="tag-wrapper"
        >
          <div
            class="tag-name online-info-btn"
            @click="showLinks"
          >
            <el-icon><Search /></el-icon>已访问互联网
          </div>
        </div>
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
          @re-generate="reGenerateContext"
          @select-text="selectText"
          @delete-item="deleteItem"
          @click.stop
        />
      </transition>

      <msgSelectionBubble
        v-if="isShowSelectionBubble && globalSelection.role === 'ai'"
        :style="{
          left: bubblePosition.x + 'px',
          top: bubblePosition.y + 'px'
        }"
        @close-bubble="closeSelectionBubble"
        @copy-value=""
        @quote-content="handleQuoteContent"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { nextTick, ref, shallowRef, onMounted, onBeforeUnmount, computed, watch } from 'vue'
import msgBubbleMenu from './comp/msgBubbleMenu.vue'
import msgSelectionBubble from './comp/msgSelectionBubble.vue'
import ToolLabelCard from './comp/toolLabelCard.vue'
import QuestionView from './comp/questionView.vue'
import MarkdownIt from 'markdown-it'
import 'github-markdown-css/github-markdown.css'
import hljs from 'highlight.js'
import { ConfirmDialog } from '../comp/confirmDialog.js'
import TodoCard from './comp/todoCard.vue'
import { useAppCacheData } from '../../../store/app'
import { globalSelection } from '../../../store/globalData.js'

const emit = defineEmits<{
  reGenerate: [id: string]
  selectText: [id: string, role: string]
  selected: [id: string]
  delete: [id: string]
  quoted: [hid: string, mid: string, role: string, content: string]
  completeQuestions: [id: string, qid: string, resp: QuestionItem[]]
  switchToBranch: [id: string]
}>()

const store = useAppCacheData()

interface ToolLabel {
  tool_call_id: string
  tool_name: string
  content: object
  status: 'pending' | 'in_progress' | 'completed' | 'error' | 'outdated'
}

interface MessageLabel {
  content: string
  label_type: 'think' | 'content'
}

type MessageChunk = MessageLabel | ToolLabel

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

type QuestionItem = {
  question: string
  options?: string[]
  response?: string[]
  multiselection?: boolean
}

type QuestionsView = {
  questions: QuestionItem[]
  qid: string
}

type ImageItem = {
  fileId: string
  src?: string
  base64?: string
  contentType?: string
  loading: boolean
  error: boolean
}

type MsgBubbleData = {
  id: string
  cid: string
  hid: string
  node_id?: number
  parent_id?: number
  pre_node?: string[]
  next_node?: string[]
  role: 'ai'
  label: string
  chunks: MessageChunk[]
  todos?: TodoItem[]
  questions?: QuestionsView
  images?: string[]
  info?: InfoTag
  extra?: any
  pending?: boolean
  selected?: boolean
}

type RenderItem =
  | {
      kind: 'message'
      key: string
      html: string
      label_type: 'think' | 'content'
    }
  | {
      kind: 'tool'
      key: string
      tool: ToolLabel
    }

const props = defineProps<{
  msg: MsgBubbleData
  is_selecting?: boolean
}>()

function isToolLabel(chunk: MessageChunk): chunk is ToolLabel {
  return 'tool_call_id' in chunk
}

function isMessageLabel(chunk: MessageChunk): chunk is MessageLabel {
  return 'label_type' in chunk
}

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

const expandedThinkMap = ref<Record<string, boolean>>({})

function toggleThinkItem(key: string) {
  expandedThinkMap.value[key] =
    !expandedThinkMap.value[key]
}

function isThinkExpanded(key: string) {
  return Boolean(expandedThinkMap.value[key])
}

const renderedChunkMap = shallowRef<Record<string, string>>({})

function buildRenderItems(chunks: MessageChunk[] = []): RenderItem[] {
  // Step 1: filter tool chunks
  const filteredChunks = chunks.filter((chunk) => {
    if (!isMessageLabel(chunk)) {
      return store.config.showToolLabels
    }

    return true
  })

  // Step 2: merge continuous think
  const mergedChunks: MessageChunk[] = []

  for (const chunk of filteredChunks) {
    if (
      isMessageLabel(chunk)
      &&
      chunk.label_type === 'think'
    ) {
      const last = mergedChunks.at(-1)

      if (
        last
        &&
        isMessageLabel(last)
        &&
        last.label_type === 'think'
      ) {
        last.content += chunk.content
      }
      else {
        mergedChunks.push({
          ...chunk,
        })
      }

      continue
    }

    mergedChunks.push(chunk)
  }

  // Step 3: render strategy
  const lastChunk = mergedChunks.at(-1)

  if (lastChunk && isMessageLabel(lastChunk)) {
    const lastKey = `msg-${mergedChunks.length - 1}`

    let html = lastChunk.content.length
      ? md.render(lastChunk.content)
      : ''

    html = postProcessHtml(html)

    renderedChunkMap.value[lastKey] = html
  }

  // Step 4: build items
  return mergedChunks.map((chunk, index) => {
    if (isMessageLabel(chunk)) {
      const key = `msg-${index}`

      // Reuse cached html
      let html = renderedChunkMap.value[key]

      // First render fallback
      if (html == null) {
        html = chunk.content.length
          ? md.render(chunk.content)
          : ''

        html = postProcessHtml(html)

        renderedChunkMap.value[key] = html
      }

      return {
        kind: 'message',
        key,
        html,
        label_type: chunk.label_type,
      }
    }

    return {
      kind: 'tool',
      key: `tool-${chunk.tool_call_id || index}`,
      tool: chunk,
    }
  })
}

const renderItems = computed(() => {
  return buildRenderItems(props.msg.chunks ?? [])
})

function toggleSelectFullArea() {
  if (props.is_selecting && props.msg.pending === false) {
    toggleSelect()
  }
}

function toggleSelect() {
  props.msg.selected = !props.msg.selected
  if (props.msg.selected) emit('selected', props.msg.id)
}

function normalizeToString(input?: MessageChunk[]) {
  if (!Array.isArray(input) || input.length === 0) return ''
  return input
    .filter(isMessageLabel)
    .map(chunk => chunk.content)
    .join('\n\n')
}

function handleMouseDown() {
  globalSelection.id = ''
  globalSelection.content = ''
  globalSelection.role = ''
  globalSelection.rect = null
}

function handleMouseUp(e: MouseEvent) {
  const selection = window.getSelection()

  if (!selection || selection.isCollapsed) {
    globalSelection.content = ''
    globalSelection.id = ''
    globalSelection.role = ''
    return
  }

  const text = selection.toString().trim()
  if (!text) {
    globalSelection.content = ''
    globalSelection.id = ''
    globalSelection.role = ''
    return
  }

  const range = selection.getRangeAt(0)
  const container = range.commonAncestorContainer
  const wrapper = e.currentTarget as HTMLElement

  if (!wrapper.contains(container) || props.msg.pending) {
    globalSelection.content = ''
    globalSelection.id = ''
    globalSelection.role = ''
    return
  }

  const rect = range.getBoundingClientRect()

  globalSelection.content = text
  globalSelection.id = props.msg.id
  globalSelection.role = 'ai'
  globalSelection.rect = rect
}

const isShowSelectionBubble = computed(() => {
  return Boolean(globalSelection.content) && globalSelection.id === props.msg.id
})

const bubblePosition = computed(() => {
  const rect = globalSelection.rect
  if (!rect) return { x: 0, y: 0 }

  return {
    x: rect.left + rect.width / 2,
    y: rect.top - 16,
  }
})

function handleSelectionChange() {
  const selection = window.getSelection()

  if (!selection || selection.isCollapsed) {
    globalSelection.content = ''
    globalSelection.id = ''
    globalSelection.role = ''
    globalSelection.rect = null
  }
}

function closeSelectionBubble() {
  window.getSelection()?.removeAllRanges()
}

function handleQuoteContent() {
  emit('quoted', props.msg.hid, props.msg.id, 'ai', globalSelection.content)
}



const handleCompleteQuestions = (qid: string, resp: QuestionItem[]) => {
  emit('completeQuestions', props.msg.id, qid, resp)
}



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

  imageItems.value = fileIds.map(fileId => ({
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

  console.log(props.msg.extra)

  if (Array.isArray(e.key_word) && e.key_word.length > 0) {
    sections.push(`
      <div class="section">
        <div class="section-title">已通过 ${e.link_provider} 搜索关键词</div>
        <div class="section-body">
          ${e.key_word
            .map(
              (kw: string) =>
                `<div style="display: flex; flex-direction: row; align-items: center; gap: 6px;">• ${kw}</div>`
            )
            .join('')}
        </div>
      </div>
    `)
  }

  if (Array.isArray(e.urls) && e.urls.length > 0) {
    sections.push(`
      <div class="section">
        <div class="section-title">已通过 ${e.content_provider} 浏览 ${e.urls.length} 个页面</div>
        <div class="section-body">
          ${e.urls
            .map(
              (url: string) =>
                `<div style="display: flex; flex-direction: row; align-items: center; gap: 6px;"><a href="${url}" target="_blank" rel="noopener noreferrer">• ${url}</a></div>`
            )
            .join('')}
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

function handlePreNodeClick() {
  emit('switchToBranch', props.msg.pre_node?.at(-1) ?? '')
}

function handleNextNodeClick() {
  emit('switchToBranch', props.msg.next_node?.at(0) ?? '')
}

function onContextMenu(e: MouseEvent) {
  showPopMenu(e.clientX, e.clientY)
}

function showPopMenu(position_x: number, position_y: number) {
  if (props.is_selecting) return
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
  const text = normalizeToString(props.msg.chunks)
  window.api?.copyToClipboard({ type: 'text', data: text })
}

function reGenerateContext() {
  emit('reGenerate', String(props.msg.parent_id ?? ''))
}

function selectText() {
  emit('selectText', props.msg.id, 'ai')
}

function deleteItem() {
  emit('delete', props.msg.id)
}

const copy_svg = ref(
  `<svg t="1776756262130" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="10157" width="20" height="20"><path d="M585.142857 365.714286a73.142857 73.142857 0 0 1 73.142857 73.142857v390.095238a73.142857 73.142857 0 0 1-73.142857 73.142857H195.047619a73.142857 73.142857 0 0 1-73.142857-73.142857V438.857143a73.142857 73.142857 0 0 1 73.142857-73.142857h390.095238z m0 73.142857H195.047619v390.095238h390.095238V438.857143z m-73.142857 219.428571v73.142857H268.190476v-73.142857h243.809524zM828.952381 121.904762a73.142857 73.142857 0 0 1 73.142857 73.142857v390.095238a73.142857 73.142857 0 0 1-73.142857 73.142857h-121.904762v-73.142857h121.904762V195.047619H438.857143v121.904762h-73.142857V195.047619a73.142857 73.142857 0 0 1 73.142857-73.142857h390.095238zM512 536.380952v73.142858H268.190476v-73.142858h243.809524z" p-id="10158" fill="var(--apix-default-dark-color)"></path></svg>`
)

function onCodeCopyClick(e: Event) {
  const target = e.target as HTMLElement
  const btn = target.closest('.code-copy-btn')
  if (!btn) return

  const code = btn.getAttribute('data-code')
  if (!code) return

  navigator.clipboard.writeText(code)
  copy_svg.value =
    `<svg t="1772103245365" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="12505" width="200" height="200"><path d="M911.075556 192.796444a45.511111 45.511111 0 0 1 5.518222 64.113778l-455.111111 540.444445a45.511111 45.511111 0 0 1-68.835556 0.910222l-227.555555-256a45.511111 45.511111 0 0 1 68.039111-60.472889l192.625777 216.689778 421.205334-500.224a45.511111 45.511111 0 0 1 64.113778-5.461334z" p-id="12506" fill="var(--apix-default-dark-color)"></path></svg>`

  setTimeout(() => {
    copy_svg.value =
      `<svg t="1776756262130" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="10157" width="20" height="20"><path d="M585.142857 365.714286a73.142857 73.142857 0 0 1 73.142857 73.142857v390.095238a73.142857 73.142857 0 0 1-73.142857 73.142857H195.047619a73.142857 73.142857 0 0 1-73.142857-73.142857V438.857143a73.142857 73.142857 0 0 1 73.142857-73.142857h390.095238z m0 73.142857H195.047619v390.095238h390.095238V438.857143z m-73.142857 219.428571v73.142857H268.190476v-73.142857h243.809524zM828.952381 121.904762a73.142857 73.142857 0 0 1 73.142857 73.142857v390.095238a73.142857 73.142857 0 0 1-73.142857 73.142857h-121.904762v-73.142857h121.904762V195.047619H438.857143v121.904762h-73.142857V195.047619a73.142857 73.142857 0 0 1 73.142857-73.142857h390.095238zM512 536.380952v73.142858H268.190476v-73.142858h243.809524z" p-id="10158" fill="var(--apix-default-dark-color)"></path></svg>`
  }, 2000)
}

const isTodosVisiable = ref(false)
const triggerTodosVisiable = () => {
  isTodosVisiable.value = !isTodosVisiable.value
}

function onResize() {
  closePopMenu()
}

const abortLabel = '<div style="-webkit-user-select: none !important; -webkit-app-region: no-drag !important; user-select: none !important; color: var(--apix-danger-color); border: 1px solid var(--apix-danger-color); padding: 3px 6px; border-radius: 8px; font-size: 12px; width: fit-content;">流式传输终止</div>'

function postProcessHtml(html: string): string {
  if (!html) return html

  if (html.includes('[Conversation Abort]')) {
    html = html.replace('[Conversation Abort]', '')
    html += abortLabel
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
  document.addEventListener('click', onCodeCopyClick)
  document.addEventListener('selectionchange', handleSelectionChange)
  window.addEventListener('resize', onResize)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', onCodeCopyClick)
  document.removeEventListener('selectionchange', handleSelectionChange)
  window.removeEventListener('resize', onResize)

  revokeAllImageObjectUrls()
})
</script>

<style scoped>
/* ==================== 公共变量 ==================== */
.message-wrapper {
  --msg-transition: background 0.6s var(--apix-cubic-bezier);
  --select-box-border: var(--apix-tertiary-light-color);
  --select-box-hover-border: var(--apix-border-error);
  --select-box-checked-bg: var(--apix-danger-color);
  --select-box-checked-border: var(--apix-danger-color);
  --branch-bg: var(--apix-default-light-color);
  --branch-border: var(--apix-lightest-color);
  --branch-hover-border: var(--apix-default-light-color);
  --branch-label-color: var(--apix-default-dark-color);
  --think-color: var(--apix-tertiary-dark-color);
  --content-color: var(--apix-default-dark-color);
  --info-tag-color: var(--apix-tertiary-light-color);
  --info-tag-hover-color: var(--apix-tertiary-dark-color);
  --bubble-radius: var(--apix-panel-border-radius);
}

/* ==================== 布局 ==================== */
.message-wrapper {
  position: relative;
  width: 840px;
  display: flex;
  flex-direction: row;
  gap: 6px;
  padding: 12px 0px;
  border-radius: var(--bubble-radius);
  align-items: center;
  justify-content: flex-start;
  background: transparent;
  transition: var(--msg-transition);
}

.message-wrapper.selected {
  background: var(--apix-default-light-color);
}

/* ==================== 多选复选框 ==================== */
.message-select-box {
  z-index: 999;
  border: 2px solid var(--select-box-border);
  border-radius: 6px;
  width: 16px;
  min-width: 16px;
  margin-left: 3px;
  height: 16px;
  cursor: pointer;
  transition: border-color 0.15s ease,
              background-color 0.15s ease;
  position: relative;
}

.message-select-box:hover {
  border-color: var(--select-box-hover-border);
}

.message-select-box.checked {
  background-color: var(--select-box-checked-bg);
  border-color: var(--select-box-checked-border);
}

.message-select-box.checked::after {
  content: "";
  position: absolute;
  left: 4px;
  top: 0px;
  width: 5px;
  height: 10px;
  border: solid var(--apix-lightest-color);
  border-width: 0 2px 2px 0;
  transform: rotate(45deg);
}

/* ==================== AI 气泡容器 ==================== */
.ai-bubble-wrapper {
  position: relative;
  display: flex;
  flex-direction: column;
  padding: 0px 16px;
  width: calc(840px - 32px);
}

.ai-bubble-wrapper.is_selecting {
  padding: 0px;
}

/* ==================== 思考块（Think） ==================== */
.think-block {
  word-wrap: break-word;
  position: relative;
  overflow: hidden;
  grid-template-columns: 6px auto;
  min-height: 24px;
  padding: 8px 4px 0px 4px;
}

.think {
  background-color: transparent !important;
  font-size: 14px;
  width: calc(100% - 32px);
  max-height: 300px;
  overflow: scroll;
  padding: 6px 16px 6px 16px;
  color: var(--think-color);
}

.expend-think-btn {
  padding: 0px;
  display: flex;
  flex-direction: row;
  gap: 6px;
  font-size: 14px;
  align-items: center;
  background-color: transparent;
  border: none;
  border-radius: 12px;
  color: var(--apix-tertiary-dark-color);
}

.expend-think-btn.expended_think_btn :deep(.expend-icon) {
  transform: rotate(90deg)
}

.expend-think-btn:hover {
  border: none;
  color: var(--apix-default-dark-color);
}

.expend-think-btn:hover :deep(.icon) {
  fill: var(--apix-secondary-dark-color);
}

.expend-think-btn :deep(.expend-icon) {
  transition: transform .25s var(--apix-cubic-bezier);
  width: 15px !important;
  height: 15px !important;
}

.expend-think-btn :deep(.icon),
.expend-think-btn :deep(.icon-thinking) {
  height: 20px;
  width: fit-content;
  background-color: transparent;
  border: none;
  fill: var(--apix-tertiary-dark-color);
}

.btn-text {
  display: inline-block;
  white-space: nowrap;
}

.btn-text.breath {
  background-image: linear-gradient(
    90deg,
    var(--apix-default-dark-color) 0%,
    var(--apix-default-dark-color) 30%,
    var(--apix-default-light-color) 50%,
    var(--apix-default-dark-color) 70%,
    var(--apix-default-dark-color) 100%
  );
  background-size: 300%;
  background-clip: text;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  animation: Gradient 3.5s ease infinite;
}

@keyframes Gradient {
  0% {
    background-position: 150% 50%;
  }
  100% {
    background-position: -50% 50%;
  }
}

/* ==================== 待办（Todos） ==================== */
.expend-todos-btn-wrapper {
  padding: 12px 0px;
}

.expend-todos-btn {
  border-radius: var(--apix-button-border-radius);
  border: 1px solid var(--apix-primary-color);
  color: var(--apix-primary-color);
  background: var(--apix-panel-layer-2-background);
  height: 28px;
  padding-left: 14px;
  display: flex;
  flex-direction: row;
  gap: 8px;
  transition:
    transform 0.20s var(--apix-cubic-bezier),
    border 0.20s var(--apix-cubic-bezier),
    color 0.20s var(--apix-cubic-bezier);
}

.expend-todos-btn :deep(.icon) {
  padding-top: 1px;
  width: 18px;
  height: 18px;
}

.expend-todos-btn:hover {
  transform: scale(1.03);
  border: 1px solid var(--apix-primary-hover);
  color: var(--apix-primary-hover);
}
.expend-todos-btn:active {
  transform: scale(1.01);
  border: 1px solid var(--apix-primary-active);
  color: var(--apix-primary-active);
}

.todos-block {
  padding: 6px 0px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  border-radius: 24px;
}

/* ==================== AI 回答正文 ==================== */
.ai-bubble {
  word-wrap: break-word;
  position: relative;
  overflow: hidden;
  align-self: center;
  display: flex;
  flex-direction: column;

  width: 100%;
  max-width: calc(840px - 32px);
  padding: 0px;
  gap: 16px;
  line-height: 1.6;
}

.content {
  color: var(--content-color);
}

/* ==================== 图片展示区域 ==================== */
.ai-images-wrapper {
  position: relative;
  overflow: visible;
  padding-bottom: 12px;
  max-width: calc(840px - 50px);
}

.ai-images-scroller {
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
  width: 100%;
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 6px;
  margin-top: 10px;
}

.ai-image-card {
  position: relative;
  flex-shrink: 0;
  width: 198px;
  height: 146px;
  border-radius: 12px;
  overflow: visible;
  background: transparent;
  display: flex;
  align-items: center;
  justify-content: center;
}

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
  background: color-mix(in oklch, var(--apix-default-light-color) 80%, transparent);
  backdrop-filter: saturate(300%) blur(6px);
  box-shadow: var(--apix-shadow-layer-3);
  transition: opacity 0.25s var(--apix-cubic-bezier), transform 0.25s var(--apix-cubic-bezier);
}

.ai-image-preview {
  display: block;
  width: auto;
  height: auto;
  max-width: 360px;
  max-height: 400px;
  object-fit: contain;
  border-radius: 10px;
}

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
  color: var(--apix-default-light-color);
  border-radius: 12px;
  background: transparent;
}

/* ==================== 信息标签（Provider/Model/Tokens） ==================== */
.info-tag {
  display: flex;
  flex-direction: row;
  font-size: 11px;
  gap: 16px;
  padding: 2px 4px;
  color: var(--info-tag-color);
  transition: color 0.15s ease;
  width: inherit;
  height: 20px;
  overflow: scroll;
  scrollbar-width: none;
}

.info-tag:hover {
  color: var(--info-tag-hover-color);
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
  align-items: center;
  gap: 4px;
  white-space: nowrap;
}

.tag-name {
  padding: 0px 4px;
  border-radius: 4px;
  border: none;
  background-color: var(--apix-default-light-color);
}

.online-info-btn {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 3px;
  color: inherit;
}

.online-info-btn:active {
  transform: scale(0.95);
}

/* ==================== 分支切换器 ==================== */
.branch-switch-wrapper {
  opacity: 0.4;
  width: calc(840px - 34px);
  margin-bottom: 12px;
  display: grid;
  grid-template-columns: 45% 10% 45%;
  justify-content: space-between;
  align-items: center;
}

.branch-switch-wrapper:hover {
  opacity: 1;
}

.branch-switch-label-wrapper {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 4px 0px;
  border-radius: 20px;
  margin: 0px auto;
  width: fit-content;
}

.branch-switch-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 16px;
  border: none;
  border-radius: 50%;
  background: transparent;
  cursor: pointer;
  padding: 0;
}

.branch-switch-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.branch-page-label {
  font-size: 14px;
  font-weight: 500;
  color: var(--branch-label-color);
  min-width: 32px;
  text-align: center;
  user-select: none;
  font-variant-numeric: tabular-nums;
}

/* ==================== 右键菜单 & 选区气泡动画 ==================== */
.scale-fade-enter-active {
  animation: scaleFadeIn 0.25s var(--apix-cubic-bezier);
}
.scale-fade-leave-active {
  animation: scaleFadeOut 0.2s var(--apix-cubic-bezier);
}

.opacity-fade-enter-active {
  animation: opacityFadeIn 0.25s var(--apix-cubic-bezier);
}
.opacity-fade-leave-active {
  animation: opacityFadeOut 0.2s var(--apix-cubic-bezier);
}

@keyframes scaleFadeIn {
  0% { opacity: 0; transform: scale(0.9) translateY(6px); }
  60% { opacity: 1; transform: scale(1.01) translateY(0); }
  100% { opacity: 1; transform: scale(1); }
}
@keyframes scaleFadeOut {
  0% { opacity: 1; transform: scale(1); }
  100% { opacity: 0; transform: scale(0.95) translateY(6px); }
}
@keyframes opacityFadeIn {
  0% { opacity: 0; transform: scale(0.9); }
  100% { opacity: 1; transform: scale(1); }
}
@keyframes opacityFadeOut {
  0% { opacity: 1; transform: scale(1); }
  100% { opacity: 0; transform: scale(0.95); }
}
</style>

<style scoped>
/* ==================== Markdown 通用表格/代码块增强 ==================== */
.markdown-body:deep(table) {
  position: relative;
  background-color: var(--apix-panel-layer-2-background) !important;
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
  padding: 16px;
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
  top: 0px;
  right: 0px;
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
  z-index: 9999;
}

:deep(.code-copy-btn .icon) {
  width: 24px;
  height: 24px;
  fill: var(--apix-secondary-dark-color);
}

:deep(.code-block:hover .code-copy-btn) {
  opacity: 1;
}
</style>