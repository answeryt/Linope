# anthropic_model

English | [中文](README.cn.md)

Anthropic Messages provider plugin. `CARD_CONFIG` is the card. The shared field list is [`model_provider`](../README.md).

## Contract

| | |
|---|---|
| `provider` | `anthropic` |
| `interface` | `anthropic` |
| `card_id` | `anthropic_model` |
| SDK call | `messages.create` in [`anthropic.py`](../../model_API/model_interface/anthropic.py) |

`capability_profile` builds the process declaration from `CARD_CONFIG` plus `--change` topics the card understands. `load` and `load_async` call `load_named_card` with this `card_id`.

The card file is `anthropic_model.json`. The card sets `max_tokens` to `128000`. Other parameters are `UNSET`.

## Model Experience

Indirectly, through [`model_runtime`](../../model_runtime/README.md). The default model is `claude-opus-5`. `base_url` is `https://api.anthropic.com`. `stream` is `UNSET`.
