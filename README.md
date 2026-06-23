<div align="center">

<img src="./README/source/APIX-bar.jpeg"  width="300" height="200" style="border-radius: 12px; display: block; margin: 0 auto;">

# APIX — 开源 AI Agent 协作平台

中文文档 | [English](./README_en.md)

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python)
![Electron](https://img.shields.io/badge/Electron-37-47848F?style=flat&logo=electron)
![Vue](https://img.shields.io/badge/Vue-3.5-4FC08D?style=flat&logo=vue.js)
![License](https://img.shields.io/badge/License-GPL%203.0-blue?style=flat)
[![Discord](https://img.shields.io/badge/Discord-Join%20Us-5865F2?style=flat&logo=discord&logoColor=white)](https://discord.gg/bsTqEzJmJ)
![QQ群](https://custom-icon-badges.demolab.com/badge/QQ群-639459172-00BFFF?style=flat&logo=tencent-qq)

**不只是聊天。构建、协作、执行——让 AI Agent 真正为你工作。**

</div>

---

## 🎯 这是什么？

APIX 是一个**全栈的 AI Agent 协作平台**。它是一套完整的 Agent 运行时——支持多智能体并行协作、安全代码执行、知识库检索。

它可以帮你完成包括但不限于代码编写、PPT生成、汇报整理以及各种自动化操作。

---

## ✨ 核心特性

<table border="1" cellpadding="8" cellspacing="0" style="border-collapse: collapse; width: 100%;">
  <tr>
    <td align="center" width="33%">🤖<br><b>多智能体协作</b><br>Leader 调度多个子代理并行工作，复杂任务自动分解，实现Agent文件访问冲突检测</td>
    <td align="center" width="33%">🔧<br><b>完整工具生态</b><br>代码执行、文件管理、网络搜索、知识检索开箱即用</td>
    <td align="center" width="33%">🧠<br><b>完善的记忆系统</b><br>以工作区划分记忆容器，人为可控的多级自动上下文压缩机制</td>
  </tr>
  <tr>
    <td align="center">🐳<br><b>代码安全沙箱</b><br>Docker 隔离执行，不用担心代码命令破坏系统</td>
    <td align="center">🔌<br><b>多模型供应商兼容</b><br>OpenAI / DeepSeek / MoonShot / Ollama / 自定义供应商任意切换</td>
    <td align="center">🎨<br><b>支持自定义任务流</b><br>卡片化任务流编辑，定制属于您的自动化任务流</td>
  </tr>
  <tr>
    <td align="center">👤<br><b>角色卡支持</b><br>自定义您的助手身份，定制一个独属于您的个人助理</td>
    <td align="center">⚒️<br><b>多协议MCP兼容</b><br>支持多种协议的MCP服务，并且可以自定义您的会话生命周期</td>
    <td align="center">💬<br><b>消息节点化管理</b><br>您可以在任意位置编辑或者删除您已发送的信息，并自动生成新的分支</td>
  </tr>
</table>

---

## 🖥️ 界面速览

<table border="0" cellpadding="6" cellspacing="6" style="border-collapse: collapse; width: 100%;">
  <tr>
    <td align="center" width="50%"><b>聊天界面展示</b><br><img src="./README/source/main-page.png"  style="border-radius: 6px;"></td>
    <td align="center" width="50%"><b>编辑器页面演示</b><br><img src="./README/source/editor-page.png"  style="border-radius: 6px;"></td>
  </tr>
  <tr>
    <td align="center"><b>资源管理页展示</b><br><img src="./README/source/src-page.png"  style="border-radius: 6px;"></td>
    <td align="center"><b>设置页展示</b><br><img src="./README/source/setting-page.png"  style="border-radius: 6px;"></td>
  </tr>
</table>

---

## 🚀 快速开始

### 一键安装攻略

对于windows用户，我们使用powershell:

```bash
Set-ExecutionPolicy Bypass -Scope Process -Force
.\setup.ps1
```

对于macos和linux，我们使用命令行终端:

```bash
chmod +x setup.sh
./setup.sh
```

> 一键安装过程中请确保网络保持畅通

### 如果您想自定义安装

可以参考我们的部署文档:

* [中文部署文档](./README/README_zh.md)
* [English Docs](./README/README_en.md)

---

## 🗺️ 路线图

- [x] 多智能体运行时
- [x] MCP 集成支持
- [x] 可视化线性工作流编辑器
- [x] Docker 安全沙箱
- [x] 事件循环
- [ ] 定时任务管理
- [ ] 插件系统与钩子
- [ ] 多平台接入
- [ ] 插件市场
- [ ] 单元测试补齐
- [ ] 图任务流编辑
- [ ] 工作区时间旅行

## 🗺️ 版本日志 (Version 2.1.1)

- 线形任务流编辑相关代码已损坏，将在后续版本中修复 (低优先级)
- 修复消息节点编辑后可能错误构建上下文的问题
- 添加事件循环与事件监听机制，非阻塞的按优先级调用事件处理函数
- 基于事件循环实现自动任务
- !!! 下一代APIX正在筹备中 (底层重构)

---

## 关于 APIX 3.0

- 将重构底层 Agent Loop；
- 更清晰的项目目录结构；
- 更自由的系统拓展点；
- 引入内存型数据库，并设置可关闭缓存；
- 更便捷的安装部署方式；
- 更高效的kv-cache命中；
- 更小的项目依赖；

---

## 📄 许可证

本项目基于 **GNU GPL v3.0** 协议开源。

---

__🫵 加入社区__

[QQ群](https://qun.qq.com/universal-share/share?ac=1&authKey=ommoQrT2zhzHU%2FUxv8pfGCJbNifW%2BJyUAFBkNdzkHTPUxdxCnlgxm5aNgGslTmdE&busi_data=eyJncm91cENvZGUiOiI2Mzk0NTkxNzIiLCJ0b2tlbiI6Im9ZZkdNUWZnSVV1Y2REeUhKNnlTbWEwc05Bb093djRzUXdXNE55dklBVnlBQk9XbGNpS0ZXSDlzK3orSW1sQ3YiLCJ1aW4iOiIzMTI5NDI0NTcyIn0%3D&data=OGTchcr80RAQg8Z8_GZTdvBb7kZDeM9B3hHcNqLaAX2ZK_KYq260C4CubblEBT1bK5fP6zgtnCk2D8fIoph1ZQ&svctype=4&tempid=h5_group_info) | [Discord](https://discord.gg/bsTqEzJmJ)


> 🌟 如果您喜欢我们的项目，欢迎您的Star!

> 已通过ApiFox进行模块测试