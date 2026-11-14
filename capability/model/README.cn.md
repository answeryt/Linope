# model/ — 提供者卡片与 SDK 调用

[English](README.md) | 中文

本家族提供模型卡片和一次提供者 SDK 调用。卡片由
[`kernel/scheduler/model_scheduler`](../../kernel/scheduler/model_scheduler/README.cn.md)
作为类 CPU 计算资源执行，不创建模型进程。
内核可以把同一张已安装卡片复制到开发者配置的多个模型核上；
本目录只负责卡片解析和单次提供者调用，不负责核的分配。

| 目录 | 职责 |
| --- | --- |
| [`model_provider/`](model_provider/README.cn.md) | 每个提供者一张卡片和一个 `capability_profile` |
| [`model_API/`](model_API/README.cn.md) | SDK 包装、粗略 token 估计，以及上下文窗口恢复 |
| [`model_message/`](model_message/README.cn.md) | 进程内的内容块 |
| [`model_runtime/`](model_runtime/README.cn.md) | 加载一张点名的卡片，并组装流式回合 |
