# APIX 文档

Apix 提供 Agent SDK、工具执行、消息存储和 HTTP 服务。事件调度与图执行由独立依赖 [Apixis](https://github.com/JJJJSTIYYYY/Apixis) 提供。

- [Apixis 接入与迁移指南](./apixis-integration.md)：安装、AgentGraph、工具路由、上下文与服务生命周期。
- [LLM Provider 适配指南](./llm-providers.md)：Bot 调用、Profile 注册、协议与 Schema、自定义厂商和测试。
- [Bot 官方文档核对记录](./llm-provider-audit.md)：全部内置服务商的官方来源、修正项与未验证边界。
- [Apixis 接口文档](https://github.com/JJJJSTIYYYY/Apixis/tree/master/docs)：事件、图、订阅、中断、快照与远程通道。

Apix 的测试覆盖业务行为及 Apixis 接入边界；事件引擎、图引擎本身的实现测试由 Apixis 仓库维护。
