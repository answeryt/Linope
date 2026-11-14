# communication

[English](README.md) | 中文

本目录建造模型看到的页面，检查模型的回复，并写下该进程自己的笔记。谁可以进入一份记忆、可以读哪一段，在 [`kernel/scheduler`](../scheduler/README.cn.md)。原始行在 [`kernel/resource/memory`](../resource/memory/README.cn.md)。本目录不定义第二套准入规则。

| 文件 | 职责 |
|---|---|
| `page.py` | 一页模型页：记忆入口、它可以读的地址，以及它可以运行的命令 |
| `channel.py` | 本进程的笔记，以及调用方已经打开的通道上的 `deliver` / `publish` |
| `address.py` | 把记忆调用转发到 `kernel.scheduler.access` |

## 契约

这一页可以提供哪些命令行，由 [`capability/agent_loop`](../../capability/agent_loop/linope/loop.py) 决定。内核执行交给它的命令行，不负责挑选这份名单。

`MemoryChannel` 向本进程的记忆写入一行。`send` 通过 `remember` 记录。这些是进程自己的笔记。它们不是两个服务之间的传输。

另一个服务只能通过调用方已经打开的通道到达。地址和主题是普通字符串。

```python
from kernel.communication.channel import deliver, publish

deliver(channel, "1", {"kind": "user", "content": "hello", "state": "asked"}, "2")
publish(channel, "weather", {"kind": "user", "content": "hello", "state": "asked"})
```

内核不打开端口，也不选择传输。已经到达这个窗口的话，作为 `load message` 交给该进程。进程有没有记忆，只说明它有没有一块记事本。转圈的是 [`capability/agent_loop`](../../capability/agent_loop/linope/loop.py)。没有记忆的进程收到的是原话。

行字段以及状态 `asked`、`continue`、`resulted`、`rejected` 和 `answered` 由 [`kernel/resource/memory`](../resource/memory/README.cn.md) 存储。进程是在睡还是在工作，在 [`kernel/trace`](../trace/README.cn.md)。

## 已知限制与暂缓事项

- **没有内建的远程传输** — `deliver` 和 `publish` 只在调用方传入的通道对象上发送。另一台机器没有回复，是调用方的超时。
