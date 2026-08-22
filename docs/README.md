# APIX 文档

本目录保存 APIX 的项目文档。当前已完成 `source/apix/core` 的使用文档，内容以项目源码及 `source/tests/core`、`source/tests/integration` 中验证过的行为为准。

## Core Runtime

- [Core Runtime 总览](./core/README.md)
- [事件系统](./core/event/README.md)
  - [处理器注册、排序与版本隔离](./core/event/handlers.md)
  - [事件通道、序列化与远程传输](./core/event/channels.md)
- [Graph Runtime](./core/graph/README.md)
  - [状态模型、Command 与复制语义](./core/graph/state.md)
  - [GraphContext、快照、恢复与流式上下文](./core/graph/context/README.md)
  - [图中断与恢复控制](./core/graph/interrupter/README.md)
- [Core 异常类型](./core/utils/README.md)

## 阅读建议

如果是第一次使用 Core Runtime，建议按以下顺序阅读：

1. [Core Runtime 总览](./core/README.md)
2. [事件系统](./core/event/README.md)
3. [Graph Runtime](./core/graph/README.md)
4. [状态模型、Command 与复制语义](./core/graph/state.md)
5. 根据需要继续阅读快照、流式输出、中断或远程事件通道文档

