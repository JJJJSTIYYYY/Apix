<template>
  <div
    class="chat-history q"
  >
    <div ctrl-area-wrapper class="ctrl-area-wrapper">
      <div class="ctrl-line q-search">
        <div class="search-wrapper">
          <el-input
            v-model="searchKeyword"
            placeholder="搜索"
            size="small"
            clearable
            @input="handleSearch"
            @focus="isSearchFocused = true"
            @blur="isSearchFocused = false"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
        </div>
      </div>
    </div>

    <!-- List -->
    <transition name="fade">
      <div style="flex: 1; min-height: 0; display: flex;">
        <el-scrollbar class="q-scroll" max-height="100%">
          <div class="q-scroll-inner">
            <el-menu
              class="q-menu"
              @select="handleSelect"
            >
              <div
                v-for="group in groupedHistories"
                :key="group.date"
                class="q-section"
              >
                <button class="q-section-title" @click="switchFold(group.date)">{{ group.date }}</button>

                <el-menu-item
                  v-for="h in group.items"
                  v-if="foldStatus[group.date]"
                  :key="h.id"
                  :index="String(h.id)"
                  class="q-cell"
                >
                  <HistoryCard
                    :history="h"
                    @rename-history="handleRenameHistory"
                    @delete-history="handleDeleteHistory"
                  />
                </el-menu-item>
              </div>

              <div v-if="filteredHistories.length === 0" class="q-empty">
                <el-icon class="shadow-icon" style="font-size: 48px;"><Search /></el-icon>
                <div style="margin-top: 8px;">暂无对话历史</div>
              </div>
            </el-menu>
          </div>
        </el-scrollbar>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { ElMessage } from 'element-plus'

import HistoryCard, { type ChatHistory } from './history_card.vue'
import { ConfirmDialog } from '../../comp/confirmDialog.js'
import { useAuthStore } from '../../../../store/auth.js'

const props = defineProps<{
  histories?: ChatHistory[]
}>()

const emit = defineEmits<{
  select: [id: number | string]
  rename: [id: number | string, newTitle: string]
  delete: [id: number | string]
}>()

const searchKeyword = ref('')
const filteredHistories = ref<ChatHistory[]>([])

const authStore = useAuthStore()
const cid = ref('')

const isSearchFocused = ref(false)

// fold 状态
const foldStatus = ref<Record<string, boolean>>({
  '已收藏': true,
  '今天': true,
  '昨天': true,
  '这周内': true,
  '更早以前': false,
})

// grouped list
const groupedHistories = computed(() => {
  const starred: ChatHistory[] = []
  const normalGroups: Record<string, ChatHistory[]> = {}

  for (const item of filteredHistories.value) {
    if (item.star) {
      starred.push(item)
    } else {
      ;(normalGroups[item.date] ||= []).push(item)
    }
  }

  const result: { date: string; items: ChatHistory[] }[] = []

  if (starred.length > 0) {
    result.push({
      date: '已收藏',
      items: [...starred].sort((a, b) => b.createTime - a.createTime),
    })
  }

  const normalGroupList = Object.entries(normalGroups)
    .map(([date, items]) => ({
      date,
      items: [...items].sort((a, b) => b.createTime - a.createTime),
    }))
    .sort((a, b) => (b.items[0]?.createTime ?? 0) - (a.items[0]?.createTime ?? 0))

  result.push(...normalGroupList)

  return result
})

const handleSearch = () => {
  const list = props.histories ? [...props.histories] : []
  const kw = searchKeyword.value.trim().toLowerCase()

  if (!kw) {
    filteredHistories.value = list
    return
  }

  filteredHistories.value = list.filter((h) =>
    (h.preview || '').toLowerCase().includes(kw)
  )
}

const handleSelect = (index: string) => {
  emit('select', isNaN(Number(index)) ? index : Number(index))
}

const switchFold = (date: string) => {
  foldStatus.value[date] = !foldStatus.value[date]
}

const handleRenameHistory = async (history_id: string, new_title: string) => {
  try {
    await window.api.updateConversation(
      cid.value,
      '',
      history_id,
      { title: new_title }
    )
    ElMessage({ type: 'success', message: '已更新', plain: true })
  } catch (err) {
    console.error("[handleRenameHistory error]:" + err)
    ElMessage({ type: 'error', message: '更新失败', plain: true })
  }
  emit('rename', history_id, new_title)
}

const handleDeleteHistory = async (history_id: string) => {
  const index = props.histories?.findIndex(c => String(c.id) === history_id) ?? -1
  if (index === -1) return

  const history = props.histories![index]

  try {
    await ConfirmDialog.confirm(
      `确定要删除对话 "${history.preview.slice(0, 8)}..." 吗？`,
      '删除确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )
  } catch (err) {
    return
  }

  try {
    await window.api.updateConversation(
      cid.value,
      '',
      history_id,
      { deleted: true }
    )
    ElMessage({ type: 'success', message: '已删除', plain: true })
    emit('delete', history_id)
  } catch (err) {
    console.error("[handleDeleteHistory error]:" + err)
    ElMessage({ type: 'error', message: '删除失败', plain: true })
  }
}

onMounted(async () => {
  await authStore.restore()
  cid.value = authStore.user.user_uid

  filteredHistories.value = props.histories ? [...props.histories] : []
})

onBeforeUnmount(() => {
})

watch(
  () => props.histories,
  (list) => {
    filteredHistories.value = list ? [...list] : []
    handleSearch()
  },
  { deep: true }
)
</script>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.28s var(--apix-cubic-bezier);
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* Layout */
.chat-history.q {
  z-index: 99;
  height: calc(100vh - 170px);
  display: flex;
  flex-direction: column;
  background: transparent;
  width: 420px; 
  max-width: 420px;

  border-radius: var(--apix-border-radius-base) 0 0 var(--apix-border-radius-base);
}

.ctrl-area-wrapper {
  margin-top: 8px;
  display: flex;
  flex-direction: column;
  border-radius: var(--apix-default-border-radius);
  transition: 
    box-shadow 0.3s var(--apix-cubic-bezier),
    background 0.3s var(--apix-cubic-bezier);
}

.ctrl-line {
  padding: 5px;
  display: flex;
  align-items: center;
  gap: 6px;
  transition: width 0.22s ease;
}

.search-wrapper {
  width: 100%;
  display: flex;
  gap: 12px;
}

.search-wrapper :deep(.el-input) {
  flex: 1;
  min-width: 0;
  height: 38px !important;
}

.search-wrapper :deep(.el-input__wrapper) {
  height: 38px !important;
  padding: 0 12px 0 10px;
  background: transparent;
  background-color: var(--apix-panel-layer-4-background);
  border: none;
  border-radius: var(--apix-border-radius-base);
  box-shadow: var(--apix-shadow-layer-1);
  transition: all 0.13s var(--apix-cubic-bezier);
}

/* Scroll */
.q-scroll {
  flex: 1;
  overflow: hidden;
  background: transparent;
  border: none;
  transition: transform 0.22s var(--apix-cubic-bezier);
  scrollbar-width: none;
}
.q-scroll :deep(.el-scrollbar__bar) {
  display: none !important;
}
.q-scroll :deep(.el-scrollbar__wrap) {
  max-height: 100% !important;
}

.q-menu {
  position: relative;
  border: none;
  background: transparent;
  padding: 0 !important;
  padding-bottom: 10px !important;
}
.q-menu :deep(.el-menu-item.q-cell) {
  position: relative;
  z-index: 1;

  height: auto;
  min-height: 36px;
  padding: 3px 3px;
  margin: 0;
  background: transparent;
}

/* Menu / Section */
.q-section {
  background: transparent;
  overflow: hidden;
}
.q-section-title {
  margin: 8px 6px 6px 6px;
  padding: 1px 6px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.4px;
  color: var(--apix-tertiary-dark-color);
  border: none;
  border-left: 2px solid var(--apix-primary-color);
  background-color: transparent;
}
.q-section-title:hover {
  color: var(--apix-primary-hover);
}

/* Empty */
.q-empty {
  padding: 46px 12px;
  text-align: center;
  color: var(--apix-tertiary-dark-color);
  align-items: center;
  justify-content: center;
}

.q-empty:deep(*) {
  color: var(--apix-tertiary-dark-color);
}

/* Mobile */
@media (max-width: 768px) {
  .chat-history.q {
    min-width: 240px;
  }
}
</style>