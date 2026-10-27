# openai_response_model

English | [中文](README.cn.md)

OpenAI Responses provider plugin. `CARD_CONFIG` is the card. The shared field list is [`model_provider`](../README.md).

## Contract

| | |
|---|---|
| `provider` | `openai` |
| `interface` | `openai_response` |
| `card_id` | `openai_response_model` |
| SDK call | `responses.create` in [`openai_response.py`](../../model_API/model_interface/openai_response.py) |

`capability_profile` builds the process declaration from `CARD_CONFIG` plus `--change` topics the card understands. `load` and `load_async` call `load_named_card` with this `card_id`.

The card file is `openai_response_model.json`.

## Model Experience

Indirectly, through [`model_runtime`](../../model_runtime/README.md). The card's model placeholder is `your-openai-response-model`. `stream` is `UNSET`. `base_url` is `https://api.openai.com/v1`.
