# 任务目标：

## 重构 message 表

### 保留及新增字段：

- `id` - 数据库内部自增主键 (保持原设计)
- `message_uid` - 消息的unique id
- `msg_cursor` - 业务id字段 (保持原设计)
- `user_uid` - 用户归属 (保持原设计)
- `conversation_id` - 数据库内部join id，提升join性能用，为conversation表的主键id (保持原设计)
- `conversation_uid` - 会话归属 (保持原设计)
- `generation_id` - 当前对话轮次id (保持原设计)
- `node_id` - 当前消息节点id，节点按对话轮次以及角色聚合 (保持原设计)
- `parent_id` - 当前消息的上一条消息id (保持原设计)
- `role` - 角色 (保持原设计)
- `name` - 名称，助手名/用户名/工具名 (新增字段)
- `content` - 内容 (保持原设计)
- `metadata` - 字典，存消息用量、模型供应商等数据 (新增字段)
- `extensions` - 字典，业务字段，如思维链、工具调用、生成的执行计划、搜索的内容用户以及上传的文件、指令、引用消息等等 (新增字段)
- `timestamp` - 改为某条记录的创建时间 (字段语意修改)
- `is_deleted` - 数据库内部软删除字段 (保持原设计)

### 删除字段：

- `extra`
- `info`
- `think`

### 注：

- 同步对齐apix/agent/store/core/server/cache_store缓存模块；
- 同步对齐apix/agent/store/core/execute_layer.py业务执行层代码；
- 同步对齐store模块的测试；
- 同步对齐apix/agent/sdk/utils/message.py的消息对象定义，同步修改消息对象的使用处；
- 数据库中可以自动创建的部分，如时间戳、自增的主键id，不需要在消息对象中保存，以免不一致；
- 消息对象中善用@property，以便捷获取extensions字段中的数据；
- 告知我重构时修改过的文件；
- ** 项目正处在快速迭代阶段，无需考虑兼容旧数据模型 **