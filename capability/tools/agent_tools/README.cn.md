# agent_tools/ — 面向模型的工具

[English](README.md) | 中文

每个目录是一族插件。插件暴露 `load`、`capability_profile`，通常还有 `tool_schemas()`。`load` 返回的字符串是工具结果。点名这些工具的路由散文在 [`system_02_tools.md`](../../prompt/prompt_card/system/system_02_tools.md)。

| 目录 | 职责 |
|---|---|
| [`file_tools/`](file_tools/README.cn.md) | 读、写、编辑、搜索和图片文件 |
| [`shell_tools/`](shell_tools/README.cn.md) | 一次性 shell 和持久 shell |
| [`terminal_tools/`](terminal_tools/README.cn.md) | 持久终端会话和桌面窗格 |
| [`code_tools/`](code_tools/README.cn.md) | 运行一个调用其他工具的 Python 程序 |
| [`web_search_tools/`](web_search_tools/README.cn.md) | 按提供者的网页搜索 |
| [`interaction_tools/`](interaction_tools/README.cn.md) | 向用户提一个问题 |
