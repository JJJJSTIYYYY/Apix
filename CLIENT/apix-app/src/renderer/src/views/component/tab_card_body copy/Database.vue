<template>
  <div 
    class="tab-card"
    :class="{ expanded: self.expanded }"
  >
    <!-- 卡片头 -->
    <div
      class="tab-card-header"
      :class="{ expanded: self.expanded }"
      :draggable="!self.expanded"
      @dragstart.stop="onTabCardDragStart($event)"
    >
      <div style="display: flex; flex-direction: row;">
        <div style="width: 16px; height: 16px; align-self: center;"></div>
        <input
          class="tab-title-input no-drag"
          v-model="titleInput"
          :placeholder="'数据库测试'"
          @change="onTabCardTitleChange($event)"
          @keyup.enter="onTabCardTitleChange($event)"
          @mouseup="onMouseUp_input($event)"
          @focusout="onMouseUp_input($event)"
          @mousemove="onMouseUp_input($event)"
          @mouseenter="onMouseUp_input($event)"
        />
      </div>

      <transition name="scale-fade">
        <PopMenu 
          v-if="isShowMenu"
          :style="menuStyle"
          @close-menu="closePopMenu"
          @save-card="saveCardAsPredefined"
          @mark-card="markCard"
          @mark-content="updateMarkContent"
        />
      </transition>

      <el-tooltip
        v-if="isShowMark_"
        :content="markMessage"
        placement="left"
        effect="light"
        raw-content
      >
        <transition name="scale-fade">
          <el-button key="11" v-if="isShowMark" class="mark-btn" :class="{ mark_btn_right: mark_btn_right }" @click="hideMark"></el-button>
        </transition>
      </el-tooltip>

      <div class="tab-card-btn-area"
        @mouseenter="mark_btn_right = false"
        @mouseleave="mark_btn_right = true"
      >
        <el-button
          ref="menuBtnRef"
          type="info"
          @click="showPopMenu"
          class="tab-card-btn-menu"
        >
          <el-icon><More /></el-icon>
        </el-button>

        <el-button
          :type="self.btnType"
          @click="editTabCard()"
          class="tab-card-btn-more"
          :class="{ tabcardbtnmoreexpanded: self?.expanded }"
        >
          <el-icon>
            <component :is="self.btnIcon" />
          </el-icon>
        </el-button>

        <el-button
          type="danger"
          @click="removeThisCard()"
          class="tab-card-btn-close"
        >
          <el-icon><Close /></el-icon>
        </el-button>
      </div>
    </div>  

    <!--  database 卡片体 -->
    <div v-if="self.showCardBody" class="database-card-body">
      <div class="database-body-wrapper" :style="{height: 'auto', overflow: 'auto', scrollbarWidth: 'none'}">
        <div
          class="database-content"
          draggable="false"
          style="display: grid; gap: 4px; grid-template-columns: 15% 85%; min-height: auto"
        >

          <div style="width: 100%; height: 32px; display: flex; justify-content: center; align-items: center; column-count: 1;">
            数据库连接:
          </div>
          <div style="width: 100%; display: flex; flex-direction: row;">
            <el-mention
              class="database-connection-input"
              :class="{ invalidFormat_databaseInput: invalidFormat_databaseInput }"
              v-model="DatabaseContext_raw"
              ref="DCr"
              :options="options"
              style="width: 100%;"
              placeholder="Database Connection Parms"
              type="textarea"
              :autosize="{ minRows: 1, maxRows: 10 }"
              :loading="loading"
              @search="handleSearch"
              @select="(option, prefix) => replaceMentioned(option, prefix, DCr)"
              @blur="(event) => translateIntoDict_databaseInput(event, DCr)"
            />
            <el-select v-model="forceType" placeholder="Force Reconnect" placement="bottom" popper-class="list-menu" style="width: 30%; max-width: 100px;">
              <el-option
                v-for="item in force_reconn_items"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
          </div>

          <div style="width: 100%; height: 32px; display: flex; justify-content: center; align-items: center; column-count: 1;">
            SQL语句:
          </div>
          <div style="width: 100%; display: flex; flex-direction: row;">
            <el-mention
              class="database-connection-input"
              v-model="SqlContext"
              ref="SC"
              :options="options"
              style="width: 100%;"
              placeholder="SQL"
              type="textarea"
              :autosize="{ minRows: 1, maxRows: 10 }"
              :loading="loading"
              @search="handleSearch"
              @select="(option, prefix) => replaceMentioned(option, prefix, DCr)"
            />
            <el-select v-model="forceType" placeholder="Force Reconnect" placement="bottom" popper-class="list-menu" style="width: 30%; max-width: 100px;">
              <el-option
                v-for="item in force_reconn_items"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
          </div>

          <div style="width: 100%; height: 32px; display: flex; justify-content: center; align-items: center; column-count: 1;">
            结果断言:
          </div>
          <div style="width: 100%; display: flex; flex-direction: row;">
            <el-mention
              class="assert-input"
              :class="{ invalidFormat_assertInput: invalidFormat_assertInput }"
              v-model="AssertContext_raw"
              ref="ACX"
              :options="options"
              style="width: 100%;"
              placeholder="Assert"
              type="textarea"
              :autosize="{ minRows: 1, maxRows: 10 }"
              :loading="loading"
              @search="handleSearch"
              @select="(option, prefix) => replaceMentioned(option, prefix, ACX)"
              @blur="(event) => translateIntoDict_assertInput(event, ACX)"
            />
            <div>
              <el-select v-model="AssertContextType" placeholder="Type" placement="bottom" popper-class="list-menu" style="width: 100px;">
                <el-option
                  v-for="item in assert_context_items"
                  :key="item.value"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </div>
          </div>

          <div style="width: 100%; height: 32px; display: flex; justify-content: center; align-items: center; column-count: 1;">
            提取变量:
          </div>
          <div style="width: 100%; display: flex; flex-direction: row;">
            <el-input-tag v-model="VarNameToExtract" clearable placeholder="Please input" />
            <div>
              <el-select placeholder="By" placement="bottom" popper-class="list-menu" style="width: 100px;">
                <el-option
                  key="JSON Path"
                  label="JSON Path"
                  value="JSON Path"
                />
              </el-select>
            </div>
          </div>



          <div></div>
          <div style="width: 100%; display: flex; flex-direction: row;">
            <div style="color: rgba(247, 104, 104, 0.764); max-height: 32px; min-height: 0; text-align: center;width: 100%; display: flex; flex-direction: row;gap: 3px;" v-if="invalidFormat_databaseInput || invalidFormat_assertInput">
              <div style="width: 24px; height: 24px;"><el-icon><Warning /></el-icon></div>
              <div>格式错误 : Invalid format</div>
            </div>
            <div style="color: rgba(0, 0, 0, 0.3); max-height: 32px; min-height: 0; text-align: center;width: 100%; display: flex; flex-direction: row;gap: 3px;" v-if="!invalidFormat_databaseInput && !invalidFormat_assertInput">
              <div style="width: 24px; height: 24px;"><el-icon><Warning /></el-icon></div>
              <div>数据格式 : key: value</div>
            </div>
          </div>

        </div>
      </div>
    </div>
  </div>
</template>


<script setup lang="ts">
type CardBase = {
  id: string
  title: string
  type: string
  level: string
}
type TabCardBase = CardBase & {
  uid: number
  showCardBody: boolean
  expanded: boolean
  btnType: string
  btnIcon: string
  prams: {}
  content: []
}

// ------------------------
// 参数列表
// ------------------------
const props = defineProps<{
  father_uid?: number
  self?: TabCardBase
  tab_key: string
}>()

// ------------------------
// 触发事件列表
// ------------------------
const emit = defineEmits<{
  (e: "update:delete-card", card_uid: number): void
}>()

import { nextTick, watch, ref } from 'vue'
import { useAppCacheData } from '../../../store/app'
import { InputDialog } from '../comp/inputDialog'
import { formatVarNameList, globalState, StringToDict } from '../../../store/globalData.js'
import PopMenu from './comp/PopMenu.vue'

const store = useAppCacheData()

const dbType_items = [
  {
    value: 'mysql',
    label: 'MySQL',
  },
  {
    value: 'postgres',
    label: 'PostgreSQL',
  },
  {
    value: 'sqlite',
    label: 'SQLite',
  },
  {
    value: 'sqlserver',
    label: 'SQL Server',
  },
  {
    value: 'oracle',
    label: 'Oracle',
  },
]

const force_reconn_items = [
  {
    value: true,
    label: 'forece reconnect',
  },
  {
    value: false,
    label: 'inherit connection',
  },
]

const assert_context_items = [
  {
    value: 'Default',
    label: 'Default',
  },
  {
    value: 'status',
    label: 'status',
  },
  {
    value: 'contains',
    label: 'contains',
  },
  {
    value: 'not_contains',
    label: 'not_contains',
  },
  {
    value: 'or_contains',
    label: 'or_contains',
  },
  {
    value: 'any_row_match',
    label: 'any_row_match',
  },
]

const loadAllVarName = () => {
  return [
    { label: 'No Suggestion', value: '' }
  ]
}
const options = ref<MentionOption[]>([])
const loading = ref(false)

const handleSearch = (_: string, prefix: string) => {
  loading.value = true
  options.value = formatVarNameList(store.getVarNameList(props.tab_key, props.self?.uid))
  loading.value = false
}


if (!props.self.prams) {
  props.self.prams = {}; // 确保是个字典
}
if (!props.self.prams.database_context_raw) {
  props.self.prams.database_context_raw = "";
}
if (!props.self.prams.sql_context) {
  props.self.prams.sql_context = "";
}
if (!props.self.prams.database_context) {
  props.self.prams.database_context = {};
}
if (!props.self.prams.force_type) {
  props.self.prams.force_type = false;
}
if (!props.self.prams.assert_context_raw) {
  props.self.prams.assert_context_raw = "";
}
if (!props.self.prams.assert_context) {
  props.self.prams.assert_context = {};
}
if (!props.self.prams.assert_context_type) {
  props.self.prams.assert_context_type = "";
}
if (!props.self.prams.extract) {
  props.self.prams.extract = [];
}
const forceType = ref(props.self.prams.force)
const DatabaseContext_raw = ref(props.self.prams.database_context_raw)
const DCr = ref<any>(null);
const DatabaseContext = ref(props.self.prams.database_context) 
const SqlContext = ref(props.self.prams.sql_context)
const SC = ref<any>(null);
const AssertContext_raw = ref(props.self.prams.assert_context_raw)
const ACX = ref<any>(null);
const AssertContext = ref(props.self.prams.assert_context)
const AssertContextType = ref(props.self.prams.assert_context_type)

const VarNameToExtract = ref<string[]>(props.self.prams.extract)

let invalidFormat_databaseInput = ref(false)
const mark_btn_right = ref(true)
let invalidFormat_assertInput = ref(false)

watch(forceType, (newVal) => {
  props.self.prams.force = newVal
  store.saveTab(props.tab_key)
})
watch(DatabaseContext_raw, (newVal) => {
  invalidFormat_databaseInput.value = false
  props.self.prams.database_context_raw = newVal
  // console.log("database: watch-DatabaseContext_raw: newVal: " + newVal)
  store.saveTab(props.tab_key)
})
watch(SqlContext, (newVal) => {
  props.self.prams.sql_context = newVal
  // console.log("database: watch-DatabaseContext_raw: newVal: " + newVal)
  store.saveTab(props.tab_key)
})
watch(AssertContext_raw, (newVal) => {
  invalidFormat_assertInput.value = false
  props.self.prams.assert_context_raw = newVal
  // console.log("database: watch-body_context_raw: newVal: " + newVal)
  store.saveTab(props.tab_key)
})
watch(AssertContextType, (newVal) => {
  props.self.prams.assert_context_type = newVal
  store.saveTab(props.tab_key)
})
watch(VarNameToExtract, (newVal) => {
  props.self.prams.extract = newVal
  store.saveTab(props.tab_key)
})

const replaceMentioned = (option: MentionOption, prefix: string, mentionComp?: any) => {
  // ⬇️ 在 nextTick 外先抓住 cursorPos
  let textarea: HTMLInputElement | HTMLTextAreaElement | null = null;
  if (mentionComp) {
    const root = (mentionComp as any).$el ?? mentionComp;
    textarea =
      root?.querySelector?.(".el-input__inner") ??
      (root?.classList?.contains?.("el-input__inner") ? root : null);

    if (!textarea) {
      textarea =
        root?.querySelector?.(".el-textarea__inner") ??
        (root?.classList?.contains?.("el-textarea__inner") ? root : null);
    }
  }
  let cursorPos = textarea?.selectionStart ?? text.length; // ✅ 提前保存 
  cursorPos = cursorPos + option.value.length

  nextTick(() => {
    if (!textarea) return;
    // console.log("database: replaceMentioned: cursorPos: " + cursorPos)
    const text = mentionComp?.$props?.modelValue ?? "";
    // console.log("database: replaceMentioned: text: " + text)
    const target = prefix + option.value;
    const beforeCursor = text.slice(0, cursorPos);
    const lastIndex = beforeCursor.lastIndexOf(target);
    if (lastIndex === -1) return;

    const newText =
      text.slice(0, lastIndex) +
      `<<${option.value}>>` +
      text.slice(lastIndex + target.length);

    mentionComp.$emit("update:modelValue", newText);

    const newCursor = lastIndex + option.value.length + 4;
    requestAnimationFrame(() => {
      textarea.selectionStart = textarea.selectionEnd = newCursor;
      textarea.focus();
    });
  });
};

const translateIntoDict_databaseInput = (event: FocusEvent, mentionComp?: any) => { 
  let textarea: HTMLTextAreaElement | null = null;

  if (mentionComp) {
    const root = (mentionComp as any).$el ?? mentionComp;
    textarea = root?.querySelector?.('.el-input__inner') ?? 
              (root?.classList?.contains?.('el-input__inner') ? root : null);
    if (!textarea) {
      textarea = root?.querySelector?.('.el-textarea__inner') ?? 
                (root?.classList?.contains?.('el-textarea__inner') ? root : null);
    }
  }

  if (!textarea) return;

  const text = mentionComp?.$props?.modelValue ?? "";
  const dict = StringToDict(text)

  if (dict && Object.keys(dict).length === 1 && "error" in dict) {
    console.error("translateIntoDict_databaseInput: error:", dict.error);
    invalidFormat_databaseInput.value = true
  } else {
    console.info("translateIntoDict_databaseInput: success-dict: "+JSON.stringify(dict));
    invalidFormat_databaseInput.value = false
    props.self.prams.database_context = dict
    // console.log("database: watch-DatabaseContext_raw: newVal: " + newVal)
    store.saveTab(props.tab_key)
  }

}

const translateIntoDict_assertInput = (event: FocusEvent, mentionComp?: any) => { 
  let textarea: HTMLTextAreaElement | null = null;

  if (mentionComp) {
    const root = (mentionComp as any).$el ?? mentionComp;
    textarea = root?.querySelector?.('.el-input__inner') ?? 
              (root?.classList?.contains?.('el-input__inner') ? root : null);
    if (!textarea) {
      textarea = root?.querySelector?.('.el-textarea__inner') ?? 
                (root?.classList?.contains?.('el-textarea__inner') ? root : null);
    }
  }

  if (!textarea) return;

  const text = mentionComp?.$props?.modelValue ?? "";

  if(AssertContextType.value === "status_code") {
    const n = Number(text);
    props.self.prams.assert_context = {
      status_code: isNaN(n) ? null : n
    };
    if(isNaN(n)) invalidFormat_assertInput.value = true
    store.saveTab(props.tab_key)
    return
  } else if(AssertContextType.value === "body_contains") {
    props.self.prams.assert_context = {
      body_contains: String(text)
    };
    store.saveTab(props.tab_key)
    return
  } else if(AssertContextType.value === "body_not_contains") {
    props.self.prams.assert_context = {
      body_not_contains: String(text)
    };
    store.saveTab(props.tab_key)
    return
  } else if(AssertContextType.value === "response_time_max") {
    const n = Number(text);
    props.self.prams.assert_context = {
      response_time_max: isNaN(n) ? null : n
    };
    if(isNaN(n)) invalidFormat_assertInput.value = true
    store.saveTab(props.tab_key)
    return
  }

  const dict = StringToDict(text)

  if (dict && Object.keys(dict).length === 1 && "error" in dict) {
    console.error("translateIntoDict_databaseInput: error:", dict.error);
    invalidFormat_assertInput.value = true
  } else {
    console.info("translateIntoDict_databaseInput: success-dict: "+JSON.stringify(dict));
    invalidFormat_assertInput.value = false
    props.self.prams.assert_context = dict
    // console.log("database: watch-DatabaseContext_raw: newVal: " + newVal)
    store.saveTab(props.tab_key)
  }

}

// ------------------------
// 右侧标签页里卡片的拖拽逻辑
// ------------------------
function onTabCardDragStart(event: DragEvent) {
  globalState.draggedStartCardUid_parent = props.father_uid
  globalState.draggedStartCardUid = props.self?.uid
  globalState.draggedCard = ""
  globalState.draggedTabCard = ""
  globalState.draggedTabCard = JSON.stringify(props.self)
}

// ------------------------
// 显示弹出菜单
// ------------------------
let isShowMenu = ref(false)
let menuStyle = ref({})
let menuBtnRef = ref(null)

function showPopMenu() {
  isShowMenu.value = !isShowMenu.value
  console.log("Note: showPopMenu: isShowMenu = " + isShowMenu.value)

  if (isShowMenu.value && menuBtnRef.value) {
    const rect = menuBtnRef.value.$el.getBoundingClientRect()
    const menuWidth = 144 // 你自己设定的菜单宽度
    console.log("Note: showPopMenu: rect = "+rect.left+" "+rect.top)

    const btnRect = menuBtnRef.value.$el.getBoundingClientRect()
    const parentRect = menuBtnRef.value.$el.offsetParent.getBoundingClientRect()

    // 相对父容器的坐标
    const relativeTop = btnRect.top - parentRect.top
    const relativeLeft = btnRect.left - parentRect.left

    menuStyle.value = {
      position: 'absolute',
      top: '10px',
      left: relativeLeft-menuWidth+'px',
    }
  }
}

function closePopMenu() {
  isShowMenu.value = false
  console.log("Note: closePopMenu")
}

// ------------------------
// 弹出菜单里的操作
// ------------------------
if (!props.self.prams.markIsShow) {
  props.self.prams.markIsShow = false;
}
const isShowMark = ref(props.self.prams.markIsShow)
const isShowMark_ = ref(true)

if (!props.self.prams.markMessage) {
  props.self.prams.markMessage = "已标记";
}
const markMessage = ref(props.self.prams.markMessage)

function saveCardAsPredefined() {
  
}

function markCard() {
  isShowMark.value = !isShowMark.value
  props.self.prams.markIsShow = isShowMark.value
  store.saveTab(props.tab_key)
}

function hideMark() {
  isShowMark.value = false
  props.self.prams.markIsShow = isShowMark.value
  store.saveTab(props.tab_key)
  setTimeout(() => {
    isShowMark_.value = false
  }, 200)
  setTimeout(() => {
    isShowMark_.value = true
  }, 220)
}

async function updateMarkContent() {
  try {
    InputDialog.open('请输入文本', '编辑 Mark 内容', {
      placeholder: markMessage.value,
      defaultValue: markMessage.value,
    }).then(value => {
      markMessage.value = value
      props.self.prams.markMessage = markMessage.value
      isShowMark.value = true
      props.self.prams.markIsShow = isShowMark.value
      store.saveTab(props.tab_key)
    }).catch(() => {
    })
  } catch {}
}

// ------------------------
// 删除右侧卡片
// ------------------------
async function removeThisCard() {
  emit("update:delete-card", props.self?.uid)
}

// ------------------------
// 编辑右侧卡片
// ------------------------
function editTabCard() {
  if (props.self.showCardBody) {
    props.self.btnType = "primary"
    props.self.btnIcon = "Postcard"
  } else {
    props.self.btnType = "success"
    props.self.btnIcon = "Check"
  }
  props.self.expanded = !props.self.expanded
  props.self.showCardBody = !props.self.showCardBody
  store.saveTab(props.tab_key)
}

// ------------------------
// 页面布局控制
// ------------------------
const titleInput = ref(props.self.title)

function onMouseUp_input(e: Event) {
  const el = e.target as HTMLInputElement
  const cursorPos = el.selectionStart   // 光标起始位置
  const cursorEnd = el.selectionEnd     // 光标结束位置
  // console.log("光标位置:", cursorPos, cursorEnd)
  el.setSelectionRange(cursorEnd, cursorEnd)
}

function onTabCardTitleChange(e: Event) {
  if (props.self) {
    props.self.title = titleInput.value
    store.saveTab(props.tab_key)
  }
  (e.target as HTMLInputElement).blur()
}

</script>


<style scoped>
.no-drag {
  -webkit-app-region: no-drag; 
}

input, textarea {
  user-select: none;
}

.database-body-wrapper {
  min-height: 60px;
}

.database-content {
  /* min-height: 100%; */
  position: relative;
  border-radius: 8px;
  background: transparent;
  flex-wrap: wrap;
  margin-right: 5px;
  overflow: auto;         /* 保持可滚动 */
  scrollbar-width: none;  /* 隐藏滚动条 */
  padding: 8px 12px;
}


/* 开启动画 */
.scale-fade-enter-active {
  animation: scaleFadeIn .25s cubic-bezier(0.22, 1, 0.36, 1); /* 弹性进入 */
}

.scale-fade-leave-active {
  animation: scaleFadeOut .2s cubic-bezier(0.4, 0, 0.2, 1);   /* 柔和离开 */
}

@keyframes scaleFadeIn {
  0% {
    opacity: 0;
    transform: scale(0.9) translateY(6px);
  }
  60% {
    opacity: 1;
    transform: scale(1.03) translateY(0); /* 稍微放大一点 */
  }
  100% {
    opacity: 1;
    transform: scale(1);
  }
}

@keyframes scaleFadeOut {
  0% {
    opacity: 1;
    transform: scale(1);
  }
  100% {
    opacity: 0;
    transform: scale(0.95) translateY(6px); /* 离场下沉一点 */
  }
}

:deep(.database-connection-input.invalidFormat_databaseInput) {
  --el-input-text-color: rgba(247, 104, 104, 0.764);
}

:deep(.assert-input.invalidFormat_assertInput) {
  --el-input-text-color: rgba(247, 104, 104, 0.764);
}
</style>
