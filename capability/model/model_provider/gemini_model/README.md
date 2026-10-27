# gemini_model

English | [中文](README.cn.md)

Gemini provider plugin. `CARD_CONFIG` is the card. The shared field list is [`model_provider`](../README.md).

## Contract

| | |
|---|---|
| `provider` | `gemini` |
| `interface` | `gemini` |
| `card_id` | `gemini_model` |
| SDK call | `generate_content` and `generate_content_stream` in [`gemini.py`](../../model_API/model_interface/gemini.py) |

`capability_profile` builds the process declaration from `CARD_CONFIG` plus `--change` topics the card understands. `load` and `load_async` call `load_named_card` with this `card_id`.

The card file is `gemini_model.json`. Parameters are `UNSET`.

## Model Experience

Indirectly, through [`model_runtime`](../../model_runtime/README.md). The card's model placeholder is `your-gemini-model`. `base_url` is empty. `stream` is `UNSET`.
