# calculate

[English](README.md) | 中文

`measure` 看一个进程，报两个数：记忆里已经存下的文本占多少 token，以及还有多少个进程和它共用同一条网络通道。这两个数放在 `Pressure` 里。负载均衡根据它决定要不要再加一个工作线程。

## 契约

| 入口 | 结果 |
|---|---|
| `count_tokens(model, content)` | 通过 `litellm` 计算一段文本、代码或一张图片的 token 数。空文本是 0。缺少模型名时使用 `gpt-4o`。 |
| `measure(...)` | 读取本进程的记忆实体，以及它通道上的其他进程。 |

`Pressure` 携带 `tokens`、`context_limit`、`context_full`、`channel`、`peers` 和 `activity`。上下文上限来自 [`capability/model/model_API/model_paramaters/context_limits`](../../capability/model/model_API/model_paramaters/context_limits/README.cn.md)。`context_full` 是调度器的 `capacity_full` 决定。已存储的行由 [`kernel/resource/memory`](../resource/memory/README.cn.md) 计数。

图片内容是以 `.png`、`.jpg`、`.jpeg`、`.gif` 或 `.webp` 结尾的字符串，或带 `url` 的字典。图片计数使用带 `use_default_image_token_count` 的 `litellm`。

## 已知限制与暂缓事项

- **计数需要 `litellm`** — `count_tokens` 在调用时导入它。没有安装则计数失败。
