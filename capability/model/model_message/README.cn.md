# model_message

[English](README.md) | 中文

进程内的消息内容块。这些是类型定义，不是可替换插件。提供者 SDK 字段在 [`model_interface`](../model_API/model_interface/README.cn.md)。流式回合组装器在 [`model_runtime`](../model_runtime/README.cn.md)。

## 契约

每个数据类都在 [`blocks.py`](blocks.py)：`TextBlock`、`ThinkingBlock`、`HintBlock`、`DataBlock`、`ToolCallBlock`、`ToolResultBlock`，以及它们的来源和状态类型。

## 模型体验

间接地，通过运行时组装器和接口解析器。本目录不添加系统提示词文本。

## 已知限制与暂缓事项

- **两套块模块** — 本文件的 `ThinkingBlock` 不是 `model_runtime.blocks.ReasoningBlock`。每个接口映射它自己解析的块。
