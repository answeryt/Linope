# tools/ — 代理工具与外部工具宿主

[English](README.md) | 中文

工具是能力插件。一个进程加载一个插件。`load` 接受种类 `tool` 和一个映射正文。`capability_profile` 是 [`kernel/process`](../../kernel/process/README.cn.md) 在启动时要的东西。

下面的目录把插件分组。模型可以被提供哪些工具，以及每个工具进程拿到的沙箱模式，由 [`kernel/process`](../../kernel/process/README.cn.md) 按 `tools.` 后面的名字决定。`tools.read` 是只读工具，因为它的名字是 `read`。

| 目录 | 职责 |
|---|---|
| [`agent_tools/`](agent_tools/README.cn.md) | 文件、shell、终端、代码、网页和向用户提问的工具 |
| [`external_tools/`](external_tools/README.cn.md) | MCP 客户端插件和插件约定的 CI |
