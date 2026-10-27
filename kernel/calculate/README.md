# calculate

English | [中文](README.cn.md)

`measure` looks at one process and reports two numbers: how many tokens are already stored in its memory, and how many other processes share its network channel. Those numbers are a `Pressure` value. Load balancing reads it when deciding whether to add another worker.

## Contract

| Entry | Result |
|---|---|
| `count_tokens(model, content)` | Token count for one piece of text, code, or one image, through `litellm`. An empty text is 0. A missing model name uses `gpt-4o`. |
| `measure(...)` | Reads this process's memory entity and the other processes on its channel. |

`Pressure` carries `tokens`, `context_limit`, `context_full`, `channel`, `peers`, and `activity`. The context limit comes from [`capability/model/model_API/model_paramaters/context_limits`](../../capability/model/model_API/model_paramaters/context_limits/README.md). `context_full` is the scheduler's `capacity_full` decision. Stored rows are counted by [`kernel/resource/memory`](../resource/memory/README.md).

Image content is a string ending in `.png`, `.jpg`, `.jpeg`, `.gif`, or `.webp`, or a dict with a `url`. The image count uses `litellm` with `use_default_image_token_count`.

## Known Limitations and Deferred Work

- **Counting needs `litellm`** — `count_tokens` imports it at call time. A missing install fails the count.
