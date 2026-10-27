# model_paramaters/ — 估计与上下文恢复

[English](README.md) | 中文

粗略 token 估计和上下文上限处理。这些模块按文件加载。它们不是可替换插件，也不互相导入。

参数翻译（`max_tokens` 改名、`stream_options` 等）写在对应的 [`model_interface`](../model_interface/README.cn.md) `call_api` 里。它不经过本目录。

| 目录 | 职责 |
|---|---|
| [`tokens/`](tokens/README.cn.md) | 文本、图片、消息和工具 schema 的粗略估计 |
| [`context_limits/`](context_limits/README.cn.md) | 默认模型窗口，以及从提供者错误中恢复 |

`context_limits` 里的最大输出长度是模型上下文内部的输出上限。它不是接口请求的 `max_tokens`。
