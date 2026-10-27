# communication

[English](README.md) | 中文

本目录建造模型看到的页面，检查模型的回复，并写下该进程自己的笔记。谁可以进入一份记忆、可以读哪一段，在 [`kernel/scheduler`](../scheduler/README.cn.md)。原始行在 [`kernel/resource/memory`](../resource/memory/README.cn.md)。本目录不定义第二套准入规则。

| 文件 | 职责 |
|---|---|
| `page.py` | 一页模型页：记忆入口、它可以读的地址，以及它可以运行的命令 |
| `verify.py` | 把一次回复解析成读取、动作或回答。这里什么都不运行 |
| `offers.py` | 这一页此刻可以提供的命令行 |
| `channel.py` | 本进程的笔记，以及调用方已经打开的通道上的 `deliver` / `publish` |
| `address.py` | 把记忆调用转发到 `kernel.scheduler.access` |

## 契约

`verify.py` 接受三种形式：一个 `continue` JSON 对象、一行光秃的命令，或一段普通回答。光秃的命令行是指针为该行的 `continue`。恰好包着一条命令的散文就是那条命令。多条命令被拒绝。通过的步骤的 `way` 是 `read`、`start`、`tool`、`ask` 或 `answer`。[`kernel/scheduler`](../scheduler/README.cn.md) 决定该步骤是否可以运行。

`offers.py` 从 `tools.*` 和 `model.*` 能力目录列出命令。列出工具之前，[`kernel/process`](../process/README.cn.md) 的 `tool_allowed` 使用提问模型的 `permission` 和 `capabilities`。没通过的工具不出现在这一页上。尚未起来的工具或模型提供 `process start`。已经起来并且在睡的工具提供 `load tool <pid> -- `。已经起来并且在睡的模型提供 `ask <pid> -- `。正忙的不提供任何命令。

`MemoryChannel` 向本进程的记忆写入一行。`send` 通过 `remember` 记录。这些是进程自己的笔记。它们不是两个服务之间的传输。

另一个服务只能通过调用方已经打开的通道到达。地址和主题是普通字符串。

```python
from kernel.communication.channel import deliver, publish

deliver(channel, "1", {"kind": "user", "content": "hello", "state": "asked"}, "2")
publish(channel, "weather", {"kind": "user", "content": "hello", "state": "asked"})
```

内核不打开端口，也不选择传输。已经到达这个窗口的话，作为 `load message` 交给该服务唯一的模型。该进程有记忆时，这次加载在 [`kernel/scheduler`](../scheduler/README.cn.md) 里走完一个页面回合。没有记忆的进程收到的是原话。只有这个窗口能够启动进程时，页面才提供 `process start`。

行字段以及状态 `asked`、`continue`、`resulted`、`rejected` 和 `answered` 由 [`kernel/resource/memory`](../resource/memory/README.cn.md) 存储。进程是在睡还是在工作，在 [`kernel/trace`](../trace/README.cn.md)。

## 已知限制与暂缓事项

- **没有内建的远程传输** — `deliver` 和 `publish` 只在调用方传入的通道对象上发送。另一台机器没有回复，是调用方的超时。
