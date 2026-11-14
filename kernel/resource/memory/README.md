# memory

English | [中文](README.cn.md)

The logical address space of one memory resource. The rows live in a `MemoryStore`. The runtime cache serves address reads and is not sent to the model by itself. Who may read or write, and which `message/0` a process means, is [`kernel/scheduler`](../../scheduler/README.md). Whether two processes hold this same memory is [`kernel/resource`](../README.md).

## The dictionary

`open_state` opens a handle. It does not copy the rows into the resource entity:

```python
{"scope": "chat", "backend": ""}
```

`scope` is the identity of this memory, such as `chat`. The rows, sequence, and page table live in a `MemoryStore`. The default backend is the in-process `memory` backend. `linope memory backend` selects `sqlite` and a path.

`items` holds the rows. The key is the stored name: `message/0`, `task/0`, `artifact/0`, or `system`. `next` is the next number for `message`, `task`, and `artifact`. `seq` is one counter for the whole dictionary, so a later row has a higher `seq`.

After one user line and one prompt file, the dictionary looks like this:

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

These stored names belong to the memory. Every process that holds it shares them. A process's own address, also written `message/0`, can point at a different stored name. That list is the process page table kept by `MemoryRuntime`. The model receives the system prompt and the current user message. It reads an older row with an address such as `message/0`.

## Writing a row

`MemoryRuntime` commits one row to the `MemoryStore`, then records it on each holder's page table.

| Entry | What happens |
|---|---|
| `class_of(kind)` | `user` and `model` are `message`. `tool` is `artifact`. `other` is `task`. Any other kind is refused. |
| `append` | Appends one row and returns the writer's own address, such as `chat/message/0`. |
| `write_system` | Keeps one named prompt file and joins every file into the system row. |

A row stores `class`, `kind`, `content`, `time`, and `seq`. Optional `state` is `asked`, `continue`, `resulted`, `rejected`, or `answered`. A process reading its own `message/0` uses its page table. A scoped read such as `chat/message/0` walks stored names. A start past the end raises `PermissionError`.

## How big it is

`estimate_tokens` estimates text that is about to be sent. One read's budget is the model context limit minus the system text, the current page, the output reserve, and the safety margin. A named read that does not fit is truncated or compressed. The sliding-window fitter asks `python -m capability.queries tail-cut` for the cut index and does not import the compression plugins. The original row stays in the `MemoryStore`. The estimate does not scan the whole history.

## Known Limitations and Deferred Work

- **The budget is an estimate** — `estimate_tokens` uses text length. It is not the provider's bill.
