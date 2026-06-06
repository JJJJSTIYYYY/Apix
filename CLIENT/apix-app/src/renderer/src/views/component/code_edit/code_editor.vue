<template>
  <div class="warn-banner-wrapper" v-if="showWarnBannerInCodeEditor">
    <div class="warn-banner">
      <el-icon><Warning /></el-icon>
      <span>编辑文件建议使用如 VS Code 等专业代码编辑器，此编辑器仅提供部分格式的代码文件与基础文本编辑能力！</span>
    </div>
    <div class="close-banner-btn" @click="showWarnBannerInCodeEditor = false">
      <svg t="1780741208778" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="8755" width="16" height="16"><path d="M512 570.88l196.864 196.8 58.88-58.88L570.752 512l196.864-196.864-58.816-58.88L512 453.248 315.136 256.32l-58.88 58.88L453.248 512l-196.864 196.864 58.88 58.88z" fill="currentColor" p-id="8756"></path></svg>
    </div>
  </div>
  <div class="markdown-editor-root">
    <!-- Search panel -->
    <SearchPanel
      :visible="showSearchPanel"
      v-model:searchText="searchText"
      v-model:replaceText="replaceText"
      v-model:caseSensitive="searchCaseSensitive"
      v-model:wholeWord="wholeWord"
      v-model:regexp="searchRegexp"
      :total-match="searchMatchCount"
      :current-match="searchMatchIndex"
      @next="searchNext"
      @prev="searchPrev"
      @replace-one="replaceOne"
      @replace-all="replaceAllText"
      @close="closeSearchPanel"
    />

    <!-- Editor -->
    <div
      ref="editorRef"
      class="editor"
    />
  </div>
</template>

<script setup lang="ts">
import {
  ref,
  shallowRef,
  onMounted,
  onBeforeUnmount,
  watch,
  nextTick
} from 'vue'

import {
  EditorState,
  Compartment
} from '@codemirror/state'

import {
  EditorView,
  keymap,
  lineNumbers,
  highlightActiveLine
} from '@codemirror/view'

import {
  defaultKeymap,
  history,
  historyKeymap
} from '@codemirror/commands'

import {
  highlightSelectionMatches,
  SearchQuery,
  setSearchQuery,
  getSearchQuery,
  findNext,
  findPrevious,
  replaceNext,
  replaceAll
} from '@codemirror/search'

import {
  markdown
} from '@codemirror/lang-markdown'

import {
  javascript
} from '@codemirror/lang-javascript'

import {
  python
} from '@codemirror/lang-python'

import {
  oneDark
} from '@codemirror/theme-one-dark'

import {
  githubLight
} from '@fsegurai/codemirror-theme-github-light'

import type {
  ViewUpdate
} from '@codemirror/view'

import SearchPanel from './search_panel.vue'
import { showWarnBannerInCodeEditor } from '../../../store/globalData'

const props = defineProps<{
  modelValue: string
  theme: string
  lang?: string
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
  (e: 'change:modelValue'): void
}>()

export type MarkdownEditorExpose = {
  applyPatch: (
    patch: {
      from: number
      to: number
      insert: string
    }[]
  ) => void
}

// ------------------------
// Language compartment
// ------------------------
const languageCompartment = new Compartment()

function getLanguageExtension(lang?: string) {
  switch ((lang || 'md').toLowerCase()) {
    case 'js':
    case 'javascript':
      return javascript()

    case 'py':
    case 'python':
      return python()

    case 'md':
    case 'markdown':
    default:
      return markdown()
  }
}

// ------------------------
// Refs
// ------------------------
const editorRef = ref<HTMLDivElement>()
const editorView = shallowRef<EditorView>()

let applyingPatch = false

function applyPatch(
  patch
) {
  if (!editorView.value) return

  applyingPatch = true

  editorView.value.dispatch({
    changes: patch
  })

  applyingPatch = false
}

defineExpose({
  applyPatch
})

// ------------------------
// Search state
// ------------------------
const showSearchPanel = ref(false)
const searchText = ref('')
const replaceText = ref('')
const searchCaseSensitive = ref(false)
const wholeWord = ref(false)
const searchRegexp = ref(false)

// Match state
const searchMatchIndex = ref(0)
const searchMatchCount = ref(0)

// ------------------------
// Theme compartment
// ------------------------
const themeCompartment = new Compartment()

// ------------------------
// Create editor
// ------------------------
onMounted(() => {
  const state = EditorState.create({
    doc: props.modelValue || '',
    extensions: [
      lineNumbers(),
      highlightActiveLine(),
      languageCompartment.of(
        getLanguageExtension(props.lang)
      ),
      themeCompartment.of(
        props.theme === 'dark' ? oneDark : githubLight
      ),
      EditorView.lineWrapping,
      history(),
      highlightSelectionMatches(),
      keymap.of([
        ...defaultKeymap,
        ...historyKeymap,
      ]),
      EditorView.updateListener.of(onModelValueChange)
    ]
  })

  editorView.value = new EditorView({
    state,
    parent: editorRef.value
  })

  window.addEventListener('keydown', onWindowKeydown)
})

// ------------------------
// Content update
// ------------------------
function onModelValueChange(update: ViewUpdate) {
  if (!update.docChanged) return

  emit(
    'update:modelValue',
    update.state.doc.toString()
  )

  // Ignore external patch sync
  if (applyingPatch) {
    return
  }

  emit('change:modelValue')

  updateSearchMatches()
}

// ------------------------
// Search
// ------------------------
function updateSearchQuery(replace: string | null = null) {
  const view = editorView.value
  if (!view) return
  view.dispatch({
    effects: setSearchQuery.of(
      new SearchQuery({
        search: searchText.value,
        caseSensitive: searchCaseSensitive.value,
        wholeWord: wholeWord.value,
        regexp: searchRegexp.value,
        replace
      })
    )
  })
}

function updateSearchMatches() {
  const view = editorView.value

  if (!view) {
    searchMatchIndex.value = 0
    searchMatchCount.value = 0
    return
  }

  const query = getSearchQuery(view.state)

  // Empty search
  if (!query.search) {
    searchMatchIndex.value = 0
    searchMatchCount.value = 0
    return
  }

  const cursor = query.getCursor(
    view.state.doc
  )

  const matches: Array<{
    from: number
    to: number
  }> = []

  while (!cursor.next().done) {
    matches.push({
      from: cursor.value.from,
      to: cursor.value.to
    })
  }

  searchMatchCount.value =
    matches.length

  if (!matches.length) {
    searchMatchIndex.value = 0
    return
  }

  const selection =
    view.state.selection.main

  const currentIndex =
    matches.findIndex(match => {
      return (
        selection.from === match.from &&
        selection.to === match.to
      )
    })

  searchMatchIndex.value =
    currentIndex >= 0
      ? currentIndex + 1
      : 1
}

function searchNext() {
  const view = editorView.value
  if (!view) return
  updateSearchQuery()
  findNext(view)
  updateSearchMatches()
}

function searchPrev() {
  const view = editorView.value
  if (!view) return
  updateSearchQuery()
  findPrevious(view)
  updateSearchMatches()
}

function replaceOne() {
  const view = editorView.value
  if (!view) return
  updateSearchQuery(replaceText.value)
  replaceNext(view)
  updateSearchMatches()
}

function replaceAllText() {
  const view = editorView.value
  if (!view) return
  updateSearchQuery(replaceText.value)
  replaceAll(view)
  updateSearchMatches()
}

async function openSearchPanel() {
  const view = editorView.value
  if (view) {
    const selection = view.state.selection.main
    // Get selected text
    const selectedText = view.state.sliceDoc(selection.from, selection.to)
    // Use selected text if not empty
    if (selectedText) {
      searchText.value = selectedText
    }
  }

  showSearchPanel.value = false
  await nextTick()
  showSearchPanel.value = true
  updateSearchQuery()
  updateSearchMatches()
}

function closeSearchPanel() {
  const view = editorView.value
  if (!view) return
  showSearchPanel.value = false
  view.focus()
  // Clear search highlight
  view.dispatch({
    effects: setSearchQuery.of(
      new SearchQuery({
        search: '',
      })
    )
  })
  searchMatchIndex.value = 0
  searchMatchCount.value = 0
}

// ------------------------
// Window keydown
// ------------------------
function onWindowKeydown(e: KeyboardEvent) {
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'f') {
    e.preventDefault()
    openSearchPanel()
  }

  if (e.key === 'Escape' && showSearchPanel.value) {
    closeSearchPanel()
  }

  if (e.key === 'Enter' && showSearchPanel.value) {
    e.preventDefault()
    if (e.shiftKey) {
      searchPrev()
    } else {
      searchNext()
    }
  }
}

// ------------------------
// Sync search query
// ------------------------
watch(
  [searchText, searchCaseSensitive, searchRegexp, wholeWord],
  () => {
    updateSearchQuery()
    updateSearchMatches()
  }
)

// ------------------------
// Sync modelValue
// ------------------------
watch(
  () => props.modelValue,
  value => {
    const view = editorView.value
    if (!view) return
    const current = view.state.doc.toString()
    if (current === value) return
    view.dispatch({
      changes: {
        from: 0,
        to: current.length,
        insert: value || ''
      }
    })
    updateSearchMatches()
  }
)

// ------------------------
// Sync theme
// ------------------------
watch(
  () => props.theme,
  theme => {
    const view = editorView.value
    if (!view) return
    view.dispatch({
      effects: themeCompartment.reconfigure(
        theme === 'dark' ? oneDark : githubLight
      )
    })
  }
)

// ------------------------
// Sync language
// ------------------------
watch(
  () => props.lang,
  lang => {
    const view = editorView.value

    if (!view) {
      return
    }

    view.dispatch({
      effects: languageCompartment.reconfigure(
        getLanguageExtension(lang)
      )
    })
  }
)

// ------------------------
// Destroy
// ------------------------
onBeforeUnmount(() => {
  window.removeEventListener('keydown', onWindowKeydown)
  editorView.value?.destroy()
})
</script>

<style scoped>
.warn-banner-wrapper {
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
  color: var(--apix-tertiary-dark-color);
  font-size: 12px;
}

.warn-banner {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 6px;
  padding: 0 12px;
}

.close-banner-btn {
  width: 16px;
  height: 16px;
  border-radius: 3px;
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: center;
}

.close-banner-btn:hover {
  background-color: var(--apix-default-light-color);
}

/* CodeMirror root */
:deep(.cm-editor) {
  height: 100%;
  font-size: 14px;
  background-color: transparent !important;
  position: unset !important;
  padding-bottom: 300px;
}

/* Scroll */
:deep(.cm-scroller) {
  overflow: auto;
  position: unset !important;
}

:deep(.cm-gutters) {
  background-color: transparent !important;
  color: var(--apix-tertiary-dark-color);
  border-right: 1px solid var(--apix-default-light-color);
}

:deep(.cm-panels.cm-panels-bottom) {
  opacity: 0;
  pointer-events: none;
  height: 0 !important;
  width: 0 !important;
  overflow: hidden;
}

:deep(.cm-searchMatch) {
  outline: none !important;
  background-color: color-mix(in srgb, var(--apix-primary-color) 40%, transparent) !important;
}

:deep(.cm-searchMatch.cm-searchMatch-selected) {
  outline: none !important;
  box-shadow: inset 0 0 0 1px var(--apix-primary-active) !important;
  /* background-color: var(--apix-primary-color) !important; */
  /* color: var(--apix-lightest-color) !important; */
  background-color: transparent !important;
}

:deep(.cm-selectionMatch) {
  outline: none !important;
  box-shadow: none !important;
  background-color: color-mix(in srgb, var(--apix-primary-color) 20%, transparent) !important;
}

:deep(.cm-focused) {
  box-shadow: none !important;
  border: none !important;
}
</style>