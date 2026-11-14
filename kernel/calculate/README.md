# calculate

English | [中文](README.cn.md)

`measure` looks at one process and reports two numbers: how many tokens are already stored in its memory, and how many other processes share its network channel. Those numbers are a `Pressure` value. Load balancing reads it when deciding whether to add another worker.

## Contract

| Entry | Result |
|---|---|
| `count_tokens(model, content)` | Token count for one piece of text, code, or one image, using the kernel's own length estimate. An empty text or a missing model name is 0. |
| `measure(...)` | Reads this process's memory entity and the other processes on its channel. |

`Pressure` carries `tokens`, `context_limit`, `context_full`, `channel`, `peers`, and `activity`. The context limit is the integer a capability declared in its process settings. When that integer is absent, the kernel uses its own fallback of 256000. `context_full` compares the system text that would be sent with that limit. It does not add a worker. Stored rows stay in [`kernel/resource/memory`](../resource/memory/README.md) until a process reads an address.

Image content is a string ending in `.png`, `.jpg`, `.jpeg`, `.gif`, or `.webp`, or a dict with a `url`. One image counts as a fixed 85 tokens. The model name only says whether this count has a subject. It does not select a provider tokenizer.
