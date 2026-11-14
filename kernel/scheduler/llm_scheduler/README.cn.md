# llm_scheduler compatibility

[English](README.md) | 中文

本目录仅保留旧导入路径的兼容文件。新的模型调度器在
[`../model_scheduler`](../model_scheduler/README.cn.md)，模型不是进程，
也不通过 `settings.slot` 进入队列。

请使用 `model use` 安装卡片、使用 `model run` 执行请求。工具仍然是
capability 进程。
