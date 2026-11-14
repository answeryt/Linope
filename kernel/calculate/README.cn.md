# calculate

[English](README.md) | 中文

`measure` 看一个进程，报两个数：记忆里已经存下的文本占多少 token，以及还有多少个进程和它共用同一条网络通道。这两个数放在 `Pressure` 里。负载均衡根据它决定要不要再加一个工作线程。

## 契约

| 入口 | 结果 |
|---|---|
| `count_tokens(model, content)` | 用内核自己的长度估算计算一段文本、代码或一张图片的 token 数。空文本或缺少模型名时是 0。 |
| `measure(...)` | 读取本进程的记忆实体，以及它通道上的其他进程。 |

`Pressure` 携带 `tokens`、`context_limit`、`context_full`、`channel`、`peers` 和 `activity`。上下文上限是能力在进程设置里声明的整数。没有这个整数时，内核使用自己的 256000 回退值。`context_full` 只比较即将发送的 system 文本和这个上限。它不会因此增加 worker。历史行留在 [`kernel/resource/memory`](../resource/memory/README.cn.md)，模型用地址读取。

图片内容是以 `.png`、`.jpg`、`.jpeg`、`.gif` 或 `.webp` 结尾的字符串，或带 `url` 的字典。一张图片按固定的 85 个 token 计算。模型名只用来判断这次计数有没有对象，不选择供应商的分词器。
