# tokens

English | [中文](README.cn.md)

Rough token estimates for text, images, messages, and tool schemas. These numbers are not written into a request as `max_tokens`. Interface field names live in [`model_interface`](../../model_interface/README.md).

## Contract

`tokens.py` does not import another module in the repository.

| Function | Result |
|---|---|
| `estimate_text_tokens_rough` | ASCII text is `(len + 3) // 4`. CJK-dense characters count as one each, and the remaining characters use the ASCII rule. Empty text is 0. |
| `estimate_image_tokens` | Image cost. The default constant is `1500`. |
| `estimate_message_tokens_rough` | One message, using the text and image estimators. |
| `estimate_messages_tokens_rough` | A list of messages. `text_estimator` and `image_estimator` may replace the defaults. |
| `estimate_tool_tokens_rough` | A tool schema list. |

`estimate_messages_tokens_rough` is not called while `call_api` builds a request.

## Model Experience

Indirectly, through a host that injects these estimators into [`context_compression`](../../../../context/context_compression/README.md). The estimate does not enter the provider request by itself.

## Known Limitations and Deferred Work

- **The count is a length heuristic** — it is not the provider tokenizer. [`kernel/calculate`](../../../../../kernel/calculate/README.md) uses `litellm` for a separate count.
