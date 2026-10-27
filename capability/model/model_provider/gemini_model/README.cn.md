# gemini_model

[English](README.md) | 中文

Gemini 提供者插件。`CARD_CONFIG` 是卡片。共享字段表在 [`model_provider`](../README.cn.md)。

## 契约

| | |
|---|---|
| `provider` | `gemini` |
| `interface` | `gemini` |
| `card_id` | `gemini_model` |
| SDK 调用 | [`gemini.py`](../../model_API/model_interface/gemini.py) 里的 `generate_content` 和 `generate_content_stream` |

`capability_profile` 用 `CARD_CONFIG` 加上卡片理解的 `--change` 主题构造进程声明。`load` 和 `load_async` 用这个 `card_id` 调用 `load_named_card`。

卡片文件是 `gemini_model.json`。参数是 `UNSET`。

## 模型体验

间接地，通过 [`model_runtime`](../../model_runtime/README.cn.md)。卡片上的模型占位是 `your-gemini-model`。`base_url` 为空。`stream` 是 `UNSET`。
