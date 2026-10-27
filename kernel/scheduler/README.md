# scheduler

English | [中文](README.cn.md)

One scheduler for model turns, pointer steps, resource routing, and thread admission. The raw memory dict is [`kernel/resource/memory`](../resource/memory/README.md). Which peer is chosen is [`kernel/load_balancing`](../load_balancing/README.md).

## Contract

| Entry | Role |
|---|---|
| `turn` | Runs one `load message` until the model answers. Returns what the terminal shows. |
| `classify` | Splits one checked step into `MemoryRead`, `ActionCall`, or `Answer`. Parsing does not run the step. |
| `route` | Hands a body to a peer that holds the named resource kind and identity. The caller supplies the channel and the opener. |
| `run_runtime` | Claims and admits requests onto one process runtime until that process asks to stop. |

`memory_space.py` is the pointer space. `space` on a memory grant names which classes belong in the pointer. The classes are `system`, `message`, `task`, and `artifact`. The pointer is the right to enter one memory resource. `message/0` and `message/0-10` are selectors inside that resource.

## Sharing one memory through addresses

The shared notebook is one memory entity. [`kernel/resource`](../resource/README.md) makes that entity when this launch names `memory` in `shared` and the claims use the same scope. The rows and their stored names live in [`kernel/resource/memory`](../resource/memory/README.md). This directory keeps a private address list for each process that holds the entity.

`access.py` stores those lists in `_MAPS`, keyed by process id and resource id, then by class. `remember` asks the memory module to append one row. The stored name comes back as `message/0`, then `message/1`, from the entity's own counter. `_map_real` appends that stored name onto every current holder whose `space` includes the class:

```python
for pid, grant in holders:
    if class_name not in visible_classes(grant):
        continue
    rows = _rows(pid, resource_id).setdefault(class_name, [])
    rows.append(real)
```

The address told back to the writer is that process's own index, prefixed by the scope: `chat/message/0`. The index is `len(rows) - 1` on the writer's list. Another holder that already had rows receives the same stored name at the next index on its own list.

A read of `message/0` uses this process's list, then loads the row by the stored name:

```python
rows = list(mapping.get(class_name) or [])
real = rows[index]
item = stored.get(real)
```

`memory_contents` returns both. `address` is the index this process used. `real` is the stored name.

Two processes can both say `message/0` and mean different stored rows. A process that starts later has an empty list. Rows written before it held the memory stay off that list. Its `message/0` is the next row written while it holds the memory and can see that class.

| When | Stored name | Process A's address | Process B's address |
|---|---|---|---|
| A writes the first line. B has not started. | `message/0` | `message/0` | — |
| B starts, then A writes the next line. | `message/1` | `message/1` | `message/0` |

A's `message/1` and B's `message/0` are the same row. A class left out of a process's `space` is never appended to that process's list.

A read that names a scope, such as `chat/message/0`, does not use the private list. `real_slice` walks the stored names in the entity whose scope is `chat`. The walk is allowed when this process has a pointer for that scope.

`access.py` approves and performs that access. `capacity_full` is true when the token count is at least a positive context limit. The token number comes from [`kernel/calculate`](../calculate/README.md). The address lists stay in `_MAPS` for this run. The memory dict keeps the rows.

`turn` gives the model one page from [`kernel/communication`](../communication/README.md). Every `load message` for a process with memory enters `turn`, and so does an `ask` whose receiver has memory. Whether the window can launch another process only decides whether the page offers `process start`. The reply is checked in communication, then this directory decides whether it may run. A read stays a read: it does not start a process or call a tool. Only a step that passes is executed. The result is written back to memory, and the next page is given. There is no step limit.

`route` refuses a missing channel and a process limit below 1. It does not take a lease. A new process, when one is required, is started by the opener the caller supplies. That opener is the existing reconciler.

## Known Limitations and Deferred Work

- **A turn has no step cap** — `turn` keeps walking until the model answers or the call fails.
- **Address lists last for this run** — `_MAPS` starts empty in a new run. Stored rows remain in the memory dict. A later write appends only that new stored name, so this process's `message/0` is the new row. Rows already stored are read with a scoped address such as `chat/message/0`.
