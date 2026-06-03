<template>
  <div class="question-view">

    <!-- Header -->
    <div class="qv-header">
      <div class="qv-title">
        需要回答以下问题<span v-if="questions.length>1">（{{ currentIndex + 1 }}/{{ questions.length }}）</span>
      </div>

      <div
        v-if="questions.length>1"
        class="qv-nav-btn-wrapper"
      >
        <div class="qv-nav">

          <button
            class="qv-nav-btn"
            :disabled="currentIndex <= 0"
            @click="prevQuestion"
          >
            <svg t="1779563021749" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="6619" width="20" height="20"><path d="M490.1 163.6L179.5 474.2H960v75.7H179.5l310.6 306.6-55.8 55.8L64 537.9v-51.8l370.3-374.3 55.8 51.8z" fill="currentColor" p-id="6620"></path></svg>
          </button>

          <button
            class="qv-nav-btn"
            :disabled="currentIndex >= questions.length - 1"
            @click="nextQuestion"
          >
            <svg t="1779563051470" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="6832" width="20" height="20"><path d="M529.9 858.5l310.6-310.6H64v-71.7h776.5L529.9 165.6l55.8-51.8L960 484.1v55.8L585.7 910.2l-55.8-51.8z" fill="currentColor" p-id="6833"></path></svg>
          </button>

        </div>
      </div>
    </div>

    <!-- Question -->
    <div class="qv-question">
      {{ currentQuestion.question }}
    </div>

    <!-- Options -->
    <div
      class="qv-options"
    >

      <button
        v-for="option in currentQuestion.options"
        :key="option"
        class="qv-option"
        :class="{ active: selectedOptions.includes(option) }"
        @click="selectOption(option)"
      >
        {{ option }}
      </button>

      <!-- Custom Input Option -->
      <div
        class="qv-input-wrapper"
        :class="{ active: isCustomMode }"
        @click="activateCustomInput"
      >
        <el-input
          v-model="customInput"
          class="qv-input"
          placeholder="输入自定义回答..."
          type="textarea"
          :rows="1"
          @focus="activateCustomInput"
          @input="onCustomInput"
        />
      </div>

    </div>

    <!-- Footer -->
    <div class="qv-footer">

      <button class="qv-confirm" type="primary" @click="submitAll">
        <svg t="1777266449849" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="9749" width="24" height="24"><path class="confirm-icon-path" d="M512 76.8C271.36 76.8 76.8 271.36 76.8 512s194.56 435.2 435.2 435.2 435.2-194.56 435.2-435.2S752.64 76.8 512 76.8z m0 768c-184.32 0-332.8-148.48-332.8-332.8S327.68 179.2 512 179.2s332.8 148.48 332.8 332.8-148.48 332.8-332.8 332.8z" p-id="9750" fill="currentColor"></path></svg>
        <span>确认</span>
      </button>

    </div>

  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'

export type QuestionItem = {
  question: string
  options?: string[]
  response?: string | string[]
  multiselection?: boolean
}

const props = defineProps<{
  questions: QuestionItem[]
  qid: string
}>()

const emit = defineEmits<{
  complete: [string, QuestionItem[]]
  change: [string, QuestionItem[]]
}>()

const currentIndex = ref(0)
const customInput = ref('')

const currentQuestion = computed(() => {
  return props.questions[currentIndex.value]
})

const isMultiple = computed(() => {
  return !!currentQuestion.value.multiselection
})

const selectedOptions = computed(() => {

  const response = currentQuestion.value?.response

  if (Array.isArray(response)) {
    return response
  }

  if (typeof response === 'string' && response) {
    return [response]
  }

  return []
})

const isCustomMode = computed(() => {

  const response = currentQuestion.value?.response
  const options = currentQuestion.value.options || []

  if (!response) {
    return false
  }

  // Multi selection
  if (Array.isArray(response)) {
    return response.some(item => !options.includes(item))
  }

  // Single selection
  return !options.includes(response)
})

watch(
  currentQuestion,
  (question) => {

    const response = question?.response
    const options = question?.options || []

    // Multi selection
    if (Array.isArray(response)) {

      const customValues = response.filter(
        item => !options.includes(item)
      )

      customInput.value = customValues.join('\n')
      return
    }

    // Single selection
    if (
      response &&
      !options.includes(response)
    ) {
      customInput.value = response
      return
    }

    customInput.value = ''
  },
  { immediate: true }
)

function emitChange() {
  emit('change', props.qid, props.questions)
}

function nextQuestion() {

  if (currentIndex.value >= props.questions.length - 1) {
    return
  }

  currentIndex.value += 1
}

function prevQuestion() {

  if (currentIndex.value <= 0) {
    return
  }

  currentIndex.value -= 1
}

function selectOption(option: string) {

  // Multi selection
  if (isMultiple.value) {

    const current = [...selectedOptions.value]
    const index = current.indexOf(option)

    if (index >= 0) {
      current.splice(index, 1)
    } else {
      current.push(option)
    }

    currentQuestion.value.response = current

    emitChange()
    return
  }

  // Single selection
  currentQuestion.value.response = option

  emitChange()
}

function activateCustomInput() {

  updateCustomResponse()
}

function onCustomInput() {

  updateCustomResponse()
}

function updateCustomResponse() {

  // Multi selection
  if (isMultiple.value) {

    const options = currentQuestion.value.options || []

    const customValues = customInput.value
      .split('\n')
      .map(item => item.trim())
      .filter(Boolean)

    const selectedBuiltinOptions = selectedOptions.value.filter(
      item => options.includes(item)
    )

    currentQuestion.value.response = [
      ...selectedBuiltinOptions,
      ...customValues
    ]

    emitChange()
    return
  }

  // Single selection
  currentQuestion.value.response = customInput.value

  emitChange()
}

function submitAll() {
  console.log("[submitAll] Confirm question result: ", props.questions)
  emit('complete', props.qid, props.questions)
}
</script>

<style scoped>
.question-view {
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: 100%;
  padding: 16px;
  box-sizing: border-box;
  background-color: var(--apix-panel-layer-2-background);
  color: var(--apix-default-dark-color);
  border-radius: 10px;
  border: 1px solid var(--apix-secondary-light-color);
}

.qv-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  border-bottom: .5px solid var(--apix-border-disabled);
  padding: 3px 0;
}

.qv-title {
  font-size: 15px;
  font-weight: 600;
}

.qv-nav-btn-wrapper {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 4px;
}

.qv-nav {
  display: flex;
  gap: 18px;
}

.qv-nav-btn {
  padding: 0;
  background-color: transparent;
  box-shadow: none;
  border: 0;
  cursor: pointer;
  color: var(--apix-default-dark-color);
  transition: 
    transform 0.35s var(--apix-cubic-bezier);
}

.qv-nav-btn:not(:disabled):hover {
  transform: scale(1.2);
}

.qv-nav-btn:disabled {
  color: var(--apix-secondary-dark-color);
  cursor: not-allowed;
}

.qv-question {
  font-size: 16px;
  line-height: 1.6;
  white-space: pre-wrap;
  padding: 3px 0;
}

.qv-options {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.qv-option {
  padding: 10px 14px;
  text-align: left;
  cursor: pointer;
  transition: all 0.15s ease;
  border: 0;
  border-radius: var(--apix-button-border-radius) !important;
  box-shadow: inset 0 0 0 1px var(--apix-secondary-light-color) !important;
  height: 42px !important;
  background: transparent;
  color: var(--apix-primary-dark) !important;
}

.qv-option.active {
  font-weight: 600;
  box-shadow: inset 0 0 0 2px var(--apix-primary-color) !important;
}

.qv-input-wrapper {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-bottom: 2px;
}

.qv-input {
  min-height: 42px;
  resize: vertical;
  box-sizing: border-box;
  font-size: 14px;
  line-height: 1.5;
}

.qv-input :deep(.el-textarea__inner) {
  box-sizing: border-box;
  min-height: 42px !important;
  box-shadow: inset 0 0 0 1px var(--apix-secondary-light-color) !important;
  border-radius: var(--apix-button-border-radius) !important;
  padding: 12px;
  background: transparent;
  color: var(--apix-primary-dark) !important;
  line-height: 1.5;
  scrollbar-width: none;
}

.qv-input :deep(.el-textarea__inner:hover) {
  box-shadow: inset 0 0 0 1px var(--apix-secondary-light-color) !important;
}

.qv-input :deep(.el-textarea__inner:focus) {
  box-shadow: inset 0 0 0 2px var(--apix-primary-color) !important;
  background: transparent !important;
  outline: none;
}

.qv-input-wrapper.active :deep(.el-textarea__inner){
  box-shadow: inset 0 0 0 2px var(--apix-primary-color) !important;
}

.qv-footer {
  display: flex;
  flex-direction: column;
  padding-top: 6px;
}

.qv-confirm {
  align-self: flex-end;
  width: 68px;
  height: 30px;
  font-size: 14px;
  border-radius: 100px;
  background-color: var(--apix-primary-color);
  color: var(--apix-primary-text);
  border: none;
  cursor: pointer;
  display: flex;
  gap: 3px;
  padding: 1px 4px;
  align-items: center;
  transition: 
    transform 0.35s var(--apix-cubic-bezier),
    box-shadow 0.35s var(--apix-cubic-bezier),
    background 0.35s var(--apix-cubic-bezier);
}

.qv-confirm:hover {
  transform: scale(1.08);
  box-shadow: var(--apix-shadow-layer-1);
}

.qv-confirm:active {
  transform: scale(0.95);
  box-shadow: var(--apix-shadow-layer-2);
}
</style>