
---

# General

## 1. Append Message

**Rule 1.1 – Source of Truth**

* **MySQL is the single source of truth** for conversation messages.
* Redis is **never** considered authoritative for message persistence.

**Process:**

1. First, append message to **MySQL**.

   * This step must succeed before any further operation.
   * Message append must be **idempotent** (use message_id / seq).

2. Then try to feedback to **Redis**:

   * If Redis key **not found** → skip silently.
   * If Redis key **exists** → append new message to Redis.

**Constraints:**

* Redis append failure **must not** rollback MySQL append.
* Redis is treated as a **best-effort runtime cache**, not persistence.

---

## 2. Query Message

**Rule 2.1 – Redis is a Cache, Not a Guarantee**

* Redis hit **does not guarantee full history**.
* Completeness is determined by cursor / sequence, not existence.

**Process:**

1. First, query **Redis**:

   * If found → return messages **within Redis-visible window**.

2. If not found in Redis:

   * Query **MySQL**.
   * If found in MySQL:

     * Return messages.
     * Feedback messages to Redis (initialize cache).
   * If not found in MySQL:

     * Return empty / not found.

**Constraints:**

* Query path must be **read-only** for MySQL.
* Redis feedback must be **asynchronous or non-blocking**.

---

## 3. Create Task

**Rule 3.1 – Redis Task Key = Active Execution**

* A task **exists in Redis if and only if it is active**.
* Redis task key **must be created with NX** (atomic).
* Redis task key MUST have TTL.
* TTL expiration is treated as abnormal task termination fallback.

**Process:**

1. First, query Redis:

   * If not found → allow creation.
   * If found and status is `pending` or `running`:

     * Reject creation.
     * Return existing `task_id`.

2. If allowed:

   * Create task entry in Redis.

**Constraints:**

* Task creation must be **atomic**.

---

## 4. Update Task

**Rule 4.1 – Redis Is the Only Mutable Task State**

* Task state transitions are allowed **only if task exists in Redis**.

**Process:**

1. First, query Redis:

   * If found → allow update.
   * If not found → reject update and return fail.

2. If allowed:

   * Update task info in Redis.
   * Validate state transition (`pending → running → finish`).

3. If task finishes (`done` or `failed`):

   * Persist final task record to **MySQL**.
   * Redis key must be deleted immediately or set TTL expired.

**Constraints:**

* MySQL task record is **append-only**.
* Redis deletion does **not** imply task failure.

---

## 5. Query Task

**Rule 5.1 – Redis First, MySQL Is Historical**

**Process:**

1. First, query Redis:

   * If found → return task info.

2. If not found in Redis:

   * Query MySQL.
   * If found:

     * Return task info.

   * If not found:

     * Return not found.

**Constraints:**

* Missing Redis key means **task is not active**, not that it never existed.
* MySQL is the final authority for completed tasks.
* Completed tasks MUST NOT be re-cached into Redis.

---

# Caution

## 1. Cursor & AI Cache Semantics

* Cursor in AI cache is an **auto-increment logical key**, not a Redis list index.
* Cursor **must never be derived from list length** unless the list represents full history.

**Rules:**

* AI cache exists only to:

  * Reduce network bandwidth.
  * Serve delta context to AI.
* AI cache:

  * Stores **old messages only**, not the latest append.
  * Can be safely dropped or invalidated at any time.
* Before querying AI cache:

  * New messages **must already be committed to MySQL**.

**Important:**

* AI cache ≠ Redis conversation cache.
* AI cache has **zero correctness guarantees**.

---

## 2. Task Storage & Execution Guarantees

* Memory service stores **only task info**.
* Redis task key existence implies:

  * Task is **currently active**.
* If a task key **cannot be found in Redis**:

  * Task is considered **finished or failed**.

**Rules:**

* Each tool execution must be protected by:

  * Redis NX lock.
* Memory service ensures:

  * **At most one active execution per tool**.
  * No tool is executed concurrently with itself.

---

## 3. Conversation Lifecycle (Implicit but Mandatory)

* Conversation creation is **explicit**, not implicit.
* Messages can only be appended to an **existing conversation_id**.
* Conversation metadata is stored in MySQL `conversations` table and updated only by:

  * create
  * close / archive
  * lifecycle events

**Never:**

* Infer conversation existence from message append.
* Create conversation implicitly during message append.

---

## 4. Redis Failure Tolerance

* Redis failure must:

  * Never block message append.
  * Never block task completion persistence.
* System must remain **correct but slower** under Redis outage.

---

* The following is URL to AI system structure PNG:

  [structure graph](./work_flow.png)

---

# 总则（General）

## 1. 追加消息（Append Message）

### 规则 1.1 —— 真相源（Source of Truth）

* **MySQL 是对话消息的唯一真相源（single source of truth）**
* Redis **绝不被视为**消息持久化的权威存储

### 流程（Process）

1. **首先**将消息追加写入 **MySQL**

   * 该步骤必须成功，后续操作才允许继续
   * 消息追加必须是**幂等的**（使用 `message_id / seq`）

2. 然后尝试将消息回写到 **Redis**

   * 如果 Redis key **不存在** → 静默跳过
   * 如果 Redis key **存在** → 将新消息追加到 Redis

### 约束（Constraints）

* Redis 写入失败 **不得**回滚 MySQL 写入
* Redis 仅被视为**尽力而为的运行时缓存**，而非持久化存储

---

## 2. 查询消息（Query Message）

### 规则 2.1 —— Redis 是缓存，而非保证

* 命中 Redis **不保证**返回的是完整历史
* 数据完整性由 **cursor / sequence** 决定，而不是 key 是否存在

### 流程（Process）

1. **优先查询 Redis**

   * 若命中 → 返回 **Redis 可见窗口内** 的消息

2. 若 Redis 未命中：

   * 查询 **MySQL**
   * 若 MySQL 命中：

     * 返回消息
     * 将消息回写到 Redis（初始化缓存）
   * 若 MySQL 也未命中：

     * 返回空结果 / 不存在

### 约束（Constraints）

* 查询路径对 MySQL **必须是只读的**
* Redis 回填必须是**异步或非阻塞**的

---

## 3. 创建任务（Create Task）

### 规则 3.1 —— Redis 任务键即“正在执行”

* **任务存在于 Redis 当且仅当任务处于活跃状态**
* Redis 任务 key **必须使用 NX 方式创建**（原子操作）
* Redis 任务 key **必须设置 TTL**
* TTL 到期被视为**异常任务终止的兜底机制**

### 流程（Process）

1. **优先查询 Redis**

   * 若不存在 → 允许创建
   * 若存在且状态为 `pending` 或 `running`：

     * 拒绝创建
     * 返回已存在的 `task_id`

2. 若允许创建：

   * 在 Redis 中创建任务条目

### 约束（Constraints）

* 任务创建必须是**原子的**

---

## 4. 更新任务（Update Task）

### 规则 4.1 —— Redis 是唯一可变的任务状态存储

* **仅当任务存在于 Redis 中时**，才允许进行状态变更

### 流程（Process）

1. **优先查询 Redis**

   * 若存在 → 允许更新
   * 若不存在 → 拒绝更新并返回失败

2. 若允许更新：

   * 更新 Redis 中的任务信息
   * 校验状态流转合法性（`pending → running → finish`）

3. 当任务结束（`done` 或 `failed`）时：

   * 将最终任务记录持久化到 **MySQL**
   * Redis key 必须被立即删除，或通过 TTL 过期

### 约束（Constraints）

* MySQL 中的任务记录为**仅追加（append-only）**
* Redis key 的删除 **不代表任务失败**

---

## 5. 查询任务（Query Task）

### 规则 5.1 —— Redis 优先，MySQL 负责历史

### 流程（Process）

1. **优先查询 Redis**

   * 若命中 → 返回任务信息

2. 若 Redis 未命中：

   * 查询 **MySQL**
   * 若命中：

     * 返回任务信息
   * 若未命中：

     * 返回不存在

### 约束（Constraints）

* Redis key 缺失表示**任务不再活跃**，而不是任务从未存在
* MySQL 是已完成任务的最终权威来源
* **已完成任务不得重新回填至 Redis**

---

# 注意事项（Caution）

## 1. Cursor 与 AI Cache 语义

* AI Cache 中的 cursor 是**自增的逻辑键**，不是 Redis list index
* 除非 Redis list 表示完整历史，否则 **cursor 不得由 list 长度推导**

### 规则（Rules）

* AI Cache 仅用于：

  * 减少网络带宽消耗
  * 向 AI 提供增量上下文
* AI Cache：

  * **只存旧消息**，不存最新追加的消息
  * 可在任意时间被安全丢弃或失效
* 在查询 AI Cache 之前：

  * 新消息 **必须已提交至 MySQL**

### 重要说明（Important）

* AI Cache ≠ Redis 对话缓存
* AI Cache **不提供任何正确性保证**

---

## 2. 任务存储与执行保证

* Memory service **只存储任务信息**
* Redis 中存在任务 key 表示：

  * 任务**正在执行**
* 若 Redis 中找不到任务 key：

  * 任务被视为**已完成或失败**

### 规则（Rules）

* 每一次工具执行必须受以下机制保护：

  * Redis NX 锁
* Memory service 保证：

  * **每个工具在任意时刻最多只有一个活跃执行**
  * 同一工具不会并发执行自身

---

## 3. 对话生命周期（隐式但强制）

* 对话创建必须是**显式的**，不得隐式创建
* 消息只能追加到**已存在的 `conversation_id`**
* 对话元数据存储在 MySQL 的 `conversations` 表中，仅在以下事件中更新：

  * 创建（create）
  * 关闭 / 归档（close / archive）
  * 生命周期事件（lifecycle events）

### 禁止行为（Never）

* 不得通过消息追加推断对话是否存在
* 不得在消息追加过程中隐式创建对话

---

## 4. Redis 故障容忍

* Redis 故障时：

  * 不得阻塞消息追加
  * 不得阻塞任务完成结果的持久化
* 在 Redis 不可用的情况下，系统必须：

  * **保持正确性**
  * **允许性能下降**

---

* 以下为 AI 系统结构示意图链接：

  [结构图](./work_flow.png)

---