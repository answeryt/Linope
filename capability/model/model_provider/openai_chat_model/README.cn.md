# openai_chat_model

[English](README.md) | 中文

OpenAI Chat 提供者插件。`CARD_CONFIG` 是卡片。共享字段表在 [`model_provider`](../README.cn.md)。

## 契约

| | |
|---|---|
| `provider` | `openai` |
| `interface` | `openai_chat` |
| `card_id` | `openai_chat_model` |
| SDK 调用 | [`openai_chat.py`](../../model_API/model_interface/openai_chat.py) 里的 `chat.completions.create` |

`capability_profile` 用 `CARD_CONFIG` 加上卡片理解的 `--change` 主题构造进程声明。`load` 和 `load_async` 用这个 `card_id` 调用 `load_named_card`。

卡片文件是 `openai_chat_model.json`。运行时配置跟随插件里的 `CARD_CONFIG`。

## 模型体验

间接地，通过 [`model_runtime`](../../model_runtime/README.cn.md)。本插件不自己添加系统提示词。默认卡片模型是 `deepseek-flash`，`stream` 为真。`base_url` 是 `https://api.deepseek.com`。
