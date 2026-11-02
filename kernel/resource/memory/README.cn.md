# memory

[English](README.md) | 中文

一份记忆资源的逻辑地址空间。完整的行在 `MemoryStore` 里。运行时缓存只是为了按地址读取，不会自动发给模型。谁可以读或写，以及一个进程说的 `message/0` 指的是哪一行，在 [`kernel/scheduler`](../../scheduler/README.cn.md)。两个进程是否持有同一份记忆，在 [`kernel/resource`](../README.cn.md)。

## 这本字典

`open_state` 只打开一个句柄，不把正文放进资源实体：

```python
{"scope": "chat", "backend": ""}
```

`scope` 是这份记忆的身份，例如 `chat`。正文、序号和页表在 `MemoryStore`。默认后端是进程内的 `memory`。用户可以用 `linope memory backend` 改成 `sqlite`，并自己给出文件路径。

`items` 放行。键就是真名：`message/0`、`task/0`、`artifact/0`，或 `system`。`next` 是 `message`、`task`、`artifact` 各自的下一个编号。`seq` 是整本字典的一个计数器，后写下的行 `seq` 更大。

写下一条用户发言、再写入一个提示文件之后，字典是这样：

```python
{
    "address_space": {"scope": "chat"},
    "items": {
        "message/0": {
            "class": "message",
            "kind": "user",
            "content": "hello",
            "time": "2026-01-01T00:00:00+00:00",
            "seq": 1,
            "state": "asked",
        },
        "system": {
            "class": "system",
            "kind": "system",
            "content": "You are a helper.",
            "time": "2026-01-01T00:00:01+00:00",
            "seq": 2,
        },
    },
    "next": {"message": 1, "task": 0, "artifact": 0},
    "seq": 2,
    "system": "You are a helper.",
    "prompt_files": [{"name": "role", "content": "You are a helper."}],
}
```

这些真名属于这份记忆。持有它的每个进程共用这些真名。进程自己的地址也写成 `message/0`，它可以指向另一个真名。那张表是这个进程的页表，由 `MemoryRuntime` 保存，并可以随存储后端恢复。模型默认只看到 system 提示词和当前用户消息。它用 `message/0` 这样的地址读取旧行。

## 写下一行

`MemoryRuntime` 把一行提交到 `MemoryStore`，再记入每个持有者的页表。

| 入口 | 结果 |
|---|---|
| `class_of(kind)` | `user` 和 `model` 是 `message`。`tool` 是 `artifact`。`other` 是 `task`。其他种类被拒绝。 |
| `append` | 追加一行，并返回写入者自己的地址，例如 `chat/message/0`。 |
| `write_system` | 保留一个有名字的提示文件，并把每个文件拼进 system 行。 |

一行存 `class`、`kind`、`content`、`time` 和 `seq`。可选的 `state` 是 `asked`、`continue`、`resulted`、`rejected` 或 `answered`。进程读自己的 `message/0` 时，用的是自己的页表。带 scope 的读取，例如 `chat/message/0`，按真名走存储里的顺序。起点超出末尾会抛出 `PermissionError`。

## 它有多大

`estimate_tokens` 估算即将发送的文本。一次读取的预算是模型上下文上限减去 system、当前页、输出预留和安全余量。超限的已点名读取会被截断或压缩；原文仍留在 `MemoryStore`。计数不扫描整本历史。

## 已知限制与暂缓事项

- **预算是估算** — `estimate_tokens` 按文本长度估算，不代替提供商的账单。
