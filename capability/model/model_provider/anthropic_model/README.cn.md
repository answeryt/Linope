# anthropic_model

[English](README.md) | 中文

Anthropic Messages 提供者插件。`CARD_CONFIG` 是卡片。共享字段表在 [`model_provider`](../README.cn.md)。

## 契约

| | |
|---|---|
| `provider` | `anthropic` |
| `interface` | `anthropic` |
| `card_id` | `anthropic_model` |
| SDK 调用 | [`anthropic.py`](../../model_API/model_interface/anthropic.py) 里的 `messages.create` |

`capability_profile` 用 `CARD_CONFIG` 加上卡片理解的 `--change` 主题构造进程声明。`load` 和 `load_async` 用这个 `card_id` 调用 `load_named_card`。

卡片文件是 `anthropic_model.json`。卡片把 `max_tokens` 设为 `128000`。其他参数是 `UNSET`。

## 模型体验

间接地，通过 [`model_runtime`](../../model_runtime/README.cn.md)。默认模型是 `claude-opus-5`。`base_url` 是 `https://api.anthropic.com`。`stream` 是 `UNSET`。
