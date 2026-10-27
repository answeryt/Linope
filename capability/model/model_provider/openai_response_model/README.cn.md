# openai_response_model

[English](README.md) | 中文

OpenAI Responses 提供者插件。`CARD_CONFIG` 是卡片。共享字段表在 [`model_provider`](../README.cn.md)。

## 契约

| | |
|---|---|
| `provider` | `openai` |
| `interface` | `openai_response` |
| `card_id` | `openai_response_model` |
| SDK 调用 | [`openai_response.py`](../../model_API/model_interface/openai_response.py) 里的 `responses.create` |

`capability_profile` 用 `CARD_CONFIG` 加上卡片理解的 `--change` 主题构造进程声明。`load` 和 `load_async` 用这个 `card_id` 调用 `load_named_card`。

卡片文件是 `openai_response_model.json`。

## 模型体验

间接地，通过 [`model_runtime`](../../model_runtime/README.cn.md)。卡片上的模型占位是 `your-openai-response-model`。`stream` 是 `UNSET`。`base_url` 是 `https://api.openai.com/v1`。
