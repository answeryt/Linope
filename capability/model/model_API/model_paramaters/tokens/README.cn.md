# tokens

[English](README.md) | 中文

文本、图片、消息和工具 schema 的粗略 token 估计。这些数字不会作为 `max_tokens` 写入请求。接口字段名在 [`model_interface`](../../model_interface/README.cn.md)。

## 契约

`tokens.py` 不导入仓库里的其他模块。

| 函数 | 结果 |
|---|---|
| `estimate_text_tokens_rough` | ASCII 文本是 `(len + 3) // 4`。CJK 密集字符每个计 1，其余字符用 ASCII 规则。空文本是 0。 |
| `estimate_image_tokens` | 图片代价。默认常数是 `1500`。 |
| `estimate_message_tokens_rough` | 一条消息，使用文本和图片估计器。 |
| `estimate_messages_tokens_rough` | 一组消息。`text_estimator` 和 `image_estimator` 可以替换默认值。 |
| `estimate_tool_tokens_rough` | 一份工具 schema 列表。 |

`call_api` 构造请求时不调用 `estimate_messages_tokens_rough`。

## 模型体验

间接地，通过把这些估计器注入 [`context_compression`](../../../../context/context_compression/README.cn.md) 的宿主。估计本身不会进入提供者请求。

## 已知限制与暂缓事项

- **这个计数是长度启发式** — 它不是提供者的分词器。[`kernel/calculate`](../../../../../kernel/calculate/README.cn.md) 用 `litellm` 做另一套计数。
