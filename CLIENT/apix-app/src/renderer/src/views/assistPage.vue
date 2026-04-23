<template>
  <el-container>
    <el-aside style="width: var(--apix-left-side-bar-width); transition: width 0.28s cubic-bezier(0.23, 1, 0.32, 1);">
      <HomePage />
    </el-aside>

    <keep-alive>
    <el-main class="main-area">
      <div class="ai-page-wrapper" :class="{ 'is-history-hide': isHistoryHide }">
        <ChatHistoryPannel
          style="margin-left: 6%;"
          :histories="historyList"
          :active-id="store.current_history_id"
          class="ai-history-pannel"
          :class="{ 'is-history-hide': isHistoryHide }"
          @select="handleSelectHistory"
          @create="handleCreateChat"
          @delete="handleDeleteHistory"
          @hide="handleHideHistory"
        />
        <div class="chat-wrapper">
          <div 
            class="work-dir-label" 
            :class="{no_work_dir: show_work_dir===''}"
            @click="handleConnectProject"
          >
            {{ show_work_dir===''?'未指定工作目录，继续处理文件相关工作时请先关联项目':show_work_dir }}
          </div>
          <div class="message-list">
            <div
              v-for="msg in messages"
              :key="msg.id"
              class="message-item"
              :class="msg.role"
            >
              <HumanMessageBubble 
                v-if="msg.role === 'human'" 
                :msg="msg" 
                :is_selecting="selectMode"
                @edit=""
                @edit-finish="handleEditFinish"
                @select-text="handleSelectText"
                @selected="selectMessageBubble"
                @delete="selectMessageBubble"
              />
              <AiMessageBubble 
                v-else-if="msg.role === 'ai'" 
                :msg="msg" 
                :is_selecting="selectMode"
                @re-generate="handleRegenerate"
                @select-text="handleSelectText"
                @selected="selectMessageBubble"
                @delete="selectMessageBubble"
                @quoted="handleQuoteShow"
              />
              <ToolMessageCard v-else-if="msg.role === 'tools' || msg.role === 'system'" :msg="msg" />
            </div>

            <div key="buttom-div" class="buttom-div"></div>
          </div>

          <div 
            class="ctrl-area"
            :class="{ empty_messages_list: messages.length === 0 }"
            v-if="!selectMode"
          >
            <div style="display: block; align-items: center;">
              <div
                v-if="messages.length === 0"
                class="hello-div"
              >
                <div style="white-space: nowrap; width: fit-content;">
                  <span class="typewriter" style="display: inline-block; width: fit-content;">{{ displayText }}</span>
                  <span class="cursor" :style="{display: 'inline-block', width: '16px', opacity: showCursor?'1':'0'}">_</span>
                </div>
              </div>
            </div>

            <Transition name="fade">
              <div class="stop-btn-wrapper" v-if="isGenerating">
                <el-button
                  class="stop-generate-button"
                  @click="stopGenerating"
                >
                  <div class="wave-container">
                    <svg t="1769702765976" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg " p-id="9117" width="32" height="32"><path d="M243.611344 62.597687l535.403013 0c98.565876 0 178.464601 80.265068 178.464601 179.283246l0 537.849738c0 99.008968-79.898725 179.283246-178.464601 179.283246L243.611344 959.013917c-98.556667 0-178.455391-80.274278-178.455391-179.283246l0-537.849738C65.155952 142.862755 145.054677 62.597687 243.611344 62.597687z" p-id="9118"></path></svg>
                    <div class="wave wave-1"></div>
                    <div class="wave wave-2"></div>
                    <div class="wave wave-3"></div>
                  </div>
                  <div>{{ stream_state_text }}</div>
                </el-button>
              </div>
            </Transition>

            <Transition name="fade">
              <div v-if="isWarningShow" class="warning-label">
                <div style="display: flex; gap: 3px; align-items: center;">
                  <svg t="1776752724390" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="1671" width="20" height="20"><path d="M558 563c0 24.852-20.148 45-45 45S468 587.852 468 563v-150c0-24.852 20.148-45 45-45s45 20.148 45 45v150z m0 132c0 24.852-20.148 45-45 45S468 719.852 468 695v-1c0-24.852 20.148-45 45-45S558 669.148 558 694v1z m-355.006 65.804a15 15 0 0 0 14.986 15.014l589.36 0.55a15 15 0 0 0 12.916-22.646L525.56 256.376a15 15 0 0 0-25.806-0.006l-294.66 496.796a15 15 0 0 0-2.098 7.638z m-75.31-53.552l294.66-496.794c29.584-49.878 93.998-66.328 143.874-36.746a105 105 0 0 1 36.768 36.784l294.7 497.346c29.56 49.89 13.08 114.298-36.808 143.86a105 105 0 0 1-53.624 14.666l-589.358-0.55c-57.99-0.054-104.956-47.108-104.9-105.1a105 105 0 0 1 14.688-53.466z" fill="#856404" p-id="1672"></path></svg>
                  <span class="warning-content">{{ WarningContent }}</span>
                </div>
                <button class="warning-close" @click="handleWarningClose">
                  <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
                    <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
                  </svg>
                </button>
              </div>
            </Transition>

            <Transition name="fade">
              <div v-if="isQuoteShow && quotedText !== ''" class="quote-label">
                <div style="display: flex; gap: 3px; align-items: center;">
                  <svg t="1776857880346" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="1651" width="20" height="20"><path d="M460.8 460.361143c54.418286 0 99.84-36.425143 99.84-94.281143 0-54.857143-37.284571-90.88-88.283429-90.88-26.148571 0-46.281143 10.294857-58.697142 30.006857 13.275429-60.854857 59.117714-101.12 121.270857-103.698286 16.713143-0.859429 28.708571-12.434286 28.708571-28.708571 0-19.730286-15.853714-30.006857-37.284571-30.006857-96.420571 0-182.125714 82.285714-182.125715 190.72 0 77.129143 51.419429 126.848 116.553143 126.848z m-262.308571 0c54.436571 0 99.858286-36.425143 99.858285-94.281143 0-54.857143-37.705143-90.88-88.704-90.88-25.709714 0-46.281143 10.294857-58.715428 30.006857 13.275429-60.854857 59.574857-100.699429 121.709714-103.698286 16.274286-0.859429 28.708571-12.434286 28.708571-28.708571 0-19.730286-16.274286-30.006857-37.705142-30.006857-96.420571 0-182.144 82.285714-182.144 190.72 0 77.129143 51.858286 126.848 116.992 126.848zM669.074286 207.908571h241.700571c18.432 0 33.005714-14.134857 33.005714-32.566857 0-18.011429-14.573714-32.146286-32.987428-32.146285h-241.737143a31.817143 31.817143 0 0 0-32.128 32.146285c0 18.432 14.134857 32.566857 32.146286 32.566857z m0 224.566858h241.700571c18.432 0 33.005714-14.134857 33.005714-32.548572 0-18.011429-14.573714-32.164571-32.987428-32.164571h-241.737143a31.817143 31.817143 0 0 0-32.128 32.146285c0 18.432 14.134857 32.566857 32.146286 32.566858zM112.786286 657.078857h797.988571a32.658286 32.658286 0 0 0 33.005714-32.585143c0-17.993143-14.573714-32.146286-32.987428-32.146285H112.786286c-18.432 0-32.566857 14.153143-32.566857 32.146285 0 18.011429 14.134857 32.585143 32.548571 32.585143z m0 224.128h797.988571c18.432 0 33.005714-14.134857 33.005714-32.128 0-18.011429-14.573714-32.585143-32.987428-32.585143H112.786286a32.292571 32.292571 0 0 0-32.566857 32.585143c0 17.993143 14.134857 32.128 32.548571 32.128z" p-id="1652"></path></svg>
                  <span class="quote-content">{{ quotedText }}</span>
                </div>
                <button class="quote-close" @click="handleQuoteClose">
                  <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
                    <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
                  </svg>
                </button>
              </div>
            </Transition>

            <div class="input-bar">
              <el-input
                v-model="inputText"
                type="textarea"
                placeholder="Inputs..."
                @keydown="msgInputHandleKeydown"
                :autosize="{ minRows: 1, maxRows: fullInput?20:9 }"
                class="chat-input"
                style="display: flex; align-items: center;"
                resize="none"
              />

              <el-button
                class="input-full-screen-button"
                @click="setFullInput"
              >
                <svg t="1768828244015" class="icon" :class="{ isFullInput: fullInput }" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="4761" width="200" height="200"><path d="M776.533333 896h-113.066666c-23.466667 0-42.666667-19.2-42.666667-42.666667s19.2-42.666667 42.666667-42.666666h113.066666c19.2 0 34.133333-14.933333 34.133334-34.133334v-113.066666c0-23.466667 19.2-42.666667 42.666666-42.666667s42.666667 19.2 42.666667 42.666667v113.066666c0 66.133333-53.333333 119.466667-119.466667 119.466667z m-416 0h-113.066666C181.333333 896 128 842.666667 128 776.533333v-113.066666c0-23.466667 19.2-42.666667 42.666667-42.666667s42.666667 19.2 42.666666 42.666667v113.066666c0 19.2 14.933333 34.133333 34.133334 34.133334h113.066666c23.466667 0 42.666667 19.2 42.666667 42.666666s-19.2 42.666667-42.666667 42.666667zM853.333333 403.2c-23.466667 0-42.666667-19.2-42.666666-42.666667v-113.066666c0-19.2-14.933333-34.133333-34.133334-34.133334h-113.066666c-23.466667 0-42.666667-19.2-42.666667-42.666666s19.2-42.666667 42.666667-42.666667h113.066666c66.133333 0 119.466667 53.333333 119.466667 119.466667v113.066666c0 23.466667-19.2 42.666667-42.666667 42.666667z m-682.666666 0c-23.466667 0-42.666667-19.2-42.666667-42.666667v-113.066666C128 181.333333 181.333333 128 247.466667 128h113.066666c23.466667 0 42.666667 19.2 42.666667 42.666667s-19.2 42.666667-42.666667 42.666666h-113.066666c-19.2 0-34.133333 14.933333-34.133334 34.133334v113.066666c0 23.466667-19.2 42.666667-42.666666 42.666667z" p-id="4762"></path></svg>
              </el-button>
              
              <div class="chat-config">
                <n-select
                  v-model:value="store.config.modelProvider"
                  :options="modelPoviderOptions"
                  class="model-provider"
                  :render-label="renderLabel"
                  :render-tag="renderSingleSelectTag"
                  :show-arrow="false"
                  :consistent-menu-width="false"
                />

                <el-button
                  class="apikey-button"
                  :class="{ errorKey: !store.config.apiKey }"
                  @click="editApiKey"
                >
                  <svg t="1773422089722" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="16943" width="200" height="200"><path d="M682.666667 256a256 256 0 1 1-216.490667 392.704L460.928 640H230.997333a42.666667 42.666667 0 0 1-25.941333-8.789333l-4.224-3.712-85.333333-85.333334a42.666667 42.666667 0 0 1-3.541334-56.32l3.541334-4.010666 85.290666-85.333334a42.666667 42.666667 0 0 1 24.576-12.117333L230.954667 384h229.973333A255.914667 255.914667 0 0 1 682.666667 256z m0 64a191.914667 191.914667 0 0 0-166.357334 96.042667 64 64 0 0 1-55.381333 31.957333H239.786667L175.829333 512l64 64h221.098667a64 64 0 0 1 55.381333 31.957333A192 192 0 1 0 682.666667 320z" :fill="store.config.apiKey?'#6f6f6f':'#f3555583'" p-id="16944"></path><path d="M682.666667 426.666667a85.333333 85.333333 0 1 1 0 170.666666 85.333333 85.333333 0 0 1 0-170.666666z m0 64a21.333333 21.333333 0 1 0 0 42.666666 21.333333 21.333333 0 0 0 0-42.666666z" :fill="store.config.apiKey?'#7c7c7c':'#f3555573'" p-id="16945"></path></svg>
                </el-button>

                <n-select
                  v-model:value="store.config.modelName"
                  :options="modelSelectOptions"
                  class="model-select"
                  :class="{ errorServer: errorServer }"
                  :consistent-menu-width="false"
                  :show-arrow="false"
                />

                <el-button
                  class="thinking-button"
                  :class="{ yes: store.config.deepThink }"
                  @click="setDeepThink"
                >
                  <svg t="1768788522926" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="9133" width="200" height="200"><path d="M882.176 882.176c-53.8368 53.8368-136.832 59.3408-249.0368 16.4864A705.1008 705.1008 0 0 1 512 837.9136a705.1008 705.1008 0 0 1-121.1392 60.7744c-112.1792 42.8288-195.2 37.3248-249.0112-16.512-53.8368-53.8112-59.3408-136.832-16.512-249.0112A705.1008 705.1008 0 0 1 186.112 512a705.1264 705.1264 0 0 1-60.7744-121.1904c-42.8288-112.1792-37.3248-195.2 16.4864-249.0368 53.8368-53.8112 136.8576-59.3152 249.0368-16.4864A705.1264 705.1264 0 0 1 512 186.112a705.1264 705.1264 0 0 1 121.1648-60.7488c112.1792-42.8544 195.1744-37.3504 249.0112 16.4864 53.8368 53.8368 59.3408 136.832 16.4864 249.0112a705.152 705.152 0 0 1-60.7744 121.1904 705.1264 705.1264 0 0 1 60.7488 121.1392c42.8288 112.1792 37.3504 195.1744-16.4864 249.0112zM194.304 194.304c-31.1552 31.1552-31.0272 87.8336 0.3584 170.0608 10.2656 26.88 22.8864 53.6832 37.888 80.4608a1115.8784 1115.8784 0 0 1 99.3536-112.9472 1115.904 1115.904 0 0 1 112.896-99.328 609.1776 609.1776 0 0 0-80.4608-37.888c-82.2016-31.3856-138.88-31.488-170.0352-0.3584z m635.392 0c-31.1296-31.1296-87.808-31.0272-170.0352 0.384-26.88 10.24-53.6832 22.8864-80.4608 37.888a1115.904 1115.904 0 0 1 112.896 99.328 1115.8784 1115.8784 0 0 1 99.3536 112.896 609.1776 609.1776 0 0 0 37.888-80.4352c31.3856-82.2272 31.5136-138.9056 0.384-170.0608z m-445.2864 190.08c-42.4448 42.4448-78.8224 84.992-109.1328 127.6416 30.3104 42.6496 66.688 85.1712 109.1072 127.5904 42.4192 42.4448 84.992 78.8224 127.616 109.1328 42.6752-30.3104 85.1968-66.688 127.6416-109.1328 42.4192-42.4192 78.7968-84.9408 109.1072-127.5904-30.336-42.6752-66.7136-85.2224-109.1328-127.6416-42.4192-42.4192-84.9664-78.7968-127.616-109.1072-42.624 30.3104-85.1712 66.688-127.5904 109.1072zM435.2 512a76.8 76.8 0 1 1 153.6 0 76.8 76.8 0 0 1-153.6 0z m-202.624 67.2256a609.1776 609.1776 0 0 0-37.888 80.4096c-31.3856 82.2272-31.488 138.9056-0.3584 170.0608 31.1552 31.1552 87.8336 31.0272 170.0608-0.3584 26.8544-10.2656 53.6576-22.8864 80.4096-37.888a1115.8784 1115.8784 0 0 1-112.9216-99.328 1115.9552 1115.9552 0 0 1-99.328-112.896z m597.0944 250.4704c31.1552-31.1552 31.0272-87.8336-0.3584-170.0608a609.1776 609.1776 0 0 0-37.888-80.4096 1115.9296 1115.9296 0 0 1-99.2768 112.896 1115.8784 1115.8784 0 0 1-112.9216 99.328 609.1264 609.1264 0 0 0 80.384 37.888c82.2528 31.36 138.9312 31.488 170.0608 0.3584z" :fill="store.config.deepThink?'#ffffff':'#6c6c6c'" p-id="9134"></path></svg>
                  深度思考
                </el-button>

                <el-button 
                  class="select-button" 
                  :class="{ yes: selectedFiles.length>0, no_error: upload_no_error }" 
                  @click="selectFile"
                  :disabled="isUploading"
                >
                <svg t="1768876989120" class="icon" v-if="!isUploading" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="2174" width="200" height="200"><path d="M796.8 902.4H240.64c-64.64 0-117.12-52.48-117.12-117.12V406.4c0-14.08 1.92-27.52 6.4-40.96L161.28 262.4c13.44-44.16 53.76-73.6 99.84-73.6h219.52c46.08 0 86.4 29.44 99.84 73.6 5.12 16.64-4.48 34.56-21.12 39.68-16.64 5.12-34.56-4.48-39.68-21.12-5.12-17.28-20.48-28.8-38.4-28.8H261.12c-17.92 0-33.28 11.52-38.4 28.8l-32 103.04c-1.92 7.04-3.2 14.72-3.2 21.76v378.88c0 29.44 23.68 53.12 53.12 53.12h556.16c29.44 0 53.12-23.68 53.12-53.12V475.52c0-29.44-23.68-53.12-53.12-53.12h-262.4c-17.92 0-32-14.08-32-32s14.08-32 32-32h262.4c64.64 0 117.12 52.48 117.12 117.12v309.76c0 64-52.48 117.12-117.12 117.12z" :fill="selectedFiles.length>0?'#ffffff':'#6c6c6c'" p-id="2175"></path></svg>
                <div v-else class="loading"></div>
                上传文件
                </el-button>

                <div class="file-path-scroll">
                  <div class="file-path-tag-wrapper">
                    <el-tag
                      v-for="tag in selectedFiles"
                      :key="tag.path"
                      :closable="true"
                      :type="tag.type"
                      class="file-tag"
                      @close="handlePathTagClose(tag)"
                    >
                      {{ tag.name }}
                    </el-tag>
                  </div>
                </div>

              </div>
              <el-button class="send-button" type="primary" @click="handleSendMessage">
                <svg t="1776519512558" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="11362" width="26" height="26"><path d="M481.834667 183.168a42.666667 42.666667 0 0 1 60.330666 0l298.666667 298.666667a42.666667 42.666667 0 0 1-60.330667 60.330666L554.666667 316.330667V810.666667a42.666667 42.666667 0 1 1-85.333334 0V316.330667l-225.834666 225.834666a42.666667 42.666667 0 0 1-60.330667-60.330666l298.666667-298.666667z" fill="#ffffff" p-id="11363"></path></svg>
              </el-button>
            </div>
          </div>
          <div
            class="ctrl-btns-area"
            v-if="selectMode"
          >
            <div class="cd-actions">
              <button
                class="cancel-btn"
                @click="handleCancel"
              >
                取消
              </button>

              <button
                class="delete-btn"
                @click="handleDeleteMessages"
              >
                删除
              </button>
            </div>
          </div>

        </div>
      </div>
    </el-main>
    </keep-alive>
  </el-container>
</template>

<script setup lang="ts">
import { ref, nextTick, reactive, watch, onMounted, onBeforeUnmount, h, computed, toRaw } from 'vue'
import type { TagProps } from 'element-plus'
import HomePage from './homePage.vue'
import HumanMessageBubble from './component/msg_bubble_body/human_message_bubble.vue'
import AiMessageBubble from './component/msg_bubble_body/ai_message_bubble.vue'
import ToolMessageCard from './component/msg_bubble_body/tool_message_card.vue'
import ChatHistoryPannel from './component/dialog_history/history_pannel.vue'
import { type ChatHistory } from './component/dialog_history/history_card.vue'
import { useAppCacheData } from '../store/app'
import { useAuthStore } from '../store/auth'
import { ElMessage } from 'element-plus'
import { NAvatar, NSelect } from 'naive-ui'
import { InputDialog } from './component/comp/inputDialog'
import { ConfirmDialog } from './component/comp/confirmDialog.js'
import { mdDisplayer } from './component/comp/mdDisplayer.js'
import { globalSelection } from '../store/globalData.js'
import ollamaIcon from '../assets/icons/llm_providers/ollama.svg'
import googleIcon from '../assets/icons/llm_providers/google.svg'
import openaiIcon from '../assets/icons/llm_providers/openai.svg'
import deepseekIcon from '../assets/icons/llm_providers/deepseek.svg'
import moonshotIcon from '../assets/icons/llm_providers/moonshot.svg'
import qwenIcon from '../assets/icons/llm_providers/qwen.svg'

const authStore = useAuthStore()
const store = useAppCacheData()

let unsubscribeWs: null | (() => void) = null

const cid = ref('')
const sid = ref('')
const inputText = ref('')

// ################################
// Types
// ################################
type Role = 'human' | 'ai' | 'system' | 'tools' | 'info'

interface ToolLabel {
  tool_call_id: string
  tool_name: string
  content: string
  status: 'pending' | 'in_progress' | 'completed' | 'error' | 'outdated'
}

type MessageChunk = string | ToolLabel

interface ChatMessage {
  id: string
  cid: string
  hid: string
  role: Role
  node_id?: number
  parent_id?: number

  content?: string | MessageChunk[]
  think?: string | MessageChunk[]
  lastField?: 'think' | 'content'

  label?: string
  info?: any
  extra?: any
  todos?: any[]
  images?: any[]
  pending?: boolean
  error?: boolean
  errors?: any
  desc?: string | null
  status?: string | null

  selected?: boolean
}

interface GeneratingState {
  isGenerating: boolean
  streamStateText: string
}

interface TagsItem {
  name: string
  path: string
  id?: string
  type?: TagProps['type']
}

// ################################
// Chunk helpers
// ################################
function ensureArrayField(msg: ChatMessage, field: 'content' | 'think') {
  if (!Array.isArray(msg[field])) {
    if (!msg[field]) {
      msg[field] = []
    } else {
      msg[field] = [msg[field] as string]
    }
  }
}

// Append string chunk and merge with the last string when possible.
function appendChunk(
  msg: ChatMessage,
  field: 'content' | 'think',
  delta: string,
  guardId?: string
) {
  if (!delta) return
  if (guardId && msg.id !== guardId) return

  ensureArrayField(msg, field)

  const arr = msg[field] as MessageChunk[]
  const last = arr[arr.length - 1]

  if (typeof last === 'string') {
    arr[arr.length - 1] = last + delta
  } else {
    arr.push(delta)
  }
}

// Append or update tool label chunk.
function appendToolLabel(
  msg: ChatMessage,
  field: 'content' | 'think',
  label: ToolLabel,
  guardId?: string
) {
  if (guardId && msg.id !== guardId) return

  ensureArrayField(msg, field)

  const arr = msg[field] as MessageChunk[]

  if (label.tool_call_id) {
    const index = arr.findIndex(
      (item: any) => item?.tool_call_id === label.tool_call_id
    )

    if (index !== -1) {
      const old = arr[index] as ToolLabel
      arr[index] = {
        ...old,
        ...label,
        tool_name: label.tool_name || old.tool_name,
        content:  old.content + '\n\n' + label.content,
      }
      return
    }
  }

  arr.push(label)
}

function cloneMaybeArray<T>(value: T[] | undefined | null): T[] {
  return Array.isArray(value) ? [...value] : []
}

function pickToolTargetField(r: any): 'content' | 'think' {
  if (r?.lastField === 'think' || r?.last_field === 'think') return 'think'
  if (r?.lastField === 'content' || r?.last_field === 'content') return 'content'

  const hasThink = !!r?.think && String(r.think).length > 0
  const hasContent = !!r?.content && String(r.content).length > 0

  if (hasThink && !hasContent) return 'think'
  if (hasContent && !hasThink) return 'content'

  return 'think'
}

function appendToolCallsFromExtra(
  msg: ChatMessage,
  extra: any,
  r: any
) {
  const toolCalls = extra?.tool_calls
  if (!Array.isArray(toolCalls) || toolCalls.length === 0) return

  const targetField = pickToolTargetField(r)

  for (const call of toolCalls) {
    const label: ToolLabel = {
      tool_call_id: call.id,
      tool_name: call.name ?? 'unknown_tool',
      content: '已过期',
      status: 'outdated',
    }

    appendToolLabel(msg, targetField, label)
  }
}

// ################################
// Message cache by history
// ################################
const messageCache = reactive<Record<string, ChatMessage[]>>({})
const loadedHistorySet = reactive(new Set<string>())
const loadingHistorySet = reactive(new Set<string>())

function ensureHistoryMessages(hid: string): ChatMessage[] {
  if (!hid || hid === '-1') return []
  if (!messageCache[hid]) {
    messageCache[hid] = reactive([]) as ChatMessage[]
  }
  return messageCache[hid]
}

const messages = computed<ChatMessage[]>(() => {
  const hid = store.current_history_id
  if (!hid || hid === '-1') return []
  return ensureHistoryMessages(hid)
})

// ################################
// Generating state by history
// ################################
const generatingState = reactive<Record<string, GeneratingState>>({})

function ensureGeneratingState(hid: string): GeneratingState {
  if (!hid || hid === '-1') {
    return { isGenerating: false, streamStateText: '' }
  }
  if (!generatingState[hid]) {
    generatingState[hid] = reactive({
      isGenerating: false,
      streamStateText: '',
    }) as GeneratingState
  }
  return generatingState[hid]
}

const isGenerating = computed(() => {
  const hid = store.current_history_id
  if (!hid || hid === '-1') return false
  return ensureGeneratingState(hid).isGenerating
})

const stream_state_text = computed(() => {
  const hid = store.current_history_id
  if (!hid || hid === '-1') return ''
  return ensureGeneratingState(hid).streamStateText
})

// ################################
// Chat history
// ################################
const historyList = ref<ChatHistory[]>([])

async function get_conversation_list(cidValue: string) {
  const res = await window.api.getChatlist(cidValue)
  const raw_list = res.messages
  const chat_list: ChatHistory[] = []

  for (const raw_chat of raw_list) {
    const format_date = formatTime(raw_chat.last_active_at)
    chat_list.push({
      id: String(raw_chat.conversation_uid),
      preview: raw_chat.title,
      time: format_date.time,
      date: format_date.label,
      tokens: raw_chat.latest_cursor,
      star: raw_chat.is_pinned,
      createTime: raw_chat.create_at,
    })
  }
  return chat_list
}

function findLatestIndexById(list: ChatMessage[], id: string, role: Role) {
  for (let i = list.length - 1; i >= 0; i--) {
    if (list[i].id === id && list[i].role === role) {
      return i
    }
    // if (list[i].role === 'human') {
    //   break
    // }
  }
  return -1
}

function findLatestIndexByStatus(list: ChatMessage[], status: boolean, role: Role) {
  for (let i = list.length - 1; i >= 0; i--) {
    if (list[i].pending === status && list[i].role === role) {
      return i
    }
  }
  return -1
}

function mergeHistoryAiMessage(
  msg: ChatMessage,
  r: any,
  extra: any,
  info: any
) {
  appendChunk(msg, 'content', r.content ?? '')
  appendChunk(msg, 'think', r.think ?? '')

  const prevInfo = msg.info ?? {}
  msg.info = {
    ...prevInfo,
    ...info,
    total_tokens: (prevInfo.total_tokens ?? 0) + (info.total_tokens ?? 0),
    total_duration: info.total_duration/1000,
  }

  const prevExtra = msg.extra ?? {}
  const nextExtra = {
    ...prevExtra,
    ...extra,
    key_word: [prevExtra.key_word, extra.key_word].filter(Boolean).join('\n'),
    link_provider: prevExtra.link_provider ?? extra.link_provider,
    content_provider: prevExtra.content_provider ?? extra.content_provider,
    urls: [...(prevExtra.urls ?? []), ...(extra.urls ?? [])],
    tool_calls: extra?.tool_calls ?? prevExtra.tool_calls,
  }

  msg.extra = nextExtra

  appendToolCallsFromExtra(msg, extra, r)

  if ((nextExtra.todo_list?.length ?? 0) > 0) {
    msg.todos = cloneMaybeArray(nextExtra.todo_list)
  }

  if ((nextExtra.image_meta?.length ?? 0) > 0) {
    msg.images = cloneMaybeArray(nextExtra.image_meta)
  }

  msg.pending = false
  msg.lastField = r.think ? 'think' : 'content'
}

function parseHistoryMessages(raw: any[], hid: string): ChatMessage[] {
  const list: ChatMessage[] = []
  const aiIndexByGeneration = new Map<string, number>()
  const systemIndexByTask = new Map<string, number>()

  for (const r of raw) {
    const extra = r.extra ?? {}
    const info = r.info ?? {}

    if (r.role === 'system' || r.role === 'tools') {
      const taskId = String(info?.task_id ?? r.generation_id ?? genUUID())
      const existingIndex = systemIndexByTask.get(taskId)

      if (existingIndex !== undefined) {
        const existing = list[existingIndex]
        existing.content = info?.tool_name ?? existing.content ?? 'Unnamed task'
        existing.desc = info?.desc ?? existing.desc ?? null
        existing.status = info?.status ?? existing.status ?? null
        existing.pending = false
      } else {
        const msg: ChatMessage = {
          id: taskId,
          cid: cid.value,
          hid,
          role: r.role,
          content: info?.tool_name ?? 'Unnamed task',
          desc: info?.desc ?? null,
          status: info?.status ?? null,
          pending: false,
        }
        list.push(msg)
        systemIndexByTask.set(taskId, list.length - 1)
      }
      continue
    }

    if (r.role === 'human') {
      const generationId = String(r.generation_id ?? genUUID())
      list.push({
        id: generationId,
        cid: cid.value,
        hid,
        role: 'human',
        node_id: r.node_id,
        parent_id: r.parent_id,
        content: r.content ?? '',
        extra,
        error: false,
        pending: false,
      })

      aiIndexByGeneration.clear()
      continue
    }

    if (r.role === 'ai' || r.role === 'info') {
      const generationId = String(r.generation_id ?? genUUID())
      const index = aiIndexByGeneration.get(generationId)

      if (index === undefined) {
        const newMsg: ChatMessage = {
          id: generationId,
          cid: cid.value,
          hid,
          role: 'ai',
          node_id: r.node_id,
          parent_id: r.parent_id,
          label: '已思考',
          content: r.content ? [r.content] : [],
          think: r.think ? [r.think] : [],
          info,
          extra,
          todos: cloneMaybeArray(extra?.todo_list ?? []),
          images: cloneMaybeArray(extra?.image_meta ?? []),
          pending: false,
          lastField: r.think ? 'think' : 'content',
        }

        appendToolCallsFromExtra(newMsg, extra, r)
        list.push(newMsg)
        aiIndexByGeneration.set(generationId, list.length - 1)
      } else {
        const msg = list[index]
        mergeHistoryAiMessage(msg, r, extra, info)
      }
    }
  }

  return list
}

async function loadHistoryMessages(hid: string, force = false) {
  if (!hid || hid === '-1') return
  if (loadingHistorySet.has(hid)) return
  if (!force && loadedHistorySet.has(hid)) return

  loadingHistorySet.add(hid)
  try {
    const res = await window.api.getChatMsgs(cid.value, sid.value, hid)
    const raw = res?.messages
    if (!Array.isArray(raw)) return

    console.log("Get message list: ", raw)

    const parsed = parseHistoryMessages(raw, hid)
    const list = ensureHistoryMessages(hid)
    list.splice(0, list.length, ...parsed)
    loadedHistorySet.add(hid)
  } catch (err) {
    console.error('Failed to load history messages:', err)
  } finally {
    loadingHistorySet.delete(hid)
  }
}

const handleSelectHistory = async (id: string | number) => {
  const nextHid = String(id)
  if (nextHid === store.current_history_id) return

  isQuoteShow.value = false
  quotedText.value = ''

  store.current_history_id = nextHid
  store.currentWorkDir = store.getWorkDir(nextHid)

  ensureHistoryMessages(nextHid)
  ensureGeneratingState(nextHid)

  if (!loadedHistorySet.has(nextHid)) {
    await loadHistoryMessages(nextHid)
  }

  // console.log('hid = ', nextHid, '\n', messages.value)

  const index = historyList.value.findIndex(c => String(c.id) === store.current_history_id)
  if (index !== -1) {
    historyList.value[index].hasNewMessage = false
  }

  nextTick(scrollToBottom)
}

const handleCreateChat = async () => {
  selectMode.value = false

  isQuoteShow.value = false
  quotedText.value = ''

  if (messages.value.length === 0 && store.current_history_id !== '-1') return

  const newHid = '-1'

  ensureHistoryMessages(newHid)
  ensureGeneratingState(newHid)

  store.current_history_id = newHid
  store.currentWorkDir = store.getWorkDir(newHid)

  startTypewriter()
}

const createChat = async () => {
  if (messages.value.length === 0 && store.current_history_id !== '-1') return

  const format_date = formatTime(new Date().toLocaleString())
  const res = await window.api.newChat(cid.value)
  const newHid = String(res.messages)

  ensureHistoryMessages(newHid)
  ensureGeneratingState(newHid)

  const chat = {
    id: newHid,
    preview: 'New chat...',
    time: format_date.time,
    date: format_date.label,
    tokens: 0,
    star: false,
    createTime: format_date.full,
  }

  historyList.value.unshift(chat)
  store.current_history_id = newHid
  store.setWorkDir(store.current_history_id, store.currentWorkDir)
  loadedHistorySet.add(newHid)
}

const handleDeleteHistory = (history_id: string) => {
  const hid = String(history_id)
  const index = historyList.value.findIndex(c => String(c.id) === hid)

  if (index === -1) {
    ElMessage({ type: 'warning', message: '未找到要删除的记录', plain: true })
    return
  }

  if (hid === store.current_history_id) {
    store.current_history_id = '-1'
    isQuoteShow.value = false
    quotedText.value = ''
  }

  store.removeWorkDir(hid)
  delete messageCache[hid]
  delete generatingState[hid]
  loadedHistorySet.delete(hid)
  loadingHistorySet.delete(hid)

  historyList.value.splice(index, 1)
  ElMessage({ type: 'success', message: '删除成功', plain: true })
}

const handleEditFinish = async (id: string, newContent: string) => {
  if (newContent === '') return
  const list = messages.value

  if(list.at(-1)?.pending === true) {
    try {
      ElMessage({
        type: 'info',
        message: "等待流式传输完成...",
        plain: true,
      })
      await window.api.stopGeneration(
        cid.value,
        sid.value,
        store.current_history_id,
      )
    } catch (err) {
      console.error('Request failed', err)
      return
    }
  }

  const targetIndex = list.findIndex(
    msg => msg.id === id && msg.role === 'human'
  )

  if (targetIndex === -1) return

  const remain = list.slice(0, targetIndex)

  list.splice(0, list.length, ...remain)
  const last_node = list.at(-1)
  const parent_id = last_node?.node_id

  await sendMessage(newContent, parent_id)
}

const handleRegenerate = async (id: string) => {
  const list = messages.value

  if(list.at(-1)?.pending === true) {
    try {
      ElMessage({
        type: 'info',
        message: "等待流式传输完成...",
        plain: true,
      })
      await window.api.stopGeneration(
        cid.value,
        sid.value,
        store.current_history_id,
      )
    } catch (err) {
      console.error('Request failed', err)
      return
    }
  }

  const targetIndex = list.findIndex(
    msg => msg.id === id && msg.role === 'human'
  )

  if (targetIndex === -1) {
    ElMessage({
      type: 'warning',
      message: "输入内容缺失或已被删除",
      plain: true,
    })
    return
  }

  console.log("Resend input: [", targetIndex, "] ", list[targetIndex])
  const inputs = list[targetIndex].content
  if (!inputs) return

  const remain = list.slice(0, targetIndex)

  list.splice(0, list.length, ...remain)
  const last_node = list.at(-1)
  const parent_id = last_node?.node_id

  await sendMessage(inputs, parent_id)
}

const selectMode = ref(false)
const selectMessageBubble = (msgId: string) => {
  const list = messages.value

  let hit = false

  for (const msg of list) {
    if (msg.id === msgId && msg.pending === false) {
      msg.selected = true
      hit = true
    }
  }

  if (hit) {
    selectMode.value = true
  }
}

// Normalize MessageChunk to string
function chunkToString(chunk: MessageChunk): string {
  if (typeof chunk === 'string') return chunk

  // ToolLabel -> custom display
  return `\n\n[>_ ${chunk.tool_name}]\n\n`
}

// Todo -> string
function todosToString(todos?: TodoItem[]): string {
  if (!Array.isArray(todos) || todos.length === 0) return ''

  return todos
    .map(todo => {
      // Map status to symbol
      const statusMap: Record<TodoItem['status'], string> = {
        pending: '⏳',
        in_progress: '📍',
        completed: '✅',
        error: '❌',
      }

      const icon = statusMap[todo.status] ?? '•'

      return `> - ${icon} ${todo.content}`
    })
    .join('\n')
}

// Normalize field (string | MessageChunk[]) to string
function fieldToString(field?: string | MessageChunk[]): string {
  if (!field) return ''

  if (typeof field === 'string') return field

  return field.map(chunkToString).join('')
}

function handleSelectText(msgId: string, role: string) {
  const msg = messages.value.find(
    m => m.id === msgId && m.role === role && m.pending === false
  )

  if (!msg) return

  let mdContent = fieldToString(msg.think)

  if (mdContent !== '') mdContent += '\n\n---\n\n'

  mdContent += fieldToString(msg.content)

  // append todos
  const todosStr = todosToString(msg.todos)
  if (todosStr) {
    mdContent += '\n\n---\n\n'
    mdContent += todosStr
  }

  mdDisplayer.show(mdContent)
}

// ################################
// WebSocket
// ################################
function getPayloadHistoryId(payload: any) {
  return String(
    payload?.data?.history_id ??
    payload?.history_id ??
    ''
  )
}

const isHistoryHide = ref(true)
const handleHideHistory = (toHide: boolean) => {
  isHistoryHide.value = toHide
}

const actionMap: Record<string, (payload: any, historyId: string) => void> = {
  msg_stream_start: handleStreamStart,
  think_chunk_rtn: handleThinkChunkRtn,
  content_chunk_rtn: handleContentChunkRtn,
  info_chunk_rtn: handleInfoChunkRtn,
  msg_stream_end: handleStreamEnd,
  msg_stream_abort: handleStreamAbort,
  async_tool_return: handleAsyncToolRtn,
  tool_exec_chunk_rtn: handleToolChunkRtn,
  token_limit_warning: handleWarning,
}

function handleWsMessage(payload: any) {
  const historyId = getPayloadHistoryId(payload)
  if (!historyId) return

  ensureHistoryMessages(historyId)
  ensureGeneratingState(historyId)

  const index = historyList.value.findIndex(c => String(c.id) === historyId)
  if (index !== -1) {
    historyList.value[index].isGenerating = true
  }

  const handler = actionMap[payload.action]
  if (handler) {
    handler(payload, historyId)
  }
}

const handleConnectProject = async () => {
  const result = await window.api.openFileDialog("folder")
  if (result.canceled || result.filePaths.length === 0) {
    return
  }

  // console.log('Current history id: ', store.current_history_id)
  if (store.current_history_id !== '-1') store.setWorkDir(store.current_history_id, result.filePaths[0])
  store.currentWorkDir = result.filePaths[0]
  store.removeWorkDir('-1')
}

function ensureAiMessage(list: ChatMessage[], historyId: string, generationId: string) {
  let index = findLatestIndexById(list, generationId, 'ai')
  if (index === -1) {
    list.push({
      id: generationId,
      cid: cid.value,
      hid: historyId,
      role: 'ai',
      label: '已准备',
      content: [],
      think: [],
      info: null,
      pending: true,
      lastField: undefined,
    })
    index = list.length - 1
  }
  return index
}

function handleAsyncToolRtn(payload: any, historyId: string) {
  const toolMsg = payload.data?.messages
  const taskId = payload.data?.task_id
  if (!toolMsg || !taskId) return

  const list = ensureHistoryMessages(historyId)
  const index = findLatestIndexById(list, taskId, 'system')

  if (index !== -1) {
    list[index].content = toolMsg.info?.tool_name ?? null
    list[index].desc = toolMsg.info?.desc ?? null
    list[index].status = toolMsg.info?.status ?? null
    list[index].pending = false
  } else {
    list.push({
      id: taskId,
      cid: cid.value,
      hid: historyId,
      role: 'system',
      content: toolMsg.info?.tool_name ?? null,
      desc: toolMsg.info?.desc ?? null,
      status: toolMsg.info?.status ?? null,
      pending: false,
    })
  }
}

function handleStreamStart(payload: any, historyId: string) {
  const generationId = payload.generation_id
  if (!generationId) return

  const list = ensureHistoryMessages(historyId)
  const state = ensureGeneratingState(historyId)
  const humanIndex = findLatestIndexByStatus(list, true, 'human')

  if (humanIndex !== -1) {
    list[humanIndex].id = generationId
    list[humanIndex].pending = false
  }

  state.isGenerating = true
  state.streamStateText = '停止生成'

  const existingIndex = findLatestIndexById(list, generationId, 'ai')
  if (existingIndex === -1) {
    list.push({
      id: generationId,
      cid: cid.value,
      hid: historyId,
      role: 'ai',
      label: '已准备',
      content: [],
      think: [],
      info: null,
      pending: true,
      lastField: undefined,
    })
  } else {
    list[existingIndex].pending = true
    list[existingIndex].label = '已准备'
    list[existingIndex].lastField = undefined
  }

  if (historyId === store.current_history_id) {
    nextTick(scrollToBottom)
  }
}

function handleThinkChunkRtn(payload: any, historyId: string) {
  const deltaThink = payload.data?.messages?.content ?? ''
  const generationId = payload.generation_id
  if (!generationId) return

  const list = ensureHistoryMessages(historyId)
  const state = ensureGeneratingState(historyId)
  const index = ensureAiMessage(list, historyId, generationId)

  const msg = list[index]

  state.isGenerating = true
  state.streamStateText = '正在思考'

  if (msg.pending === true) {
    msg.label = '思考中...'
    appendChunk(msg, 'think', deltaThink, generationId)
    msg.lastField = 'think'
  }
}

function handleContentChunkRtn(payload: any, historyId: string) {
  const deltaContent = payload.data?.messages?.content ?? ''
  const generationId = payload.generation_id
  if (!generationId) return

  const list = ensureHistoryMessages(historyId)
  const state = ensureGeneratingState(historyId)
  const index = ensureAiMessage(list, historyId, generationId)

  const msg = list[index]

  state.isGenerating = true
  state.streamStateText = '正在回答'

  if (msg.pending === true) {
    msg.label = '回答中...'
    appendChunk(msg, 'content', deltaContent, generationId)
    msg.lastField = 'content'
  }
}

function handleInfoChunkRtn(payload: any, historyId: string) {
  const deltaInfo = payload.data?.messages?.content
  const generationId = payload.generation_id
  if (!deltaInfo || !generationId) return

  const list = ensureHistoryMessages(historyId)
  const state = ensureGeneratingState(historyId)
  const index = ensureAiMessage(list, historyId, generationId)

  state.isGenerating = true

  if (list[index].pending === true) {
    
  }
}

async function handleStreamEnd(payload: any, historyId: string) {
  const generationId = payload.generation_id
  if (!generationId) return

  const list = ensureHistoryMessages(historyId)
  const state = ensureGeneratingState(historyId)
  const index = findLatestIndexById(list, generationId, 'ai')

  state.isGenerating = false
  state.streamStateText = ''

  if (index !== -1 && list[index].pending === true) {
    list[index].label = '已思考'
    list[index].pending = false
    list[index].lastField = undefined
  }

  await syncHistoryMessages(historyId)

  const hIndex = historyList.value.findIndex(c => String(c.id) === historyId)
  if (hIndex !== -1) {
    historyList.value[hIndex].isGenerating = false
    if (store.current_history_id !== historyId) {
      historyList.value[hIndex].hasNewMessage = true
    }
  }
}

async function handleStreamAbort(payload: any, historyId: string) {
  const generationId = payload.generation_id
  const event_name = payload.data?.messages?.event_name
  const detail = payload.data?.messages?.content
  if (!generationId) return
  if (event_name === 'error_occurred') {
    ElMessage({
      type: 'error',
      message: detail,
      plain: true,
    })
  }

  const list = ensureHistoryMessages(historyId)
  const state = ensureGeneratingState(historyId)

  state.isGenerating = false
  state.streamStateText = ''

  const index = findLatestIndexById(list, generationId, 'ai')
  if (index !== -1 && list[index].pending === true) {
    list[index].pending = false
    list[index].lastField = undefined
  }

  await syncHistoryMessages(historyId)
  console.warn('Generation abort, generation_id = ', generationId)

  const hIndex = historyList.value.findIndex(c => String(c.id) === historyId)
  if (hIndex !== -1) {
    historyList.value[hIndex].isGenerating = false
    if (store.current_history_id !== historyId) {
      historyList.value[hIndex].hasNewMessage = true
    }
  }
}

const isWarningShow = ref(false)
const WarningContent = ref('')

function handleWarning(payload: any, historyId: string) {
  const generationId = payload.generation_id
  if (!generationId) return

  if (payload.action === 'token_limit_warning') {
    WarningContent.value = '当前选择的模型上下文窗口过小，请及时更换。'
  }

  isWarningShow.value = true
}

function handleWarningClose() {
  WarningContent.value = ''
  isWarningShow.value = false
}

function handleToolChunkRtn(payload: any, historyId: string) {
  const generationId = payload.generation_id
  const toolData = payload.data?.messages
  if (!generationId || !toolData) return

  const toolName = toolData?.tool_name
  const toolCallId = toolData?.tool_call_id
  const chunkPosition = toolData?.chunk_position
  const chunkStatus = toolData?.status
  const toolContent = toolData?.content

  const list = ensureHistoryMessages(historyId)
  const index = findLatestIndexById(list, generationId, 'ai')

  if (toolCallId && toolCallId !== '' && index !== -1) {
    const msg = list[index]

    let status: ToolLabel['status'] = 'pending'
    if (chunkPosition === 'start') {
      status = 'in_progress'
    } else if (chunkPosition === 'end') {
      status = chunkStatus === 'success' ? 'completed' : 'error'
    }

    const toolLabel: ToolLabel = {
      tool_call_id: toolCallId,
      tool_name: toolName,
      content: toolContent,
      status,
    }

    const field = msg.lastField ?? 'think'
    appendToolLabel(msg, field, toolLabel, generationId)
  }

  if (toolName === 'send_images') {
    handleImageChunkRtn(generationId, toolData, historyId)
  }
  else if (toolName === 'write_todos') {
    handleTodoChunkRtn(generationId, toolData, historyId)
  }
}

function handleTodoChunkRtn(generationId: string, data: any, historyId: string) {
  // console.log("Todo data: ", data)
  if (!data || !generationId) return

  const list = ensureHistoryMessages(historyId)
  const state = ensureGeneratingState(historyId)
  const index = ensureAiMessage(list, historyId, generationId)
  const todos = data.content

  if (!todos) return
  if (data.chunk_position !== 'start' || data.status !== 'success') return

  state.isGenerating = true

  if (list[index].pending === true) {
    list[index].todos = cloneMaybeArray(todos)
  }
}

function handleImageChunkRtn(generationId: string, data: any, historyId: string) {
  if (!data || !generationId) return

  const list = ensureHistoryMessages(historyId)
  const state = ensureGeneratingState(historyId)
  const index = ensureAiMessage(list, historyId, generationId)

  state.isGenerating = true

  if (list[index].pending === true) {
    if (data.chunk_position === 'end' && data.status === 'success') {
      if (!Array.isArray(list[index].images)) {
        list[index].images = []
      }
      const content = data.content
      if (Array.isArray(content)) {
        list[index].images!.push(...content)
      }
    }
  }
}

async function syncHistoryMessages(historyId: string) {
  if (!historyId || historyId === '-1') return
  if (loadingHistorySet.has(historyId)) return

  const list = ensureHistoryMessages(historyId)
  const hasPending = list.some(m => m.pending)

  if (hasPending) return

  try {
    const res = await window.api.getChatMsgs(cid.value, sid.value, historyId)
    const raw = res?.messages
    if (!Array.isArray(raw)) return

    const parsed = parseHistoryMessages(raw, historyId)
    list.splice(0, list.length, ...parsed)
    loadedHistorySet.add(historyId)
  } catch (err) {
    console.warn('syncHistoryMessages failed:', err)
  }
}

async function handleSendMessage() {
  const list = messages.value
  const last_node = list.at(-1)
  const parent_id = last_node?.node_id
  await sendMessage(inputText.value.trim(), parent_id)
}

// ################################
// Send message
// ################################
async function sendMessage(content:string = '', parent_id: number = 0, pushToList: boolean = true) {
  if (!store.config.modelName
    || store.config.modelName === ''
    || !store.config.modelProvider
    || store.config.modelProvider === ''
  ) {
    ElMessage({
      type: 'warning',
      message: '请选择一个模型',
      plain: true,
    })
    return
  }

  if (isUploading.value) {
    ElMessage({
      type: 'warning',
      message: '请等待文件上传完成',
      plain: true,
    })
    return
  }

  if (content.length > 32000) {
    ElMessage({
      type: 'warning',
      message: '输入文本过长',
      plain: true,
    })
    return
  }

  if (!content) return
  if (store.current_history_id === '-1') await createChat()

  const currentHid = store.current_history_id
  const list = ensureHistoryMessages(currentHid)
  ensureGeneratingState(currentHid)
  loadedHistorySet.add(currentHid)

  const uploadedFiles = selectedFiles.value
    .filter(f => f.id && f.type === 'success')
    .map(f => ({
      file_name: f.name,
      file_id: f.id!,
    }))

  if (quotedText.value !== '') {
    content = `> “${quotedText.value}”\n\n` + content
  }

  isQuoteShow.value = false
  quotedText.value = ''

  const messagePayload = {
    role: 'human',
    content,
    parent_id,
    extra: {
      user_meta_data: {
        uploaded_files: uploadedFiles,
      },
    },
  }

  if (pushToList) {
    list.push({
      id: genUUID(),
      cid: cid.value,
      hid: currentHid,
      role: 'human',
      content,
      extra: messagePayload.extra,
      error: false,
      pending: true,
    })
  }

  inputText.value = ''
  selectedFiles.value = []
  scrollToBottom()

  if (list.length === 1) {
    const nowHis = historyList.value.find(c => String(c.id) === currentHid)
    if (nowHis) {
      nowHis.preview = content
      try {
        await window.api.updateConversation(
          cid.value,
          sid.value,
          currentHid,
          { title: content.slice(0, 30) }
        )
      } catch (err) {
        console.warn('Failed to update conversation title:', err)
      }
    }
  }

  try {
    await window.api.chatComplations(
      cid.value,
      sid.value,
      currentHid,
      messagePayload,
      {
        models_provider: store.config.modelProvider,
        model_name: store.config.modelName,
        api_key: store.config.apiKey,
        enable_think: store.config.deepThink,
        work_dir: store.currentWorkDir,

        llm_calls_warning_threshold: store.config.tokenLimit,
        async_tools_invoke: store.config.toolsInvokeAi,
        link_provider: store.config.linkProvider,
        link_api_key: store.config.linkApiKey,
        content_provider: store.config.contentPovider,
        content_api_key: store.config.contentApiKey,
        web_cleaner_mode: store.config.webContentFilter,
        keep_tools_message: store.config.remainToolsCache,
        enable_longterm_memory: store.config.longtermMemory,
        enable_shortterm_memory: store.config.shorttermMemory,
        summary_trigger_threshold: store.config.messageSummary,
        summary_exempt_tail_length: store.config.keepNotSummary,
        pure_chat_on: store.config.pureChat,
        use_model_vision: store.config.visionOn,

        enable_file_opration: store.config.fileOpration,
        enable_web_search: store.config.webSearch,
        enable_knowledge_retrieval: store.config.knowledgeRetrieval,
        enable_command_opration: store.config.commandOpration,
        enable_skill_load: store.config.skillLoad,
        enable_agent_assign: store.config.agentAssign,
        enable_agent_swarm: store.config.agentSwarm,

        embed_model: store.config.embeddingModel,
        role_prompt: toRaw(store.config.rolePrompt),
        higher_role_prompt_permission: store.config.higherRolePromptPermission,
        enable_task_flow: store.config.testExpertMode,
      }
    )
  } catch (err) {
    console.error('Request failed', err)
    ElMessage({
      type: 'error',
      message: '消息发送失败',
      plain: true,
    })

    const index = findLatestIndexByStatus(list, true, 'human')
    if (index !== -1) {
      list[index].pending = false
      list[index].error = true
    }
  }
}

const handleCancel = () => {
  messages.value.forEach(msg => {
    if (msg.selected) msg.selected = false
  })

  selectMode.value = false
}

const handleDeleteMessages = async () => {
  const list = messages.value

  const del_list = list
    .filter(msg => msg.selected)
    .map(msg => ({
      generation_id: msg.id,
      role: msg.role,
    }))

  const remain = list.filter(msg => !msg.selected)

  if (del_list.length === 0) {
    ElMessage({
      type: 'warning',
      message: '未选择任何消息',
      plain: true,
    })
    return
  }

  try {
    await ConfirmDialog.confirm(
      `确定删除要选中的 ${del_list.length} 条记录吗？<br>` +
      `⚠︎ 在此之前产生的部分摘要记忆也将删除。`,
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
    const res = await window.api.deleteMsgs(
      cid.value, 
      store.current_history_id, 
      del_list
    )
    if (res.success !== true) throw new Error(res.messages || "Delete messages failed.")

    list.splice(0, list.length, ...remain)
  } catch (error) {
    ElMessage({
      type: 'warning',
      message: '删除失败: ' + error,
      plain: true,
    })
    return
  }

  ElMessage({
    type: 'success',
    message: '已删除',
    plain: true,
  })

  selectMode.value = false
}

const isQuoteShow = ref(false)
const quotedText = ref('')

function handleQuoteClose() {
  isQuoteShow.value = false
  quotedText.value = ''
}

function handleQuoteShow(id: string, content: string) {
  if (id !== store.current_history_id) return
  isQuoteShow.value = true
  quotedText.value = content
}


// ################################
// Lifecycle
// ################################
onMounted(async () => {
  try {
    unsubscribeWs = window.api.onWsMessage((payload: any) => {
      handleWsMessage(payload)
    })

    await authStore.restore()
    cid.value = authStore.user.user_uid
    historyList.value = await get_conversation_list(cid.value)

    if (store.current_history_id && store.current_history_id !== '-1') {
      ensureHistoryMessages(store.current_history_id)
      ensureGeneratingState(store.current_history_id)
      await loadHistoryMessages(store.current_history_id)
    }
    if (store.current_history_id) {
      store.currentWorkDir = store.getWorkDir(store.current_history_id)
    }
  } catch (err) {
    console.error('Initialization failed', err)
  }

  startTypewriter()

  cursorTimer = window.setInterval(() => {
    showCursor.value = !showCursor.value
  }, 520)
})

onBeforeUnmount(() => {
  unsubscribeWs?.()
  unsubscribeWs = null

  if (timer) clearInterval(timer)
  if (cursorTimer) clearInterval(cursorTimer)
})

// ################################
// Utils
// ################################
function genUUID() {
  return crypto.randomUUID()
}

function scrollToBottom() {
  const box = document.querySelector('.message-list')
  if (!box) return
  box.scrollTo({ top: box.scrollHeight, behavior: 'smooth' })
}

function formatTime(timeStr: string) {
  if (!timeStr) return { label: '无效时间', time: '', full: '' }

  let inputTime = new Date(timeStr)

  if (isNaN(inputTime.getTime())) {
    const isoStr = timeStr.replace(' ', 'T')
    inputTime = new Date(isoStr)
    if (isNaN(inputTime.getTime())) {
      return { label: '无效时间', time: '', full: timeStr }
    }
  }

  const hours = String(inputTime.getHours()).padStart(2, '0')
  const minutes = String(inputTime.getMinutes()).padStart(2, '0')
  const seconds = String(inputTime.getSeconds()).padStart(2, '0')
  const timePart = `${hours}:${minutes}:${seconds}`

  const now = new Date()
  const dayDiff = Math.floor(
    (
      Date.UTC(now.getFullYear(), now.getMonth(), now.getDate()) -
      Date.UTC(inputTime.getFullYear(), inputTime.getMonth(), inputTime.getDate())
    ) / (24 * 60 * 60 * 1000)
  )

  let dateLabel = 'Further more'
  if (dayDiff === 0) dateLabel = 'Today'
  else if (dayDiff === 1) dateLabel = 'Yesterday'
  else if (dayDiff >= 2 && dayDiff <= 7) dateLabel = 'In this Week'

  return {
    label: dateLabel,
    time: timePart,
    full: inputTime.toLocaleString(),
  }
}

// ################################
// Chat configuration
// ################################
const show_work_dir = computed(() => store.currentWorkDir)

const modelPoviderOptions = [
  { label: 'Ollama:local', value: 'ollama:local', icon: ollamaIcon },
  { label: 'Ollama', value: 'ollama', icon: ollamaIcon },
  { label: 'OpenAI', value: 'openai', icon: openaiIcon },
  { label: 'Google', value: 'google', icon: googleIcon },
  { label: 'DeepSeek', value: 'deepseek', icon: deepseekIcon },
  { label: '通义千问', value: 'qwen', icon: qwenIcon },
  { label: '月之暗面', value: 'moonshot', icon: moonshotIcon },
]

const renderSingleSelectTag = ({ option }: any) => {
  return h(
    'div',
    { style: { display: 'flex', background: 'transparent', borderRadius: '12px' } },
    [
      h(NAvatar, {
        src: option.icon,
        round: false,
        size: 22,
        objectFit: 'contain',
        style: { background: 'transparent' },
      }),
      h('div', { style: { opacity: 0, width: '0px' } }, option.label),
    ]
  )
}

const renderLabel = (option: any) => {
  return h(
    'div',
    { style: { display: 'flex', alignItems: 'center', borderRadius: '12px' } },
    [
      h(NAvatar, {
        src: option.icon,
        round: true,
        size: 24,
        objectFit: 'contain',
        style: { background: '#FFFA', padding: '3px' },
      }),
      h(
        'div',
        { style: { marginLeft: '6px' } },
        option.label
      ),
    ]
  )
}

const errorServer = ref(true)
const modelSelectOptions = ref<any[]>([])
let latestRequestId = 0

watch(
  () => store.config.modelProvider,
  async (newProvider, oldProvider) => {
    if (newProvider === oldProvider) return

    store.saveAppConfig('modelProvider', newProvider)
    store.config.apiKey = store.apiKeyCache[store.config.modelProvider] ?? ''

    store.saveAppConfig('modelName', '')
    modelSelectOptions.value.length = 0

    if (!newProvider) return

    const requestId = ++latestRequestId

    try {
      const models = await window.api.getModelsList(
        newProvider,
        store.config.apiKey
      )

      if (requestId !== latestRequestId) return

      modelSelectOptions.value.push(
        ...models.map((name: string) => ({
          label: name,
          value: name,
        }))
      )
      errorServer.value = false
      ensureValidModel()
    } catch (err) {
      if (requestId !== latestRequestId) return

      errorServer.value = true
      modelSelectOptions.value = [{
        label: 'Server Error: Please make sure ai service is accessable.',
        value: '',
      }]
      ensureValidModel()
      console.error('getModelsList failed:', err)
    }
  },
  { immediate: true }
)

watch(
  () => store.config.modelName,
  (val, oldVal) => {
    if (val === oldVal) return
    if (!val) return

    store.saveAppConfig('modelName', val)
    console.log('Update model to:', val)
  },
  { immediate: true }
)

function ensureValidModel() {
  const options = modelSelectOptions.value
  if (options.length === 0) return

  const current = store.config.modelName
  const isValid = options.some(opt => opt.value === current)

  if (!current || !isValid) {
    const firstValue = options[0].value
    store.saveAppConfig('modelName', firstValue)
    console.log('Use default model:', firstValue)
  }
}

const editApiKey = async () => {
  InputDialog.open('请输入您的 API 密钥', 'API KEY', {
    defaultValue: store.config.apiKey,
  })
    .then(value => {
      store.config.apiKey = value
      if (store.config.modelProvider) {
        store.setApiKeyCache(store.config.modelProvider, value)
      }
    })
    .catch(() => {})
}

watch(
  () => store.config.apiKey,
  async (newkey, oldkey) => {
    if (newkey === oldkey) return

    store.saveAppConfig('apiKey', newkey)
    modelSelectOptions.value.length = 0

    const requestId = ++latestRequestId

    try {
      const models = await window.api.getModelsList(store.config.modelProvider, newkey)
      if (requestId !== latestRequestId) return

      modelSelectOptions.value.push(
        ...models.map((name: string) => ({
          label: name,
          value: name,
        }))
      )

      errorServer.value = false
      ensureValidModel()
    } catch (err) {
      if (requestId !== latestRequestId) return

      errorServer.value = true
      modelSelectOptions.value = [{
        label: 'Server Error: Please make sure ai service is accessable.',
        value: '',
      }]
      ensureValidModel()
      console.error('getModelsList failed:', err)
    }
  }
)

const setDeepThink = () => {
  store.saveAppConfig('deepThink', !store.config.deepThink)
}

// ################################
// Greeting / typing effect
// ################################
const fullText = ref('  “嗨！今天从哪里开始？”')

function getRandomGreeting(): string {
  const greetings = [
    '  “嗨！今天从哪里开始？”',
    '  “准备好继续了吗？”',
    '  “要不要从一个新想法开始？”',
    '  “这次想聊点什么？”',
    '  “今天有什么新计划？”',
    '  “有个想法想整理一下吗？”',
  ]

  const index = Math.floor(Math.random() * greetings.length)
  return greetings[(index + 1) % 6]
}

const displayText = ref('')
const showCursor = ref(true)

let timer: number | null = null
let cursorTimer: number | null = null

function startTypewriter() {
  fullText.value = getRandomGreeting()
  displayText.value = '⌘  '
  let index = 1

  if (timer) {
    clearInterval(timer)
    timer = null
  }

  timer = window.setInterval(() => {
    displayText.value += fullText.value[index]
    index++

    if (index >= fullText.value.length) {
      clearInterval(timer!)
      timer = null
      setTimeout(() => {
        showCursor.value = false
      }, 800)
    }
  }, 60)
}

const stopGenerating = async () => {
  try {
    await window.api.stopGeneration(
      cid.value,
      sid.value,
      store.current_history_id,
    )
  } catch (err) {
    console.error('Request failed', err)
  }
}

const msgInputHandleKeydown = async (e: KeyboardEvent & { isComposing?: boolean; keyCode?: number }) => {
  if (e.isComposing || e.keyCode === 229) {
    return
  }

  if (e.shiftKey && e.key === 'Enter') {
    return
  }

  if (e.key === 'Enter') {
    e.preventDefault()
    const list = messages.value
    const last_node = list.at(-1)
    const parent_id = last_node?.node_id
    await sendMessage(inputText.value.trim(), parent_id)
  }
}

// ################################
// File select / upload
// ################################
const selectedFiles = ref<TagsItem[]>([])

const handlePathTagClose = (tag: TagsItem) => {
  const index = selectedFiles.value.indexOf(tag)
  if (index !== -1) {
    selectedFiles.value.splice(index, 1)
  }
}

const makeUniqueFileName = (
  fileName: string,
  existingNames: Set<string>
): string => {
  if (!existingNames.has(fileName)) {
    return fileName
  }

  const dotIndex = fileName.lastIndexOf('.')
  const base = dotIndex !== -1 ? fileName.slice(0, dotIndex) : fileName
  const ext = dotIndex !== -1 ? fileName.slice(dotIndex) : ''

  let index = 1
  let newName = `${base} (${index})${ext}`

  while (existingNames.has(newName)) {
    index += 1
    newName = `${base} (${index})${ext}`
  }

  return newName
}

const isUploading = ref(false)
const upload_no_error = ref(true)

watch(
  () => selectedFiles.value.map(f => f.type),
  types => {
    upload_no_error.value = !types.includes('danger')
  },
  { immediate: true }
)

const selectFile = async () => {
  if (isUploading.value) return

  try {
    const result = await window.api.openFileDialog("file")
    if (result.canceled || result.filePaths.length === 0) return

    isUploading.value = true

    const existingNames = new Set(selectedFiles.value.map(f => f.name))

    const newFiles: TagsItem[] = result.filePaths.map((filePath: string) => {
      const originalName = filePath.split(/[/\\]/).pop() || filePath
      const uniqueName = makeUniqueFileName(originalName, existingNames)
      existingNames.add(uniqueName)

      return {
        name: uniqueName,
        path: filePath,
        type: 'info',
      }
    })

    const startIndex = selectedFiles.value.length
    selectedFiles.value.push(...newFiles)

    const uploadTasks = newFiles.map((_, offset) => {
      const index = startIndex + offset
      const tag = selectedFiles.value[index]

      const plainFile = {
        name: tag.name,
        path: tag.path,
      }

      return window.api
        .uploadAiFiles(cid.value, [plainFile])
        .then((res: {
          success: boolean
          messages: Array<{ file_id: string; file_name: string }>
        }) => {
          if (!res.success) {
            throw new Error('upload failed')
          }

          if (!Array.isArray(res.messages)) {
            throw new Error('invalid response format')
          }

          const matched = res.messages.find(r => r.file_name === tag.name)
          if (!matched?.file_id) {
            throw new Error('file_id not returned')
          }

          selectedFiles.value[index] = {
            ...tag,
            id: matched.file_id,
            type: 'success',
          }
        })
        .catch(err => {
          console.error(`Upload failed: ${tag.name}`, err)

          selectedFiles.value[index] = {
            ...tag,
            type: 'danger',
          }
        })
    })

    await Promise.allSettled(uploadTasks)

    ElMessage({
      type: 'success',
      message: '文件上传完成',
      plain: true,
    })
  } catch (err) {
    console.error('selectFile failed:', err)
    ElMessage({
      type: 'error',
      message: '文件上传失败' + String(err),
      plain: true,
    })
  } finally {
    isUploading.value = false
  }
}

// ################################
// Maximize input
// ################################
const fullInput = ref(false)
const setFullInput = () => {
  fullInput.value = !fullInput.value
}
</script>

<style scoped>

.main-area {
  display: flex;
  justify-content: center;
  padding: 0;
  position: relative;
  overflow: hidden;
  height: calc(100vh - 30px);
}

.ai-page-wrapper {
  display: grid;
  position: relative;
  grid-template-columns: 20% 80%;
  width: 100%;
  height: 100%;
  overflow: hidden;
  transition: all 0.28s cubic-bezier(0.23, 1, 0.32, 1);
}

.ai-page-wrapper.is-history-hide {
  display: grid;
  position: relative;
  grid-template-columns: 0% 100%;
  width: 100%;
  height: 100%;
  overflow: hidden;
  transition: all 0.28s cubic-bezier(0.23, 1, 0.32, 1);
}

.ai-history-pannel.is-history-hide {
  width: 40px !important;
  max-width: 40px;
}

.chat-wrapper {
  width: 100%;
  height: calc(100vh - 30px);
  position: relative;
  background-color: transparent;
  display: flex;
  justify-content: center;
}

.hello-div {
  display: flex;
  justify-content: center;  /* 水平居中 */
  align-items: center;
  font-size: 32px;
  color: #324f4c;
  font-family: "Microsoft YaHei";
  white-space: nowrap;
}

.work-dir-label {
  width: 60%;
  position: absolute;
  align-self: center;
  align-items: center;
  align-content: center;
  text-align: center;
  border-radius: 24px;
  height: 24px;
  top: 12px;
  backdrop-filter: blur(3px);
  background-color: #e7ebebca;
  border: 1px solid #324c4f81;
  color: #19312fe3;
  padding: 0px 12px 0px 0px;
  font-weight: bold;
  overflow: hidden;
  white-space: nowrap;
  display: block;
  z-index: 99999;
  transition: all 0.6s cubic-bezier(0.23, 1, 0.32, 1);
}

.work-dir-label.no_work_dir {
  width: 28px;
  height: 16px;
  color: transparent;
  background-color: #d1d1d130;
  border: 1px solid #a6a6a623;
}

.work-dir-label.no_work_dir::before {
  content: "•••";
  color: #62626238;
  position: absolute;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
}

.work-dir-label.no_work_dir:hover {
  width: 60%;
  height: 24px;
  color: #df0f0f4c;
  background-color: #ebb7b757;
  border: 1px solid #c82c2c23;
}

.work-dir-label.no_work_dir:hover::before {
  content: "";
}

.message-list {
  position: relative;
  z-index: 0;
  margin-top: 16px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 22px 52px 88px 52px;
  width: 85%;
  height: calc(100vh - 190px);
  scrollbar-width: none;
  -webkit-mask-image: linear-gradient(
    to bottom,
    transparent 0%,
    black 12px,
    black calc(100% - 12px),
    transparent 100%
  );
  mask-image: linear-gradient(
    to bottom,
    transparent 0%,
    black 12px,
    black calc(100% - 12px),
    transparent 100%
  );
}

.message-item {
  display: flex;
  flex-direction: row;
  position: relative;
  height: fit-content;
}

.message-item.human {
  justify-content: flex-end;
}

.message-item.ai {
  justify-content: flex-start;
  flex-direction: column; /* 或 row，根据布局需求 */
  height: fit-content; /* 根据需要设置最大高度 */
  max-width: calc(100% - 24px);
}

.buttom-div {
  min-height: 30px;
}

.ctrl-area {
  position: absolute;
  bottom: 20px;
  width: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  transition: all 0.6s cubic-bezier(0.23, 1, 0.32, 1);
}

.ctrl-area.empty_messages_list {
  bottom: 44vh;
  width: 80%;
  transition: all 0.6s cubic-bezier(0.23, 1, 0.32, 1);
}

.ctrl-btns-area {
  z-index: 999;
  position: absolute;
  height: 32px;
  width: 80%;
  border-radius: 24px;
  bottom: 30px;
  padding: 16px 16px;
  display: flex;
  justify-content: flex-end;
  -webkit-backdrop-filter: saturate(300%) blur(16px);
  backdrop-filter: saturate(300%) blur(16px);
  background: linear-gradient(0deg, rgb(251, 251, 251) 30%, color-mix(in oklch, #fbfbfb 90%, transparent) 60%, color-mix(in oklch, #fbfbfb 70%, transparent) 80%, color-mix(in oklch, #fbfbfb 50%, transparent));
  box-shadow:
    0 10px 26px rgba(77, 77, 77, 0.086),
    0 2px 6px rgba(0, 0, 0, 0.05),
    inset 1px 1px 0px rgba(255, 255, 255, 0.506),
    inset -1px 1px 0px rgba(255, 255, 255, 0.506);
  transition: all 0.6s cubic-bezier(0.23, 1, 0.32, 1);
}

.cd-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.cancel-btn {
  width: 80px;
  height: 32px;
  padding: 6px 16px;
  border-radius: 8px;
  border: none;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s ease;
  color: #555;
  background: transparent;
  box-shadow: inset 0 0 0 1px rgba(0, 0, 0, 0.08);
}

.cancel-btn:hover {
  color: #185d56;
  background: rgb(239, 239, 239);
}

.delete-btn {
  width: 80px;
  height: 32px;
  padding: 6px 16px;
  border-radius: 8px;
  border: none;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s ease;
  color: #f35050;
  background: transparent;
  box-shadow: inset 0 0 0 1px rgba(0, 0, 0, 0.08);
}

.delete-btn:hover {
  color: #df3f3f;
  background-color: rgb(255, 209, 209);
}

.quote-label,
.warning-label {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 12px;
  background-color: #fff8ef;
  border: 1px solid #ffc107;
  border-radius: 12px;
  color: #4a4124;
  font-size: 14px;
  line-height: 1.5;
  min-width: 160px;
  max-width: 75%;
}

.quote-label {
  background-color: #f7f7f7;
  border: 1px solid #cbcbcb;
  color: #474747;
}

.quote-content,
.warning-content {
  flex: 1;
  word-break: break-word;
}

.quote-close,
.warning-close {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  width: 24px;
  height: 24px;
  padding: 0;
  border: none;
  background: transparent;
  color: #856404;
  cursor: pointer;
  border-radius: 4px;
  transition: background-color 0.2s, color 0.2s;
}

.quote-close {
  color: #434343;
}

.warning-close:hover {
  background-color: rgba(0, 0, 0, 0.08);
  color: #5a3f02;
}

.quote-close:hover {
  background-color: rgba(0, 0, 0, 0.08);
  color: #202020;
}

.quote-close:active,
.warning-close:active {
  background-color: rgba(0, 0, 0, 0.12);
}

/* Enter & leave active */
.fade-enter-active,
.fade-leave-active {
  transition:
    opacity 0.18s ease,
    transform 0.18s ease;
}

/* Initial & final state */
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
  transform: translateY(6px) scale(0.98);
}

/* Stable visible state */
.fade-enter-to,
.fade-leave-from {
  opacity: 1;
  transform: translateY(0) scale(1);
}

.stop-btn-wrapper {
  border-radius: 16px;
  bottom: 20px;
  z-index: 10;
  background: transparent;
  box-shadow:
    0 10px 26px color-mix(in oklch, rgba(77, 77, 77) 11%, transparent),
    0 2px 6px color-mix(in oklch, rgba(77, 77, 77) 5%, transparent);
  transition: width 0.3s cubic-bezier(0.215, 0.61, 0.355, 1);
}

.stop-btn-wrapper:deep(svg) {
  width: 20px;
  height: 20px;
  fill: #232f2e76;
}

.stop-generate-button {
  width: fit-content;
  height: 32px;
  overflow: hidden;
  color: #232f2e76;
  border-radius: 16px;
  border: none;
  -webkit-backdrop-filter: saturate(300%) blur(16px);
  backdrop-filter: saturate(300%) blur(16px);
  background: color-mix(in oklch, #f6f6f6 40%, transparent);
  -webkit-transition: all 0.22s cubic-bezier(0.215, 0.61, 0.355, 1);
  transition: all 0.22s cubic-bezier(0.215, 0.61, 0.355, 1);

  border: 1.5px solid color-mix(in oklch, #f6f6f6 15%, transparent);      /* border replacement */
}

.stop-generate-button:hover {
  transform: scale(1.05);
  color: #2f232376;
}

.stop-generate-button:active {
  transform: scale(1.02);
  color: #232f2e76;
}

.stop-generate-button:deep(.icon) {
  overflow: visible;
  width: 14px;
  height: 14px;
  fill: #ff211dac;
  margin-right: 6px;
  box-shadow:
    0 0px 26px rgba(255, 0, 0, 0.206),
    0 0px 6px rgba(255, 0, 0, 0.09);
}

.wave-container {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 14px;
  height: 14px;
  margin-right: 6px;
}

.wave-container svg {
  position: relative;
  z-index: 2;
  width: 14px;
  height: 14px;
  fill: #ff211dac;
  margin-right: 0;
  box-shadow:
    0 0px 26px rgba(255, 0, 0, 0.206),
    0 0px 6px rgba(255, 0, 0, 0.09);
}

.wave {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-54%, -50%);
  width: 14px;
  height: 14px;
  border: 1px solid #ff211dac;
  border-radius: 4px;
  opacity: 0;
  z-index: 1;
  pointer-events: none;
}

.wave-1 {
  animation: wave-expand 2s cubic-bezier(0.215, 0.61, 0.355, 1) infinite;
}

.wave-2 {
  animation: wave-expand 2s cubic-bezier(0.215, 0.61, 0.355, 1) infinite 0.6s;
}

.wave-3 {
  animation: wave-expand 2s cubic-bezier(0.215, 0.61, 0.355, 1) infinite 1.2s;
}

@keyframes wave-expand {
  0% {
    width: 14px;
    height: 14px;
    opacity: 0.4;
    border-radius: 4px;
  }
  100% {
    width: 40px;
    height: 40px;
    opacity: 0;
    border-radius: 12px;
  }
}

.loading {
  overflow: visible;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  border: 2px solid rgba(255, 255, 255, 0.25);
  border-top-color: #ffffff;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.input-bar {
  /* position: absolute; */
  /* bottom: 20px; */
  z-index: 999;
  bottom: 0px;
  overflow: hidden;
  display: grid;
  grid-template-columns: calc(100% - 50px) 38px;
  column-gap: 10px;
  padding: 8px;
  -webkit-backdrop-filter: saturate(300%) blur(16px);
  backdrop-filter: saturate(300%) blur(16px);
  background: linear-gradient(0deg, rgb(251, 251, 251) 30%, color-mix(in oklch, #fbfbfb 90%, transparent) 60%, color-mix(in oklch, #fbfbfb 70%, transparent) 80%, color-mix(in oklch, #fbfbfb 50%, transparent));
  border-bottom: 2px solid rgba(43, 159, 140, 0.509);
  box-shadow:
    0 10px 26px rgba(77, 77, 77, 0.106),
    0 2px 6px rgba(0, 0, 0, 0.05),
    inset 1px 1px 0px rgba(255, 255, 255, 0.506),
    inset -1px 1px 0px rgba(255, 255, 255, 0.506);
  border-radius: 24px;
  width: 80%;
  row-gap: 14px;

  -webkit-transition: all 0.3s cubic-bezier(0.215, 0.61, 0.355, 1);
  transition: all 0.3s cubic-bezier(0.215, 0.61, 0.355, 1);
}

.send-button {
  width: 38px;
  height: 38px;
  font-size: 20px;
  border-radius: 100px;
  background: #76827f;
  color: whitesmoke;
  border: none;
  cursor: pointer;

  display: flex;
  align-self: flex-end;
  justify-self: end;
  grid-row: 2;
  grid-column: 2;

  /* 平滑动画 */
  transition: 
    transform 0.18s ease,
    box-shadow 0.25s ease,
    background 0.35s ease;
}

/* 悬停效果：轻微放大 + 阴影增强 */
.send-button:hover {
  transform: scale(1.08);
  box-shadow: 0 4px 14px rgb(255, 255, 255);
  background: rgb(105, 115, 114);
}

/* 点击效果：轻微缩小 + 暗色反馈 */
.send-button:active {
  transform: scale(0.95);
  background: rgb(82, 90, 90);
  box-shadow: 0 2px 8px rgba(255, 255, 255, 0.908);
}

.chat-input {
  grid-row: 1;
  grid-column: 1 / 3;
  padding: 8px;
  padding-top: 6px;
  transition: all 0.25s ease;
  align-self: center;
  width: calc(100% - 8px);
}

:deep(.chat-input .el-input__wrapper) {
  box-shadow: none !important;
  border: none !important;
  background-color: transparent;
  padding: 0 !important;
  transition: all 0.25s ease;
}

:deep(.chat-input .el-input__wrapper:hover) {
  box-shadow: none !important;
  border: none !important;
  transition: all 0.25s ease;
}

:deep(.chat-input .el-input__wrapper.is-focus) {
  box-shadow: none !important;
  border: none !important;
  transition: all 0.25s ease;
}

:deep(.chat-input .el-textarea__inner) {
  border: none !important;
  box-shadow: none !important;
  font-size: 16px;
  line-height: 20px;
  height: 38px;
  resize: none; /* 禁止拖拽大小 */
  padding: 0 !important;
  background: transparent;  
  border-radius: 0 !important;
  transition: all 0.25s ease;
  scrollbar-width: none;
  padding-top: 16px !important;
  margin-top: -16px !important;
}

.input-full-screen-button{
  position: absolute;
  border: none;
  border-radius: 6px;
  width: 30px;
  height: 30px;
  background: #ffffff00;
  transition: all 0.25s ease;
  padding: 0px 6px;
  color: rgba(59, 59, 59, 0.836);
  grid-row: 1;
  grid-column: 2;
  margin-left: 3px;
}

.input-full-screen-button:active {
  transform: scale(0.88);
}

.input-full-screen-button:deep(.icon.isFullInput) {
  width: 24px;
  height: 24px;
  transition: fill 0.25 ease;
  fill: #324f4c2b;
}

.input-full-screen-button:deep(.icon:not(.isFullInput)) {
  width: 24px;
  height: 24px;
  transition: fill 0.25 ease;
  fill: transparent;
}

.input-full-screen-button:deep(.icon:hover) {
  width: 24px;
  height: 24px;
  transition: fill 0.25 ease;
  fill: #324f4c2b;
}

.chat-config {
  opacity: 0.5;
  position: relative;
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 12px;
  width: 100%;
  max-width: calc(100%-96px);
  transition: all 0.28s cubic-bezier(0.23, 1, 0.32, 1);
}

.chat-config:hover {
  opacity: 1;
}

.model-provider {
  margin-left: 6px;
  position: relative;
  width: 22px;
  height: 22px;
  border-radius: 6px !important;
  border: 1px solid #547c8500 !important;
  background-color: rgba(255, 255, 255, 0) !important;
}

.model-provider::before {
  content: "";
  position: absolute;
  width: 24px;
  height: 24px;
  border-radius: 6px;
  border: 1px solid #547c8584;
  background-color: rgb(255, 255, 255);
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%) rotate(45deg);
  z-index: 1;
}

.model-provider:deep(*) {
  padding: 0px;
  z-index: 2;
}

.model-provider:deep(.n-base-selection) {
  width: 24px;
  height: 24px !important;
  min-height: 24px !important;
}

.model-provider:deep(.n-base-selection-label) {
  padding: auto;
  border: none;
  font-size: 12px !important;
  border-radius: 6px !important;
  background-color: rgba(98, 156, 174, 0) !important;
  box-shadow: none;
  width: 24px;
  height: 24px;
  align-items: center;
  font-size: 20px !important;
}

.model-provider:deep(.n-base-selection-input) {
  padding: 0px;
  border: none;
  font-size: 12px !important;
  border-radius: 6px !important;
  background-color: rgba(98, 156, 174, 0) !important;
  box-shadow: none;
  min-width: 24px;
  min-height: 24px;
  align-items: flex-start;
}

.model-select {
  transform: translateX(-24px);
}

.model-select:deep(.n-base-selection__border),
.model-provider:deep(.n-base-selection__border) {
  opacity: 0;
}

.model-select:deep(.n-base-selection__state-border),
.model-provider:deep(.n-base-selection__state-border) {
  opacity: 0;
}

.model-select {
  width: 100px !important;
  border: none !important;
  border-radius: 32px !important;
  color: white !important;
}

.model-select:deep(*) {
  color: white !important;
  align-items: center;
}

.model-select:not(.errorServer):deep(.n-base-selection) {
  width: 100px;
  height: 24px;
  border: 1px solid #5485801c !important;
  font-size: 12px !important;
  font-weight: bold;
  border-radius: 32px !important;
  background-color: rgba(98, 156, 174, 0.797) !important;
  box-shadow: none;
  min-height: 28px;
  color: white !important;
}

.model-select.errorServer:deep(.n-base-selection) {
  width: 100px;
  height: 24px;
  border: 1px solid #f35555bb !important;
  font-size: 12px !important;
  font-weight: bold;
  border-radius: 32px !important;
  background-color: #f35555ee !important;
  box-shadow: none;
  min-height: 28px;
  color: white !important;
}

.model-select:deep(.n-base-selection-label) {
  position: relative;
  color: white !important;
  height: 28px;
  background-color: rgba(98, 156, 174, 0) !important;
}

.model-select:deep(.n-base-selection-input) {
  padding: 6px 8px !important;
}

.model-select:deep(.n-base-selection-placeholder__inner) {
  color: rgba(255, 255, 255, 0.731) !important;
  font-weight: 500;
  font-size: 14px;
}

.apikey-button:not(.errorKey) {
  position: relative;
  border-left: 1px solid transparent;
  border-right: 1px solid #324f4c79;
  border-top: 1px solid #324f4c79;
  border-bottom: 1px solid #324f4c79;
  border-radius: 0 14px 14px 0;
  width: 52px;
  height: 28px;
  background-color: rgb(255, 255, 255);
  transition: all 0.25s ease;
  padding: 0px 6px;
  transform: translateX(-21px);
}

.apikey-button.errorKey {
  position: relative;
  border-left: 1px solid transparent;
  border-right: 1px solid #f3555583;
  border-top: 1px solid #f3555583;
  border-bottom: 1px solid #f3555583;
  border-radius: 0 14px 14px 0;
  width: 52px;
  height: 28px;
  background-color: rgb(255, 255, 255);
  box-shadow: 0px 0px 6px #f3555521;
  transition: all 0.25s ease;
  padding: 0px 6px;
  transform: translateX(-21px);
}

.select-button.yes,
.thinking-button.yes {
  position: relative;
  display: flex;
  flex-direction: row;
  border: 1px solid #1a8e77ed;
  border-radius: 16px;
  width: 100px;
  height: 30px;
  background: #23bba9cf;
  transition: all 0.25s ease;
  padding: 0px 6px;
  color: rgba(255, 255, 255, 0.836);
  margin: 0px;
  transform: translateX(-24px);
}

.select-button:not(.yes),
.thinking-button:not(.yes) {
  position: relative;
  display: flex;
  flex-direction: row;
  border: 1px solid #324f4c79;
  border-radius: 16px;
  width: 100px;
  height: 30px;
  background: #ffffff12;
  transition: all 0.25s ease;
  padding: 0px 6px;
  color: rgba(59, 59, 59, 0.749);
  margin: 0px;
  transform: translateX(-24px);
}

.select-button:active,
.thinking-button:active {
  transform: translateX(-24px) scale(0.8);
}

.select-button:not(.no_error) {
  border: 1px solid #f35555ee;
  background: #f35555bb;
}

.apikey-button:deep(.icon) {
  width: 28px;
  height: 28px;
  transition: fill 0.25 ease;
  padding-left: 16px;
}
.thinking-button:deep(.icon) {
  width: 16px;
  height:16px;
  transition: fill 0.25 ease;
}
.select-button:deep(.icon) {
  width: 18px;
  height: 18px;
  transition: fill 0.25 ease;
  margin-top: -1px;
}

/* 外层：真正的横向滚动容器 */
.file-path-scroll {
  flex: 1;
  min-width: 0;
  height: 30px;
  padding: 4px;
  max-width: calc(80% - 64px);
  align-items: center;
  align-content: center;
  overflow-x: auto;
  overflow-y: hidden;
}

/* 隐藏滚动条（Chrome / Electron） */
.file-path-scroll::-webkit-scrollbar {
  display: none;
}

/* Firefox */
.file-path-scroll {
  scrollbar-width: none;
  height: 22px;
  border-radius: 8px;
  padding: 0px 3px;
}

/* 内层：横向排列 tag */
.file-path-tag-wrapper {
  display: flex;
  flex-wrap: nowrap;       /* 禁止换行 */
  gap: 4px;
  white-space: nowrap;
  align-self: center;
  height: 22px;
  margin-top: -2px;
  border-radius: 8px;
}

.file-tag {
  border: none;
  border-radius: 8px;
  transition: all 0.24s ease;
}

.file-tag:hover {
  transform: scale(1.02);
  border-radius: 8px;
}
</style>
