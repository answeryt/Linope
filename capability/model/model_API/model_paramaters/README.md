# model_paramaters

Token 粗估和上下文上限处理。这些是按文件加载的内部模块，不是可替换插件，彼此不 import。

参数翻译（`max_tokens` 改名、`stream_options` 等）写在对应的 `model_interface.call_api` 里，不经过本目录。

## 模块

| 文件 | 职责 |
| --- | --- |
| `tokens/tokens.py` | 文本 / 图片 / 消息 / 工具 schema 的粗估（不用于填写请求 `max_tokens`） |
| `context_limits/context_limits.py` | 模型默认窗口表，以及从错误里恢复更小窗口或输出上限 |

## tokens

`estimate_messages_tokens_rough` 默认使用本文件的文本和图片估算。仍可传入 `text_estimator` / `image_estimator` 覆盖。不在 `call_api` 组请求时调用。

## context_limits

- `resolve_default_context_length`：按最长子串匹配模型窗口
- `recover_missing_context_length` / `recover_lower_context_from_error` / `recover_context_probe_tier` / `recover_output_token_cap`
- `recover_request`：按上述顺序尝试

这里的最大输出长度是模型上下文里的输出上限，和接口请求的 `max_tokens` 不是同一件事。
