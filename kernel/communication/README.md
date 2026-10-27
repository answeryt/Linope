# communication

English | [中文](README.cn.md)

This directory builds the page a model sees, checks the model's reply, and writes that process's own notes. Who may enter a memory, and which span they may read, is [`kernel/scheduler`](../scheduler/README.md). The raw rows are [`kernel/resource/memory`](../resource/memory/README.md). This directory does not define a second admission rule.

| File | Role |
|---|---|
| `page.py` | One model page: the memory entry, the addresses it may read, and the commands it may run |
| `verify.py` | Parses one reply into a read, an action, or an answer. Nothing runs here |
| `offers.py` | The command lines that page may offer right now |
| `channel.py` | This process's notes, and `deliver` / `publish` on a channel the caller already opened |
| `address.py` | Forwards memory calls to `kernel.scheduler.access` |

## Contract

`verify.py` accepts three forms: a `continue` JSON object, one bare command line, or a plain answer. A bare command line is a `continue` whose pointer is that line. Prose around exactly one command is that command. Several commands are refused. A passed step has `way` `read`, `start`, `tool`, `ask`, or `answer`. [`kernel/scheduler`](../scheduler/README.md) decides whether that step may run.

`offers.py` lists commands from the catalog of `tools.*` and `model.*` capabilities. Before a tool is listed, `tool_allowed` in [`kernel/process`](../process/README.md) applies the asking model's `permission` and `capabilities`. A tool that fails that check is left off the page. A tool or model that is not up offers `process start`. A tool that is up and sleeping offers `load tool <pid> -- `. A model that is up and sleeping offers `ask <pid> -- `. A busy one offers nothing.

`MemoryChannel` writes one row into this process's memory. `send` records through `remember`. These are the process's own notes. They are not a transport between two services.

Another service is reached only through a channel the caller already opened. Addresses and topics are ordinary strings.

```python
from kernel.communication.channel import deliver, publish

deliver(channel, "1", {"kind": "user", "content": "hello", "state": "asked"}, "2")
publish(channel, "weather", {"kind": "user", "content": "hello", "state": "asked"})
```

The kernel does not open a port and does not choose a transport. Words that have already arrived in this window are given to the service's only model as `load message`. When that process has memory, the load runs as one page turn in [`kernel/scheduler`](../scheduler/README.md). A process with no memory receives the words as they arrived. A page offers `process start` only when this window can launch a process.

Row fields and the states `asked`, `continue`, `resulted`, `rejected`, and `answered` are stored by [`kernel/resource/memory`](../resource/memory/README.md). Whether the process is sleeping or working is [`kernel/trace`](../trace/README.md).

## Known Limitations and Deferred Work

- **No built-in remote transport** — `deliver` and `publish` send only on the channel object the caller passed in. A missing reply from another machine is the caller's timeout.
