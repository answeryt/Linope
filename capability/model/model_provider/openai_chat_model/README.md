# openai_chat_model

English | [中文](README.cn.md)

OpenAI Chat provider plugin. `CARD_CONFIG` is the card. The shared field list is [`model_provider`](../README.md).

## Contract

| | |
|---|---|
| `provider` | `openai` |
| `interface` | `openai_chat` |
| `card_id` | `openai_chat_model` |
| SDK call | `chat.completions.create` in [`openai_chat.py`](../../model_API/model_interface/openai_chat.py) |

`capability_profile` builds the process declaration from `CARD_CONFIG` plus `--change` topics the card understands. `load` and `load_async` call `load_named_card` with this `card_id`.

The card file is `openai_chat_model.json`. Runtime configuration follows `CARD_CONFIG` in the plugin.

## Model Experience

Indirectly, through [`model_runtime`](../../model_runtime/README.md). This plugin adds no system prompt of its own. The default card model is `deepseek-flash` and `stream` is true. `base_url` is `https://api.deepseek.com`.
