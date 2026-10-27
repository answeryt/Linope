# model/ — 提供者卡片与 SDK 调用

[English](README.md) | 中文

本家族把一张提供者卡片变成一份进程声明和一次提供者 SDK 调用。它不走模型回合。回合在 [`kernel/scheduler`](../../kernel/scheduler/README.cn.md)。

| 目录 | 职责 |
|---|---|
| [`model_provider/`](model_provider/README.cn.md) | 每个提供者一张卡片和一个 `capability_profile` |
| [`model_API/`](model_API/README.cn.md) | SDK 包装、粗略 token 估计，以及上下文窗口恢复 |
| [`model_message/`](model_message/README.cn.md) | 进程内的内容块 |
| [`model_runtime/`](model_runtime/README.cn.md) | 加载一张点名的卡片，并组装流式回合 |
