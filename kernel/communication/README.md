# communication

English | [中文](README.cn.md)

This directory builds the page a model sees, checks the model's reply, and writes that process's own notes. Who may enter a memory, and which span they may read, is [`kernel/scheduler`](../scheduler/README.md). The raw rows are [`kernel/resource/memory`](../resource/memory/README.md). This directory does not define a second admission rule.

| File | Role |
|---|---|
| `page.py` | One model page: the memory entry, the addresses it may read, and the commands it may run |
| `channel.py` | This process's notes, and `deliver` / `publish` on a channel the caller already opened |
| `address.py` | Forwards memory calls to `kernel.scheduler.access` |

## Contract

Which command lines a page may offer is decided in [`capability/agent_loop`](../../capability/agent_loop/linope/loop.py). The kernel executes a command line it is given. It does not choose the list.

`MemoryChannel` writes one row into this process's memory. `send` records through `remember`. These are the process's own notes. They are not a transport between two services.

Another service is reached only through a channel the caller already opened. Addresses and topics are ordinary strings.

```python
from kernel.communication.channel import deliver, publish

deliver(channel, "1", {"kind": "user", "content": "hello", "state": "asked"}, "2")
publish(channel, "weather", {"kind": "user", "content": "hello", "state": "asked"})
```

The kernel does not open a port and does not choose a transport. Words that have already arrived in this window are given to that process as `load message`. Memory means the process has a notebook. The turn itself is [`capability/agent_loop`](../../capability/agent_loop/linope/loop.py). A process with no memory receives the words as they arrived.

Row fields and the states `asked`, `continue`, `resulted`, `rejected`, and `answered` are stored by [`kernel/resource/memory`](../resource/memory/README.md). Whether the process is sleeping or working is [`kernel/trace`](../trace/README.md).

## Known Limitations and Deferred Work

- **No built-in remote transport** — `deliver` and `publish` send only on the channel object the caller passed in. A missing reply from another machine is the caller's timeout.
