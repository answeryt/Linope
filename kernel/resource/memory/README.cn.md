# memory

[English](README.md) | 中文

一份记忆实体的笔记本：一个装着行的字典。谁可以读或写，以及一个进程说的 `message/0` 指的是哪一行，在 [`kernel/scheduler`](../../scheduler/README.cn.md)。两个进程是否持有同一本字典，在 [`kernel/resource`](../README.cn.md)。本目录保存这些行和它们的真名。

## 这本字典

`open_state` 把一个新实体打开为它的 scope 所命名的范围：

```python
{"address_space": {"scope": "chat"}}
```

`scope` 是这份记忆的身份，例如 `chat`。`prepare` 复制一份状态；缺少 `address_space` 时放进一个空的。

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

这些真名属于这个实体。持有它的每个进程共用这些真名。进程自己的地址也写成 `message/0`，它可以指向另一个真名。那张表由调度器放在 `_MAPS` 里。

## 写下一行

`store.py` 修改这本字典。

| 入口 | 结果 |
|---|---|
| `class_of(kind)` | `user` 和 `model` 是 `message`。`tool` 是 `artifact`。`other` 是 `task`。其他种类被拒绝。 |
| `append_row` | 追加一行，并返回它的真名，例如 `message/0`。 |
| `write_prompt` | 保留一个有名字的提示文件，并把每个文件拼进 system 行。 |

`append_row` 读出该类当前的 `next`，把行存在 `类/这个编号` 下，再把 `next` 加一。传进来的文字存在 `content`。一行还存 `class`、`kind`、`time` 和 `seq`。可选的 `state` 是 `asked`、`continue`、`resulted`、`rejected` 或 `answered`。不给的话，这一行没有 `state` 字段。行上不写 token 数。

`write_prompt` 保留 `prompt_files`。每个文件有 `name` 和 `content`。同一名字替换那一份。`place` 从 1 开始，是它在列表里的位置。没有 `place` 时，新文件加到末尾，已有的文件留在原处。各段文字用一个空行拼成 `system` 那一行。同一段文字也存在 `state["system"]`。

`real_slice` 按真名走一个类。`system` 就是那一条 system 行。其他类从 `类/0` 走到 `类/next - 1`。起点超出末尾会抛出 `PermissionError`。带 scope 的读取，例如 `chat/message/0`，由调度器走这一趟。进程读自己的 `message/0` 时，用的是调度器里那张私有地址表，再按表里记下的真名取出这一行。

## 它有多大

`token_meter.count_state(model, state)` 把字典里已经存下的文本的 token 数加总。`text_contents` 收集每一行的 `content`；各行里没有 system 行时，再加上 `state["system"]`。这个数在询问时算出来。计数使用 [`kernel/calculate`](../../calculate/README.cn.md)。

## 已知限制与暂缓事项

- **计量只加总已存储的文本** — `count_state` 遍历 `text_contents`，不在行上另存一个 token 字段。
