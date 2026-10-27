# trace

[English](README.md) | 中文

两份只追加的文件。调度器和模型页都不读它们。

## 契约

| 文件 | 它存什么 | 命令 |
|---|---|---|
| `.linope/activity.jsonl` | 进程是 `sleeping`、`self`、`with` 还是 `closed`，按发生顺序。`with` 可以点名对方和方式，例如 `task`。 | `trace <pid>` 打印该进程 |
| `.linope/log/session.jsonl` | 回合日志：人键入的每一行，以及模型每次写完时的原文和判定。人键入的行没有 pid。 | `log` 按时间顺序打印每一行。`log <pid>` 只打印 `pid` 相符的行。 |

`activity.py` 是 `ActivityLog`。`journal.py` 是 `Journal`。`journal_path` 是工作目录下的 `.linope/log/session.jsonl`。`journal_beside` 是账本文件旁边的日志。

`kernel/command/log.py` 打印日志。文件缺失时打印 `No turn log yet` 并以 1 退出。没有任何行出现该 pid 时以 1 退出。非数字 pid 以 1 退出。

没有活窗口时，`trace` 读取已保存的活动文件。命令入口在 [`kernel/command/process`](../command/process/README.cn.md)。

## 已知限制与暂缓事项

- **没有跨度树** — 诊断记录是可选的，持有 `trace_id`、错误文本和错误所在处。它不是第二套完成状态，也不持久化任务状态。
