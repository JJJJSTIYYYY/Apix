# 一、重构目标

本次重构的核心目标是：

> 将当前单体 `AI_Agent` 类拆分为 **运行时调度层 + 执行骨架层 + 节点实现层**，通过 Hook 机制消除 Agent 与 SubAgent 的重复逻辑，同时保留其关键差异。

---

## 具体目标

### 1. 职责解耦

* `AI_Agent` 当前承担：

  * agent 构建
  * graph 构建
  * node 实现
  * sub-agent 调度
  * cache 管理
* 👉 重构后拆为：

  * `AiAgentRuntime`（调度）
  * `AgentBase`（执行骨架）
  * `AgentNode`（节点实现）

---

### 2. 消除重复代码

当前问题：

* `_create_agent` vs `_create_sub_agent` 大量重复
* node 实现复制两份

👉 重构目标：

* graph 结构统一
* node 主逻辑统一
* 差异通过 hook 注入

---

### 3. 控制复杂度

* 保持**少类设计（3+2）**
* 避免过度抽象
* 避免 if/else role 分支

---

# 二、重构后整体结构

```text
AiAgentRuntime        ← 运行时（调度 / factory / 生命周期）
│
├── AgentBase         ← Agent执行骨架（graph构建 + hook定义）
│       ↑
│       ├── Agent         ← 主Agent
│       └── WorkerAgent   ← 子Agent
│
└── AgentNode         ← 节点实现（统一逻辑 + 调用hook）
```

---

# 三、核心类设计

---

# 3.1 AiAgentRuntime（运行时层）

## 职责

* Agent 创建（factory）
* SubAgent 调度
* 生命周期管理
* cache（可选）

👉 **不包含任何业务逻辑 / node / LLM 调用**

---

## 示例实现

```python
class AiAgentRuntime:

    def __init__(self):
        self._running_tasks: dict[str, asyncio.Task] = {}

    def create_agent(self, role: str, config: dict):
        if role in ["main", "agent", "team_leader"]:
            return Agent(config, runtime=self)
        else:
            return WorkerAgent(config, runtime=self)

    async def submit_agent_task(self, state, config):
        agent = self.create_agent(state.get("agent_role"), config)
        return agent.run_stream(state)

    async def submit_sub_agent_task(self, agent_name, state, config):
        task = asyncio.create_task(
            self.create_agent("worker", config).run_stream(state)
        )
        self._running_tasks[state["task_id"]] = task
```

---

# 3.2 AgentBase（执行骨架）

## 职责

* 构建 LangGraph
* 定义标准执行流程
* 定义 Hook（差异注入点）

---

## Graph 结构（统一）

```text
START
  ↓
context_prepare
  ↓
context_summary
  ↓
llm_call
  ↓
persist
  ↓
(conditional)
  ├── tools → persist
  └── END
```

---

## 实现

```python
class AgentBase:

    def __init__(self, config: dict, runtime: AiAgentRuntime):
        self.config = config
        self.runtime = runtime
        self.graph = self._build_graph()

    def run_stream(self, state):
        return self.graph.astream(
            state,
            {"recursion_limit": 1024},
            stream_mode="custom"
        )

    def _build_graph(self):
        nodes = AgentNode(self)

        graph = StateGraph(self._state_type())

        graph.add_node("context_prepare", nodes.context_prepare)
        graph.add_node("context_summary", nodes.context_summary)
        graph.add_node("llm_call", nodes.llm_call)
        graph.add_node("persist", nodes.persist)

        graph.add_edge(START, "context_prepare")
        graph.add_edge("context_prepare", "context_summary")
        graph.add_edge("context_summary", "llm_call")
        graph.add_edge("llm_call", "persist")

        if not self._pure_chat():
            graph.add_node("tools", nodes.tools)
            graph.add_conditional_edges(
                "persist",
                nodes.should_continue,
                {
                    "llm": "context_summary",
                    "tools": "tools",
                    END: END,
                },
            )
            graph.add_edge("tools", "persist")
        else:
            graph.add_edge("persist", END)

        return graph.compile()
```

---

# 四、Hook 设计（核心）

👉 所有差异必须通过 hook 注入

---

## 必须实现

```python
class AgentBase:

    def _state_type(self):
        raise NotImplementedError

    async def hook_context_prepare(self, state):
        raise NotImplementedError

    async def hook_persist(self, state, last_message):
        raise NotImplementedError
```

---

## 可选 Hook

```python
class AgentBase:

    async def hook_after_summary(self, state, summary, recent):
        pass

    def hook_should_continue(self, state, last_message):
        if last_message.tool_calls:
            return "tools"
        return END
```

---

# 五、AgentNode（节点实现层）

## 职责

* 实现所有 graph node
* 复用通用逻辑
* 在关键点调用 hook

---

## 5.1 context_prepare

```python
async def context_prepare(self, state):
    return await self.agent.hook_context_prepare(state)
```

---

## 5.2 context_summary（重点复用）

```python
async def context_summary(self, state):

    messages = state.get("messages", [])
    threshold = max(16, self.agent.config.get("message_summary", 0))

    if len(messages) < threshold:
        return {}

    to_process, recent = ai_context_manager.split_messages(messages, keep_recent=4)

    summary = await self._do_summary(state, to_process)

    state["messages"].clear()
    state["messages"].extend(recent)

    await self.agent.hook_after_summary(state, summary, recent)

    return {"shortterm_memory": summary}
```

---

## 5.3 llm_call（统一）

👉 这一块你可以**完全复用一份**

---

## 5.4 persist（差异最大）

```python
async def persist(self, state):
    last_message = state["messages"][-1]
    return await self.agent.hook_persist(state, last_message)
```

---

## 5.5 should_continue

```python
def should_continue(self, state):
    last = state["messages"][-1]
    return self.agent.hook_should_continue(state, last)
```

---

# 六、Agent vs WorkerAgent

---

## 6.1 主 Agent

```python
class Agent(AgentBase):

    def _state_type(self):
        return MessagesState

    async def hook_context_prepare(self, state):
        # DB + memory + sandbox
        ...

    async def hook_persist(self, state, last_message):
        await ai_context_manager.append_to_messages(...)
        return {"current_tool_calls": ...}

    async def hook_after_summary(self, state, summary, recent):
        await ai_context_manager.insert_shortterm_memory(...)
```

---

## 6.2 WorkerAgent

```python
class WorkerAgent(AgentBase):

    def _state_type(self):
        return SubAssistantState

    async def hook_context_prepare(self, state):
        # generating_cache
        ...

    async def hook_persist(self, state, last_message):
        await logger.write_log(...)
        return {"outputs": last_message.content}

    async def hook_after_summary(self, state, summary, recent):
        await generating_cache.rewrite_history(...)
```

---

# 七、迁移步骤（强烈建议按顺序）

---

## Step 1（安全复制）

* 保留原 `AI_Agent`
* 新建：

  * `AgentBase`
  * `AgentNode`

---

## Step 2

👉 先迁移：

* `llm_call`
* `should_continue`

（最简单）

---

## Step 3

👉 迁移 `context_summary`

（抽公共逻辑 + hook）

---

## Step 4

👉 迁移 `persist`

---

## Step 5（最难）

👉 拆 `context_prepare`

---

## Step 6

👉 引入：

* `Agent`
* `WorkerAgent`

---

## Step 7

👉 最后替换 runtime

---

# 八、重构收益

---

## 1. 代码量下降（实际）

* `_create_agent`：1000+ 行 ❌
* → 拆成：

  * Base：200 行
  * Node：300 行
  * 子类：各 100 行

---

## 2. 可维护性提升

* node 可单测
* hook 可控
* graph 固定

---

## 3. 消灭最大风险点

👉 **复制代码 + 行为分叉**

---

# 九、设计原则总结（非常重要）

---

### 1️⃣ 流程统一

> graph 永远只有一套

---

### 2️⃣ 差异注入

> 所有差异必须走 hook

---

### 3️⃣ 禁止 role if/else

❌ 错误：

```python
if role == "main":
```

---

### 4️⃣ 副作用隔离

* DB
* cache
* log

👉 全部放 hook

---

# 十、一句话总结

> 👉 **用一个稳定的执行骨架（AgentBase）承载复杂度，用 hook 吸收差异，用 runtime 做调度**

---

如果你下一步想继续优化，我可以帮你做一件更狠的：

👉 **把 context_prepare 再拆成“可组合中间件链”**（类似 FastAPI middleware）

那一步能让你 agent 系统彻底模块化。
