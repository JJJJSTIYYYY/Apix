<template>
  <el-container>
    <el-aside class="aside-area">
      <HomePage />
    </el-aside>

    <el-main
      v-if="showPage"
      ref="page"
      class="main-area"
    >
    <div class="setting-page-wrapper">
      <div class="title-tag-wrapper">
        <div style="width: 100%; max-width: 1000px; margin-bottom: 40px;">
          <div class="apix-banner">
            <div class="corner-accent"></div>
            
            <div class="banner-content">
              
              <div class="banner-text">
                <div class="banner-title-wrapper">
                  <h1 class="banner-title">APIX</h1>
                  <span class="version-tag">{{ apix_client_version }}</span>
                </div>
                
                <div class="divider"></div>
                
                <p class="banner-subtitle">
                  一款<strong>兼容多引擎</strong>的 Agent 平台，支持处理 
                  <strong>网页制作</strong>、<strong>代码编写</strong>、<strong>文档处理</strong>、<strong>海报设计</strong> 等复杂任务
                </p>
                
                <div class="banner-meta">
                  <a class="dev-badge" href="https://github.com/JJJJSTIYYYY/Apix">Github</a>
                  
                  <div class="engine-tags">
                    <span class="engine-tag">Ollama</span>
                    <span class="engine-tag">OpenAI</span>
                    <span class="engine-tag">DeepSeek</span>
                    <span class="engine-tag">MoonShot</span>
                    <span class="engine-tag">更多引擎等待兼容...</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
      <div
        class="app-layout"
      >
        <!-- 组1: 界面设置 -->
        <div class="setting-group">
          <div class="group-divider">
            <span class="group-label">界面设置</span>
          </div>
      
          <div class="setting-card">
            <div class="setting-title">在AI消息中显示工具调用标签</div>
            <div class="setting-control">
              <div class="setting-info">
                开启后实时显示AI当前正在调用的工具名称。
              </div>
              <div class="mode-switch">
                <div class="slider" :class="{ right: store.config.showToolLabels }" />

                <button
                  class="off-select"
                  :class="{ active: !store.config.showToolLabels }"
                  @click="switchMode('showToolLabels', 'off')"
                >
                  Off
                </button>

                <button
                  class="on-select"
                  :class="{ active: store.config.showToolLabels }"
                  @click="switchMode('showToolLabels', 'on')"
                >
                  On
                </button>
              </div>
            </div>
          </div>
      
          <div class="setting-card">
            <div class="setting-title">启用深色主题   <span class="setting-label">Beta</span></div>
            <div class="setting-control">
              <div class="setting-info">
                开启有颜色主题可能适配不佳。
              </div>
              <div class="mode-switch">
                <div class="slider" :class="{ right: store.config.dark_theme }" />

                <button
                  class="off-select"
                  :class="{ active: !store.config.dark_theme }"
                  @click="switchMode('dark_theme', 'off')"
                >
                  Off
                </button>

                <button
                  class="on-select"
                  :class="{ active: store.config.dark_theme }"
                  @click="switchMode('dark_theme', 'on')"
                >
                  On
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- 组2: 数据管理 -->
        <div class="setting-group">
          <div class="group-divider">
            <span class="group-label">数据管理</span>
          </div>
          <!-- Reset -->
          <div class="setting-card">
            <div class="setting-title">重载预设卡片</div>
            <div class="setting-control">
              <div class="setting-info">
                恢复预设卡片到初始状态，已修改或新增的卡片不会被删除。
              </div>
              <el-button
                type="primary"
                off
                size="default"
                @click="resetPresetCard"
                class="confirm-button"
              >
                恢复
              </el-button>
            </div>
          </div>

          <!-- Clear cache -->
          <div class="setting-card">
            <div class="setting-title">打开缓存文件夹</div>
            <div class="setting-control">
              <div class="setting-info">
                打开保存卡片以及任务的文件夹位置。
              </div>
              <el-button
                type="primary"
                off
                size="default"
                @click="openCacheDir"
                class="confirm-button"
              >
                打开
              </el-button>
            </div>
          </div>
        </div>

        <!-- 组3: 网络代理 -->
        <div class="setting-group">
          <div class="group-divider">
            <span class="group-label">网络代理</span>
          </div>
          <!-- Port -->
          <div class="setting-card">
            <div class="setting-title">为AI服务设置全局网络代理</div>
            <div class="setting-control">
              <el-input
                placeholder="http://expmale.com:7890 ,http://expmale.com:7890 "
                v-model="store.config.httpProxyUrl"
                class="line-input"
              >
              </el-input>
              <el-button
                type="primary"
                off
                size="default"
                @click="setNetProxy"
                class="confirm-button"
              >
                保存
              </el-button>
            </div>
          </div>

          <div class="setting-card">
            <div class="setting-title">全局代理排除以下地址</div>
            <div class="setting-control">
              <el-input
                placeholder="localhost,127.0.0.1,expmale.com"
                v-model="store.config.excludeUrl"
                class="line-input"
              >
              </el-input>
              <el-button
                type="primary"
                off
                size="default"
                @click="setNetProxy"
                class="confirm-button"
              >
                保存
              </el-button>
            </div>
          </div>
        </div>

        <!-- 组4: AI设置 -->
        <div class="setting-group">
          <div class="group-divider">
            <span class="group-label">权限设置</span>
          </div>
          <div class="setting-card">
            <div class="setting-title">允许 Agent 操作文件</div>
            <div class="setting-control">
              <div class="setting-info">允许Agent对工作区文件进行修改，包括读取用户上传文件、查看工作区目录、新建或<strong>删改</strong>工作区文件。</div>
              <div class="mode-switch">
                <div class="slider" :class="{ right: store.config.fileOpration }" />

                <button
                  class="off-select"
                  :class="{ active: !store.config.fileOpration }"
                  @click="switchMode('fileOpration', 'off')"
                >
                  Off
                </button>

                <button
                  class="on-select"
                  :class="{ active: store.config.fileOpration }"
                  @click="switchMode('fileOpration', 'on')"
                >
                  On
                </button>
              </div>
            </div>
          </div>
          <div class="setting-card">
            <div class="setting-title">允许 Agent 执行命令</div>
            <div class="setting-control">
              <div class="setting-info">开放命令行权限给Agent，允许Agent在沙箱内执行命令。</div>
              <div class="mode-switch">
                <div class="slider" :class="{ right: store.config.commandOpration }" />

                <button
                  class="off-select"
                  :class="{ active: !store.config.commandOpration }"
                  @click="switchMode('commandOpration', 'off')"
                >
                  Off
                </button>

                <button
                  class="on-select"
                  :class="{ active: store.config.commandOpration }"
                  @click="switchMode('commandOpration', 'on')"
                >
                  On
                </button>
              </div>
            </div>
          </div>
          <div class="setting-card">
            <div class="setting-title">允许 Agent 浏览网页</div>
            <div class="setting-control">
              <div class="setting-info" :class="{ danger_info: store.config.webSearch && store.config.knowledgeRetrieval}">
                允许Agent使用网络搜索工具在互联网上搜索信息。
              </div>
              <div class="mode-switch">
                <div class="slider" :class="{ right: store.config.webSearch }" />

                <button
                  class="off-select"
                  :class="{ active: !store.config.webSearch }"
                  @click="switchMode('webSearch', 'off')"
                >
                  Off
                </button>

                <button
                  class="on-select"
                  :class="{ active: store.config.webSearch }"
                  @click="switchMode('webSearch', 'on')"
                >
                  On
                </button>
              </div>
            </div>
          </div>
          <div class="setting-card">
            <div class="setting-title">允许 Agent 访问知识库</div>
            <div class="setting-control">
              <div class="setting-info" :class="{ danger_info: store.config.webSearch && store.config.knowledgeRetrieval }">
                允许Agent使用知识库检索工具在知识库中搜索信息。与网络搜索能力同时开启时，会降低模型知识库检索表现。
              </div>
              <div class="mode-switch">
                <div class="slider" :class="{ right: store.config.knowledgeRetrieval }" />

                <button
                  class="off-select"
                  :class="{ active: !store.config.knowledgeRetrieval }"
                  @click="switchMode('knowledgeRetrieval', 'off')"
                >
                  Off
                </button>

                <button
                  class="on-select"
                  :class="{ active: store.config.knowledgeRetrieval }"
                  @click="switchMode('knowledgeRetrieval', 'on')"
                >
                  On
                </button>
              </div>
            </div>
          </div>
          <div class="setting-card">
            <div class="setting-title">允许 Agent 使用技能包</div>
            <div class="setting-control">
              <div class="setting-info">允许Agent加载技能包，获取技能包扩展。</div>
              <div class="mode-switch">
                <div class="slider" :class="{ right: store.config.skillLoad }" />

                <button
                  class="off-select"
                  :class="{ active: !store.config.skillLoad }"
                  @click="switchMode('skillLoad', 'off')"
                >
                  Off
                </button>

                <button
                  class="on-select"
                  :class="{ active: store.config.skillLoad }"
                  @click="switchMode('skillLoad', 'on')"
                >
                  On
                </button>
              </div>
            </div>
          </div>

          <div class="setting-card">
            <div class="setting-title">启用模型视觉输入</div>
            <div class="setting-control">
              <div class="setting-info">
                开启后，图片将发送给模型进行理解，而不使用OCR工具提取文字。系统会自动检测模型是否具备视觉处理能力。
              </div>
              <div class="mode-switch">
                <div class="slider" :class="{ right: store.config.visionOn }" />

                <button
                  class="off-select"
                  :class="{ active: !store.config.visionOn }"
                  @click="switchMode('visionOn', 'off')"
                >
                  Off
                </button>

                <button
                  class="on-select"
                  :class="{ active: store.config.visionOn }"
                  @click="switchMode('visionOn', 'on')"
                >
                  On
                </button>
              </div>
            </div>
          </div>

          <div class="setting-card">
            <div class="setting-title">启用 Agent 子代理   <span class="setting-label">Beta</span></div>
            <div class="setting-control">
              <div class="setting-info" :class="{ danger_info: store.config.agentAssign }">
                开启智能体子代理模式，提供异步任务处理能力，不推荐在个人PC本地部署时开启。
              </div>
              <div class="mode-switch">
                <div class="slider" :class="{ right: store.config.agentAssign }" />

                <button
                  class="off-select"
                  :class="{ active: !store.config.agentAssign }"
                  @click="switchMode('agentAssign', 'off')"
                >
                  Off
                </button>

                <button
                  class="on-select"
                  :class="{ active: store.config.agentAssign }"
                  @click="switchMode('agentAssign', 'on')"
                >
                  On
                </button>
              </div>
            </div>
          </div>

          <div class="setting-card">
            <div class="setting-title">启用 Agent-Term 蜂群模式   <span class="setting-label">Beta</span></div>
            <div class="setting-control">
              <div class="setting-info" :class="{ danger_info: store.config.agentSwarm }">
                开启多智能体协作模式，不推荐在个人PC本地部署时开启。开启此项默认将 <strong>Agent 子代理</strong> 视为已开启。
              </div>
              <div class="mode-switch">
                <div class="slider" :class="{ right: store.config.agentSwarm }" />

                <button
                  class="off-select"
                  :class="{ active: !store.config.agentSwarm }"
                  @click="switchMode('agentSwarm', 'off')"
                >
                  Off
                </button>

                <button
                  class="on-select"
                  :class="{ active: store.config.agentSwarm }"
                  @click="switchMode('agentSwarm', 'on')"
                >
                  On
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- 组4: AI设置 -->
        <div class="setting-group">
          <div class="group-divider">
            <span class="group-label">记忆设置</span>
          </div>

          <div class="setting-card">
            <div class="setting-title">开启长期记忆</div>
            <div class="setting-control">
              <div class="setting-info"  :class="{ danger_info: store.config.longtermMemory }">
                不推荐在个人PC本地部署时开启, 算力不足时可能导致Agent运行缓慢。
              </div>
              <div class="mode-switch">
                <div class="slider" :class="{ right: store.config.longtermMemory }" />

                <button
                  class="off-select"
                  :class="{ active: !store.config.longtermMemory }"
                  @click="switchMode('longtermMemory', 'off')"
                >
                  Off
                </button>

                <button
                  class="on-select"
                  :class="{ active: store.config.longtermMemory }"
                  @click="switchMode('longtermMemory', 'on')"
                >
                  On
                </button>
              </div>
            </div>
          </div>

          <div class="setting-card">
            <div class="setting-title">当上下文达到窗口大小限制时自动总结上下文</div>
            <div class="setting-control">
              <div class="setting-info">需同步设置上下文总结触发阈值与保留的窗口长度</div>
              <div class="mode-switch">
                <div class="slider" :class="{ right: store.config.shorttermMemory }" />

                <button
                  class="off-select"
                  :class="{ active: !store.config.shorttermMemory }"
                  @click="switchMode('shorttermMemory', 'off')"
                >
                  Off
                </button>

                <button
                  class="on-select"
                  :class="{ active: store.config.shorttermMemory }"
                  @click="switchMode('shorttermMemory', 'on')"
                >
                  On
                </button>
              </div>
            </div>
          </div>

          <div class="setting-card">
            <div v-if="store.config.shorttermMemory" class="setting-title">上下文总结触发阈值</div>
            <div v-else class="setting-title">上下文截断触发阈值</div>
            <div class="setting-control">
              <div class="setting-info">过小的触发阈值可能导致Agent陷入死循环，最小生效值为16</div>
              <el-input-number 
                v-model="summaryMessages"
                controls-position="right" 
                class="number-input"
              />
              <el-button
                type="primary"
                off
                size="default"
                @click="storeMessageSummary"
                class="confirm-button"
              >
                保存
              </el-button>
            </div>
          </div>

          <div class="setting-card">
            <div v-if="store.config.shorttermMemory" class="setting-title">总结时保留的上下文长度</div>
            <div v-else class="setting-title">截断时保留的上下文长度</div>
            <div class="setting-control">
              <div class="setting-info">过小的保留长度可能导致Agent陷入死循环，最小生效值为4</div>
              <el-input-number 
                v-model="keepMessages"
                controls-position="right" 
                class="number-input"
              />
              <el-button
                type="primary"
                off
                size="default"
                @click="storeKeepNotSummary"
                class="confirm-button"
              >
                保存
              </el-button>
            </div>
          </div>
        </div>

        <!-- 组5: 联网搜索配置 -->
        <div class="setting-group">
          <div class="group-divider">
            <span class="group-label">联网搜索</span>
          </div>
          <!-- Online search -->
          <div class="setting-card">
            <div class="setting-title">配置关键词搜索引擎</div>
            <div class="setting-control">
              <el-select v-model="linkProvider" placeholder="Auto" class="select-input">
                <el-option
                  v-for="item in linkProviderOptions"
                  :key="item.value"
                  :label="item.label"
                  :value="item.value"
                  :disabled="item.disabled"
                />
              </el-select>
              <el-button
                type="primary"
                off
                size="default"
                @click="storeLinkProvider"
                class="confirm-button"
              >
                保存
              </el-button>
            </div>
          </div>

          <div class="setting-card">
            <div class="setting-title">配置关键词搜索引擎API-Key</div>
            <div class="setting-control">
              <el-input
                v-model="linkApiKey"
                type="password"
                placeholder="Your API key"
                show-password
                class="line-input"
              />
              <el-button
                type="primary"
                off
                size="default"
                @click="storeLinkApiKey"
                class="confirm-button"
              >
                保存
              </el-button>
            </div>
          </div>

          <div class="setting-card">
            <div class="setting-title">配置网页内容搜索引擎</div>
            <div class="setting-control">
              <el-select v-model="contentProvider" placeholder="Auto" class="select-input">
                <el-option
                  v-for="item in contentPoviderOptions"
                  :key="item.value"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
              <el-button
                type="primary"
                off
                size="default"
                @click="storeContentPovider"
                class="confirm-button"
              >
                保存
              </el-button>
            </div>
          </div>

          <div class="setting-card">
            <div class="setting-title">配置网页内容搜索API-Key</div>
            <div class="setting-control">
              <el-input
                v-model="contentApiKey"
                type="password"
                placeholder="Your API key"
                show-password
                class="line-input"
              />
              <el-button
                type="primary"
                off
                size="default"
                @click="storeContentApiKey"
                class="confirm-button"
              >
                保存
              </el-button>
            </div>
          </div>

          <div class="setting-card">
            <div class="setting-title">配置AI联网搜索内容过滤规则</div>
            <div class="setting-control">
              <el-select v-model="webContentFilter" placeholder="规则过滤 (默认)" class="select-input">
                <el-option
                  v-for="item in webContentFilterOptions"
                  :key="item.value"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
              <el-button
                type="primary"
                off
                size="default"
                @click="storeWebContentFilter"
                class="confirm-button"
              >
                保存
              </el-button>
            </div>
          </div>

          <div class="setting-card">
            <div class="setting-title">允许的域名关键字</div>
            <div class="setting-control">
              <el-input
                placeholder="选择一个配置文件或直接输入 e.g: wiki,github,arxiv"
                v-model="store.config.excludeWebUrl"
                class="line-input"
              >
              </el-input>
              <el-button
                type="primary"
                off
                size="default"
                @click=""
                class="confirm-button"
              >
                打开
              </el-button>
            </div>
          </div>
        </div>

        <!-- 组6: 功能开关 -->
        <div class="setting-group">
          <div class="group-divider">
            <span class="group-label">其他设置</span>
          </div>
          <div class="setting-card">
            <div class="setting-title">单轮生成中LLM调用轮次预警值</div>
            <div class="setting-control">
              <div class="setting-info">超出阈值时将提醒Agent加快处理进度</div>
              <el-input-number 
                v-model="tokenLimit"
                controls-position="right" 
                class="number-input"
              />
              <el-button
                type="primary"
                off
                size="default"
                @click="storeTokenLimit"
                class="confirm-button"
              >
                保存
              </el-button>
            </div>
          </div>

          <div class="setting-card">
            <div class="setting-title">异步工具返回时唤醒AI</div>
            <div class="setting-control">
              <div class="setting-info">
                异步工具返回结果时主动唤醒AI (若AI正在生成, 将会打断)。
              </div>
              <div class="mode-switch">
                <div class="slider" :class="{ right: store.config.toolsInvokeAi }" />

                <button
                  class="off-select"
                  :class="{ active: !store.config.toolsInvokeAi }"
                  @click="switchMode('toolsInvokeAi', 'off')"
                >
                  Off
                </button>

                <button
                  class="on-select"
                  :class="{ active: store.config.toolsInvokeAi }"
                  @click="switchMode('toolsInvokeAi', 'on')"
                >
                  On
                </button>
              </div>
            </div>
          </div>

          <div class="setting-card">
            <div class="setting-title">将过去的思维链以及工具返回内容回传接口</div>
            <div class="setting-control">
              <div class="setting-info">
                工具的返回结果通常会携带大量的文本信息，极大增加Token消耗，如果是本地模型，将同时增加GPU的计算负担，某些供应商需要开启此选项。
              </div>
              <div class="mode-switch">
                <div class="slider" :class="{ right: store.config.remainToolsCache }" />

                <button
                  class="off-select"
                  :class="{ active: !store.config.remainToolsCache }"
                  @click="switchMode('remainToolsCache', 'off')"
                >
                  Off
                </button>

                <button
                  class="on-select"
                  :class="{ active: store.config.remainToolsCache }"
                  @click="switchMode('remainToolsCache', 'on')"
                >
                  On
                </button>
              </div>
            </div>
          </div>

          <div class="setting-card">
            <div class="setting-title">重置模型能力缓存</div>
            <div class="setting-control">
              <div class="setting-info">
                重置服务器对于模型能力的缓存信息，如果您发现支持视觉输入的模型错误的使用了OCR工具提取文字，可尝试此功能。
              </div>
              <el-button
                type="primary"
                off
                size="default"
                @click="clearVisionCache()"
                class="confirm-button"
              >
                重置
              </el-button>
            </div>
          </div>

          <div class="setting-card">
            <div class="setting-title">开启纯对话模式</div>
            <div class="setting-control">
              <div class="setting-info" :class="{ danger_info: store.config.pureChat }">
                开启此选项将禁用Agent全部工具（含生成计划、多模态、联网搜索、文件操作等），适用于无工具调用能力的模型。
              </div>
              <div class="mode-switch">
                <div class="slider" :class="{ right: store.config.pureChat }" />

                <button
                  class="off-select"
                  :class="{ active: !store.config.pureChat }"
                  @click="switchMode('pureChat', 'off')"
                >
                  Off
                </button>

                <button
                  class="on-select"
                  :class="{ active: store.config.pureChat }"
                  @click="switchMode('pureChat', 'on')"
                >
                  On
                </button>
              </div>
            </div>
          </div>
          
          <div class="setting-card">
            <div class="setting-title">模型温度百分比</div>
            <div class="setting-control">
              <el-slider
                v-model="store.config.modelTemp"
                :min="0"
                :max="100"
                @change="changeModelTemp"
              />
              <span class="setting-value">{{ store.config.modelTemp }}%</span>
            </div>
          </div>
        </div>

      </div>

      <!-- Logout -->
      <div class="logout-btn-wrapper">
        <el-button
          type="danger"
          off
          @click="onLogout"
        >
          Logout {{ username }}
        </el-button>
      </div>
      </div>
    </el-main>
</el-container>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'

import HomePage from './homePage.vue'
import { useAppCacheData } from '../store/app'
import { useAuthStore } from "../store/auth"
import { apix_client_version, defaultCards, setHighlightTheme } from '../store/globalData.js'
import { ConfirmDialog } from './component/comp/confirmDialog.js'

const router = useRouter()
const store = useAppCacheData()
const authStore = useAuthStore()
const username = ref("")

/* Layout */
const pageHeight = ref(window.innerHeight - 30)
const showPage = ref(false)

const updatePageHeight = () => {
  pageHeight.value = window.innerHeight - 30
}

onMounted(async () => {
  window.addEventListener('resize', updatePageHeight)
  showPage.value = true

  await authStore.restore()
  username.value = authStore.user.username
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', updatePageHeight)
})

/* Settings */
const changeModelTemp = (value) => {
  store.saveAppConfig('modelTemp', value)
}

/* Proxy */
const setNetProxy = async () => {
  store.saveAppConfig('httpProxyUrl', store.config.httpProxyUrl)
  try {
    const res = await window.api.setProxy(
      store.config.httpProxyUrl,
      store.config.httpsProxyUrl,
      store.config.excludeUrl
    )
    ElMessage.success('代理已保存')
  } catch (err) {
    ElMessage.error('代理保存失败')
    console.error(err)
  }
}

/* Reset cards */
const resetPresetCard = async () => {
  const presets = defaultCards
  const cardMap = new Map(store.cards.map(c => [c.id, c]))

  let index = 0
  presets.forEach(preset => {
    if (cardMap.has(preset.id)) {
      const exist = cardMap.get(preset.id)
      Object.assign(exist, preset)

      const oldIndex = store.cards.indexOf(exist)
      if (oldIndex !== index) {
        store.cards.splice(oldIndex, 1)
        store.cards.splice(index, 0, exist)
      }
    } else {
      store.cards.splice(index, 0, preset)
    }
    index++
  })

  await store.saveCards()
  ElMessage.success('已恢复预设')
}

const openCacheDir = async () => {
  try {
    await window.api.openCacheDir()
  }catch (err) {
    ElMessage.error('打开失败')
    console.error("error to open cache directory: ", err)
  }
}

const clearVisionCache = async () => {
  try {
    await ConfirmDialog.confirm(
      `确定模型能力清除缓存？`,
      '重置确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )

    try {
      await window.api.clearVisionCache()
      ElMessage.success('已重置')
    }catch (err) {
      ElMessage.error('重置失败')
      console.error("error to restore vision_cache: ", err)
    }
  } catch (err) {
  }
}

/* Token limit */
const tokenLimit = ref(store.config.tokenLimit || 0)
function storeTokenLimit() {
  store.config.tokenLimit = tokenLimit.value
  store.saveAppConfig('tokenLimit', tokenLimit.value)
  ElMessage.success('保存成功')
}

/* Summary messages */
const summaryMessages = ref(store.config.messageSummary || 0)
function storeMessageSummary() {
  store.config.messageSummary = summaryMessages.value
  store.saveAppConfig('messageSummary', summaryMessages.value)
  ElMessage.success('保存成功')
}
const keepMessages = ref(store.config.keepNotSummary || 0)
function storeKeepNotSummary() {
  store.config.keepNotSummary = keepMessages.value
  store.saveAppConfig('keepNotSummary', keepMessages.value)
  ElMessage.success('保存成功')
}

/* Search Links (Urls) Provider */
const linkProvider = ref(store.config.linkProvider || '')
const linkProviderOptions = [
  {
    value: '',
    label: 'Auto',
  },
  {
    value: 'duckduckgo',
    label: 'DuckDuckGo',
  },
  {
    value: 'bing',
    label: 'Bing',
  },
  {
    value: 'bocha',
    label: 'Bocha',
  },
  {
    value: 'google',
    label: 'Google',
    disabled: true,
  },
  {
    value: 'searxng',
    label: 'Searxng',
    disabled: true,
  },
  {
    value: 'tavily',
    label: 'Tavily',
  },
  {
    value: 'uniFuncs',
    label: 'UniFuncs',
  }
]
function storeLinkProvider() {
  store.config.linkProvider = linkProvider.value
  store.saveAppConfig('linkProvider', linkProvider.value)
  ElMessage.success('保存成功')
}
const linkApiKey = ref(store.config.linkApiKey || '')
function storeLinkApiKey() {
  store.config.linkApiKey = linkApiKey.value
  store.saveAppConfig('linkApiKey', linkApiKey.value)
  ElMessage.success('保存成功')
}

/* Search Contents Provider */
const contentProvider = ref(store.config.contentProvider || '')
const contentPoviderOptions = [
  {
    value: '',
    label: 'Auto',
  },
  {
    value: 'tavily',
    label: 'Tavily',
  },
  {
    value: 'crawl4ai',
    label: 'Crawl4AI',
  },
  {
    value: 'jina',
    label: 'Jina',
  }
]
function storeContentPovider() {
  store.config.contentProvider = contentProvider.value
  store.saveAppConfig('contentProvider', contentProvider.value)
  ElMessage.success('保存成功')
}

const contentApiKey = ref(store.config.contentApiKey || '')
function storeContentApiKey() {
  store.config.contentApiKey = contentApiKey.value
  store.saveAppConfig('contentApiKey', contentApiKey.value)
  ElMessage.success('保存成功')
}

/* Search Contents filter */
const webContentFilter = ref(store.config.webContentFilter || '')
const webContentFilterOptions = [
  {
    value: 'rule',
    label: '规则过滤 (默认)',
  },
  {
    value: 'llm',
    label: '大模型过滤',
  },
  {
    value: 'none',
    label: '无过滤',
  }
]
function storeWebContentFilter() {
  store.config.webContentFilter = webContentFilter.value
  store.saveAppConfig('webContentFilter', webContentFilter.value)
  ElMessage.success('保存成功')
}

/* Generic boolean mode switch */
const switchMode = (key: keyof typeof store.config, target: 'on' | 'off') => {
  const value = target === 'on'

  // Update reactive config
  store.config[key] = value as any

  // Persist to local storage / backend
  store.saveAppConfig(key as string, value)
}

/* Logout */
const onLogout = async () => {
  try {
    await ConfirmDialog.confirm(
      `确定登出账户 "${username.value}" 吗？`,
      '登出确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )
    authStore.logout()
    window.api.closeWebsocket()
    store.messages.length = 0
    router.replace("/loginPage")
  } catch (err) {
  }
}
</script>

<style scoped>
:deep(.el-select__wrapper .el-tooltip__trigger .el-tooltip__trigger) {
  display: block !important;
  opacity: 1 !important;
}

:deep(.el-slider__bar) {
  background-color:var(--apix-primary-color);
}

:deep(.el-slider__button) {
  background-color:var(--apix-primary-light);
  border: 2px solid var(--apix-primary-active);
  border-radius: var(--apix-button-border-radius);
}

:deep(.el-slider__button:hover) {
  width: 24px;
  transform: none;
}

:deep(.el-popper:deep(*)) {
  color: transparent;
}

span.el-popper__arrow {
  display: none;
}

:deep(.el-slider__button:active) {
  transform: scale(1.2);
  overflow: hidden;
  border: 2px solid color-mix(in srgb, var(--apix-primary-color) 25%, transparent);
  -webkit-backdrop-filter: saturate(180%) blur(16px);
  backdrop-filter: saturate(180%) blur(3px);
  transition: all 0.3s var(--apix-cubic-bezier);
  background-color: color-mix(in srgb, var(--apix-panel-base-layer-background) 30%, transparent);
  color: var(--apix-info-dark-text);
}

.setting-page-wrapper {
  position: relative;
  padding: 16px;
  display: flex;
  flex-direction: column;
  align-items: center;
  overflow: scroll;
  max-height: calc(100vh - 32px - 36px);
}

.title-tag-wrapper {
  position: relative;
  width: 100%;
  height: fit-content;
  justify-content: center;
  display: flex;
  align-items: center;
  opacity: 0.95;
}

.app-layout {
  padding: 24px 32px;
  padding-bottom: 100px;
  display: flex;
  flex-direction: column;
  gap: 24px;
  background: transparent;
  width: 1000px;
  max-width: 1200px;
}

.setting-group {
  display: grid;
  width: 100%;
  grid-template-columns: 50% 50%;
  gap: 18px;
  width: 100%;
  padding-top: 8px;
  margin-top: 8px;
}

.group-divider {
  grid-column: 1 / -1;
  display: flex;
  align-items: center;
  margin-bottom: 4px;
  gap: 6px
}

.group-label {
  position: relative;
  width: 100%;
  height: 30px;
  font-size: 18px;
  font-weight: 600;
  color: var(--apix-primary-color);
  text-transform: uppercase;
  letter-spacing: 0.8px;
  padding: 0 12px;
  border-left: 3px solid var(--apix-primary-color);
}

.setting-card {
  position: relative;
  padding: 16px 18px;
  border-radius: var(--apix-border-radius-base);
  height: 64px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  background: var(--apix-panel-layer-3-background);
  box-shadow: var(--apix-shadow-layer-1);
  transition: transform 0.2s var(--apix-cubic-bezier),
    box-shadow 0.2s var(--apix-cubic-bezier);
}

.setting-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--apix-shadow-layer-3);
}

.setting-label {
  margin-right: 6px;
  padding: 2px 6px;
  color: #059669;
  border: 1px solid rgba(5, 150, 105, 0.1);
  background: rgba(5, 150, 105, 0.05);
  border-radius: 16px;
  font-size: 10px;
}

.danger-label {
  margin-right: 6px;
  padding: 2px 6px;
  color: #960505;
  border: 1px solid rgba(150, 22, 5, 0.1);
  background: rgba(150, 22, 5, 0.05);
  border-radius: 16px;
  font-size: 10px;
}

.setting-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--apix-darkest-color);
  position: relative;
}

.setting-control {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 16px;
  width: calc(100% - 78px);
}

.setting-info {
  font-size: 12px;
  color: var(--apix-secondary-dark-color);
  position: relative;
  transition: color 0.25s var(--apix-cubic-bezier);
}

.danger_info {
  color: var(--apix-danger-color);
}

.confirm-button {
  position: absolute;
  right: 14px;
  width: 64px;
  color: var(--apix-primary-color);
  border: 2px solid var(--apix-primary-light);
  transition: color 0.22s var(--apix-cubic-bezier),
    border 0.22s var(--apix-cubic-bezier);
  background-color: var(--apix-primary-lighter);
  border-radius: var(--apix-button-border-radius);
}

.confirm-button:hover {
  color: var(--apix-primary-active);
  border: 2px solid var(--apix-primary-light-dark);
}

.setting-value {
  width: 44px;
  text-align: right;
  font-size: 13px;
  color: #5a6a6a;
}

.line-input {
  width: 100%;
}

.line-input :deep(.el-input) {
  flex: 1;
  min-width: 0;
  height: 38px !important;
  transform-origin: center;
  transform: scale(1);
  transition: transform 0.22s var(--apix-cubic-bezier);
}

.line-input :deep(.el-input__wrapper) {
  height: 38px !important;
  padding: 0 12px 0 10px;
  background: transparent;
  background-color: var(--apix-panel-layer-4-background);
  border: none;
  border-radius: var(--apix-border-radius-base);
  box-shadow: none;
  transition: all 0.13s var(--apix-cubic-bezier);
}

.number-input {
  width: 100%;
}

/* 输入框基础样式 - 青绿色主题边框 */
.number-input:deep(.el-input__wrapper) {
  background: color-mix(in srgb, var(--apix-primary-color) 5%, transparent);
  border: 2px solid color-mix(in srgb, var(--apix-primary-color) 25%, transparent);
  border-radius: 999px;
  padding: 0 12px;
  box-shadow: none;
  transition: all 0.3s cubic-bezier(0.215, 0.61, 0.355, 1);
}

.number-input:deep(.el-input__wrapper:hover),
.number-input:deep(.el-input__wrapper.is-hover) {
  border-color: color-mix(in srgb, var(--apix-primary-color) 50%, transparent) !important;
  background: color-mix(in srgb, var(--apix-primary-active) 8%, transparent) !important;
  box-shadow: none !important;
}

.number-input:deep(.el-input__wrapper:has(.el-input-number__increase:hover)),
.number-input:deep(.el-input__wrapper:has(.el-input-number__decrease:hover)) {
  border-color: color-mix(in srgb, var(--apix-primary-color) 50%, transparent) !important;
  box-shadow: none !important;
}

.number-input:deep(.el-input__wrapper.is-focus) {
  border-color: color-mix(in srgb, var(--apix-primary-active) 53%, transparent) !important;
  background: color-mix(in srgb, var(--apix-primary-color) 10%, transparent);
  box-shadow: none !important;
}

/* 输入文字左对齐 */
.number-input:deep(.el-input__inner) {
  text-align: left;
  color: var(--apix-link-color);
  font-weight: 500;
  height: 34px;
  line-height: 34px;
  padding-right: 70px;
}

/* 控制按钮 - 圆形青绿色主题 */
.number-input:deep(.el-input-number__increase),
.number-input:deep(.el-input-number__decrease) {
  background: color-mix(in srgb, var(--apix-primary-color) 5%, transparent);
  border: none;
  color: var(--apix-link-color);
  width: 26px;
  height: 26px;
  font-size: 12px;
  font-weight: bold;
  display: flex;
  align-items: center;
  justify-content: center;
  position: absolute;
  right: 8px;
  transition: all 0.3s cubic-bezier(0.215, 0.61, 0.355, 1);
}

/* 增加按钮在上，减少按钮在下 */
.number-input:deep(.el-input-number__increase) {
  border-radius: 0px 16px 0px 0px;
  right: 3px;
  top: 3px;
  height: 16px;
}

.number-input:deep(.el-input-number__decrease) {
  border-radius: 0px 0px 16px 0px;
  right: 3px;
  bottom: 3px;
  height: 16px;
}

/* 按钮悬浮 */
.number-input:deep(.el-input-number__increase:hover),
.number-input:deep(.el-input-number__decrease:hover) {
  background: color-mix(in srgb, var(--apix-primary-active) 15%, transparent);
  border-color: color-mix(in srgb, var(--apix-primary-color) 50%, transparent);
}

/* 按钮点击 */
.number-input:deep(.el-input-number__increase:active),
.number-input:deep(.el-input-number__decrease:active) {
  background: color-mix(in srgb, var(--apix-primary-color) 24%, transparent);
  transform: scale(0.95);
}

/* 禁用状态 */
.number-input:deep(.el-input-number__increase.is-disabled),
.number-input:deep(.el-input-number__decrease.is-disabled) {
  background: transparent;
  border-color: color-mix(in srgb, var(--apix-border-disabled) 30%, transparent);
  color: var(--apix-secondary-light-color);
  cursor: not-allowed;
  transform: none;
}

.select-input {
  width: 100%;
}

/* 外层输入框 */
.select-input:deep(.el-select__wrapper) {
  background: color-mix(in srgb, var(--apix-primary-color) 5%, transparent);
  border: 2px solid color-mix(in srgb, var(--apix-primary-color) 25%, transparent);
  border-radius: 999px;
  padding: 0 14px;
  min-height: 36px;
  box-shadow: none;
  transition: all 0.3s cubic-bezier(0.215, 0.61, 0.355, 1);
}

/* hover */
.select-input:deep(.el-select__wrapper:hover) {
  border-color: color-mix(in srgb, var(--apix-primary-color) 50%, transparent) !important;
  background: color-mix(in srgb, var(--apix-primary-active) 8%, transparent) !important;
  box-shadow: none !important;
}

/* focus */
.select-input:deep(.el-select__wrapper.is-focused) {
  border-color: color-mix(in srgb, var(--apix-primary-active) 53%, transparent) !important;
  background: color-mix(in srgb, var(--apix-primary-color) 10%, transparent);
  box-shadow: none !important;
}

/* 文字区域 */
.select-input:deep(.el-select__selection) {
  color: var(--apix-link-color);
  font-weight: 500;
}

/* placeholder */
.select-input:deep(.el-select__placeholder) {
  color: color-mix(in srgb, var(--apix-link-color) 65%, transparent);
}

/* 选中值 */
.select-input:deep(.el-select__selected-item) {
  color: var(--apix-link-color);
  font-weight: 500;
}

/* 下拉箭头 */
.select-input:deep(.el-select__caret) {
  color: var(--apix-link-color);
  font-size: 14px;
  transition: transform 0.25s ease, color 0.25s ease;
}

/* hover 箭头颜色 */
.select-input:deep(.el-select__wrapper:hover .el-select__caret) {
  color: var(--apix-primary-active);
}

/* 打开时旋转 */
.select-input:deep(.is-reverse .el-select__caret) {
  transform: rotate(180deg);
}

/* disabled */
.select-input:deep(.is-disabled.el-select__wrapper) {
  background: color-mix(in srgb, var(--apix-border-disabled) 8%, transparent);
  border-color: color-mix(in srgb, var(--apix-border-disabled) 30%, transparent);
}

/* ---------------------------------- */
.mode-switch {
  position: absolute;
  right: 14px;
  display: flex;
  background: color-mix(in srgb, var(--apix-default-light-color) 32%, transparent);
  border-radius: 999px;
  border: 1px solid color-mix(in srgb, var(--apix-border-light) 31.8%, transparent);
  box-shadow: inset 1px -1px 16px color-mix(in srgb, var(--apix-primary-color) 8.3%, transparent);
}

.mode-switch button {
  flex: 1;
  height: 24px;
  border: none;
  background-color: transparent;
  cursor: pointer;
  z-index: 1;
  font-size: 12px;
  color: var(--apix-secondary-dark-color);
  transition: color 0.25s ease;
}

.mode-switch button.active {
  color: var(--apix-darkest-color);
}

/* 共用 active 时的光晕与背景效果（original used color-mix） */
.mode-switch:active .slider,
.mode-switch:active:deep(.slider) {
  z-index: 999;
  box-shadow:
    var(--apix-shadow-lg),
    0 0 0 2px color-mix(in srgb, var(--apix-primary-color) 14%, transparent);
  backdrop-filter: saturate(180%) blur(3px);
  transition: all 0.3s var(--apix-cubic-bezier);
  background-color: color-mix(in srgb, var(--apix-default-light-color) 1%, transparent);
}

.highlight-select {
  color: var(--apix-secondary-dark-color);
  transition: color 0.25s ease;
}

.highlight-select.right {
  color: var(--apix-darkest-color);
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
  transition: all 0.3s var(--apix-cubic-bezier);
  box-shadow:
    var(--apix-shadow-md),
    0 0 0 2px color-mix(in srgb, var(--apix-primary-color) 47.1%, transparent);
  background-color: var(--apix-lightest-color);
}

.slider.right {
  transform: translateX(87%);
}
/* ---------------------------------- */

:deep(.el-slider__runway) {
  background-color: var(--apix-panel-layer-0-background);
}

/* Logout */
.logout-btn-wrapper {
  position: fixed;
  right: 36px;
  bottom: 22px;
  z-index: 999;
  border-radius: var(--apix-button-border-radius) !important;
}
</style>


<style scoped>
/* 横幅容器 - 纯净深色基底 */
.apix-banner {
  width: 100%;
  max-width: 900px;
  background: linear-gradient(145deg, #0b1220 0%, #151d2e 100%);
  border-radius: 20px;
  padding: 48px;
  position: relative;
  overflow: hidden;
  border: 1px solid rgba(136, 202, 197, 0.2);
  box-shadow: 
      0 20px 60px -15px rgba(0, 0, 0, 0.5),
      inset 0 1px 0 rgba(255, 255, 255, 0.05);
}

/* 简化光效 - 更纯净 */
.apix-banner::before {
  content: '';
  position: absolute;
  top: -40%;
  right: -20%;
  width: 600px;
  height: 600px;
  background: radial-gradient(circle, rgba(136, 202, 197, 0.12) 0%, transparent 70%);
  pointer-events: none;
}

/* 内容布局 - 关键修复：垂直居中对齐 */
.banner-content {
  position: relative;
  z-index: 2;
  display: flex;
  align-items: center; /* 改为center，解决对齐问题 */
  gap: 32px;
  flex-wrap: wrap;
}

/* Logo区域 - 扁平化设计，去除浑浊渐变 */
.banner-logo {
  flex-shrink: 0;
  width: 80px;
  height: 80px;
  background: rgb(136, 202, 197);
  border-radius: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 
      0 12px 40px -8px rgba(136, 202, 197, 0.35),
      inset 0 1px 0 rgba(255, 255, 255, 0.3);
  position: relative;
  border: none;
}

/* 图标样式 - 关键修复：完美居中 */
.banner-logo .icon {
  width: 48px;
  height: 48px;
  fill: #0b1220; /* 深色填充，提高对比度 */
  display: block;
}

/* 文字区域 - 移除顶部padding，与图标对齐 */
.banner-text {
  flex: 1;
  min-width: 300px;
  padding-top: 0; /* 移除8px padding */
  display: flex;
  flex-direction: column;
  justify-content: center; /* 垂直居中内容 */
}

.banner-title-wrapper {
  position: relative;
  display: inline-block;
  margin-bottom: 12px;
  width: 150px;
}

.banner-title {
  font-size: 56px;
  font-weight: 800;
  letter-spacing: 2px;
  margin: 0;
  color: rgb(136, 202, 197);
  line-height: 1;
  display: flex;
  align-items: center;
}

/* beta标签 - 绝对定位右上角 */
.version-tag {
  position: absolute;
  top: -8px;
  right: -50px;
  padding: 3px 8px;
  background: rgba(136, 202, 197, 0.05);
  border: 1px solid rgba(136, 202, 197, 0.2);
  border-radius: 18px;
  font-size: 10px;
  color: rgb(136, 202, 197);
  font-weight: 600;
  letter-spacing: 0.5px;
}

/* 简化分隔线 */
.divider {
  width: 40px;
  height: 2px;
  background: rgb(136, 202, 197);
  margin: 16px 0;
  border-radius: 1px;
  opacity: 0.6;
}

.banner-subtitle {
  font-size: 15px;
  color: #8b9aae; /* 更纯净的灰色 */
  line-height: 1.6;
  max-width: 550px;
  margin: 0;
}

.banner-subtitle strong {
  color: rgb(136, 202, 197);
  font-weight: 500;
}

/* 开发者标签 - 扁平化 */
.banner-meta {
  display: flex;
  align-items: center;
  gap: 20px;
  margin-top: 20px;
  flex-wrap: wrap;
}

.dev-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px 6px 11px;
  background: rgba(136, 202, 197, 0.08);
  border: 1px solid rgba(136, 202, 197, 0.2);
  border-radius: 20px;
  font-size: 12px;
  color: #c4d0dc;
  transition: all 0.2s ease;
}

.dev-badge:hover {
  background: rgba(136, 202, 197, 0.15);
  border-color: rgba(136, 202, 197, 0.35);
}

.dev-badge::before {
  content: '◆';
  font-size: 10px;
  color: rgb(136, 202, 197);
}

/* 引擎标签 - 简化 */
.engine-tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.engine-tag {
  padding: 5px 12px;
  background: rgba(136, 202, 197, 0.06);
  border: 1px solid rgba(136, 202, 197, 0.15);
  border-radius: 8px;
  font-size: 11px;
  color: #9ab;
  font-weight: 500;
  letter-spacing: 0.5px;
}

.engine-tag:hover {
  background: rgba(136, 202, 197, 0.12);
  border-color: rgba(136, 202, 197, 0.3);
  color: rgb(200, 235, 230);
}

/* 装饰元素 - 极简 */
.corner-accent {
  position: absolute;
  top: 0;
  right: 0;
  width: 120px;
  height: 120px;
  background: linear-gradient(225deg, rgba(136, 202, 197, 0.08) 0%, transparent 60%);
  pointer-events: none;
    }
</style>