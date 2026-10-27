# memory

English | [中文](README.cn.md)

The notebook for one memory entity: one dictionary of rows. Who may read or write, and which `message/0` a process means, is [`kernel/scheduler`](../../scheduler/README.md). Whether two processes hold this same dictionary is [`kernel/resource`](../README.md). This directory stores the rows and their stored names.

## The dictionary

`open_state` opens a new entity as the range named by its scope:

```python
{"address_space": {"scope": "chat"}}
```

`scope` is the identity of this memory, such as `chat`. `prepare` copies a state and puts an empty `address_space` in when that key is missing.

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

These stored names belong to the entity. Every process that holds the entity shares them. A process's own address, also written `message/0`, can point at a different stored name. That list is kept by the scheduler, in `_MAPS`.

## Writing a row

`store.py` edits this dictionary.

| Entry | What happens |
|---|---|
| `class_of(kind)` | `user` and `model` are `message`. `tool` is `artifact`. `other` is `task`. Any other kind is refused. |
| `append_row` | Appends one row and returns its stored name, such as `message/0`. |
| `write_prompt` | Keeps one named prompt file and joins every file into the system row. |

`append_row` reads `next` for that class, stores the row at `class/that number`, then adds one to `next`. The text passed in is stored as `content`. A row also stores `class`, `kind`, `time`, and `seq`. Optional `state` is `asked`, `continue`, `resulted`, `rejected`, or `answered`. Leave it out, and the row has no `state` field. No token count is written onto the row.

`write_prompt` keeps `prompt_files`. Each file has a `name` and a `content`. The same name replaces that file. `place` starts at 1 and is the position in the list. With no `place`, a new file goes at the end, and an existing file stays where it was. The texts are joined with a blank line into the `system` row. The same text is also stored at `state["system"]`.

`real_slice` walks stored names for one class. `system` is the single system row. The other classes walk `class/0` through `class/next - 1`. A start past the end raises `PermissionError`. The scheduler uses this walk for a scoped read such as `chat/message/0`. A process reading its own `message/0` uses its private address list in the scheduler, then loads the row stored under the name that list holds.

## How big it is

`token_meter.count_state(model, state)` adds up tokens for the texts already in the dictionary. `text_contents` gathers every row's `content`, and `state["system"]` when no system row was among the rows. The number is computed when asked. Counting uses [`kernel/calculate`](../../calculate/README.md).

## Known Limitations and Deferred Work

- **The meter only sums stored text** — `count_state` walks `text_contents` and does not keep a separate token field on the row.
