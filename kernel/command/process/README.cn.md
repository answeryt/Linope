# process

[English](README.md) | 中文

进程命令打开一个能力，并与已经在这个窗口里的进程对话。资源记录在 [`kernel/process`](../../process/README.cn.md)。插件循环在 [`kernel/process/process_runtime`](../../process/process_runtime/README.cn.md)。

## 契约

`process.py` 接受：

```text
linope process start <capability> [--change topic=value] [--count count] [--share resource kind] [--with kind=identity] [--once] [--ping]
linope process list
linope process show <pid> [address]
linope process trace <pid>
```

在活着的窗口里，同样的词针对该窗口运行。在窗口外，`list`、`show` 和 `trace` 读取已保存的账本、活动轨迹和日志。

### 启动

`start.py` 向能力要它的画像，为每个 pid 打开一份资源记录，打印每个 `pid=`，并留在启动它的进程里。它不脱离，也不会自己进入 `process_runtime` 的请求循环。

| 标志 | 含义 |
|---|---|
| `--change topic=value` | 转给 `capability_profile`。`space` 也会抄到记忆声明上。启动模型时，`permission` 是 `read-only`、`workspace-write` 或 `danger-full-access`，`capabilities` 是可以提供的工具名单。规则在 [`kernel/process`](../../process/README.cn.md)。 |
| `--count` | 打开几份副本。省略表示一份。 |
| `--share <kind>` | 这次启动共享的种类。只是被允许共享的种类，在被点名之前仍是独占。点名一个种类不会共享其他种类。 |
| `--with kind=identity` | 声明画像尚未声明的额外种类。画像已经有的种类保持画像所写的内容。 |
| `--once` | 一次 `load` 交出去之后关闭记录并返回。 |
| `--ping` | 打开之后询问每个活着的进程，并等待 `pong`。没有回答就关闭记录，命令失败。 |
| `--cwd` | 房间的工作目录。 |
| `--env-file` | 这次启动的环境文件。省略时使用窗口记住的文件。 |
| `--max-runtime-seconds` | 这次启动的宿主执行上限。 |
| `--max-concurrent-tasks`、`--min-concurrent-tasks`、`--max-sync-workers` | 这次启动的线程策略。默认都是 1。 |

没有可用画像的能力在进程创建之前停止。契约拒绝的 `--share` 种类，包括不是资源的名字，会使启动失败。

没有 `--once` 时，命令一直留到进程退出或窗口停止。

### 窗口里的行

`listen.py` 在启动之后读行。这些行都不写入资源账本。

| 行 | 结果 |
|---|---|
| `load <kind> <pid> -- <body>` | 发给该进程已经打开的适配器。`message` 通过 [`kernel/scheduler`](../../scheduler/README.cn.md) 走完一个有记忆的模型。`tool` 是一次工具加载。 |
| `load message <pid> <地址> -- <问题>` | 该地址上的原文放进模型的第一页，然后问题记入记忆并走完这一问。地址是 `message/0`、`message/0-3` 或 `chat/message/0`。地址不对时，问题不会写入记忆。`show <pid>` 列出这个进程能看见的全部行。 |
| `load <kind> <pid> -- <n> <file>` | `.txt`、`.md` 或 `.json` 文件被抄进 `system`，不发给模型。副本序号从 1 开始。同一路径更新那一份。没有序号时，新文件放到最后，已有路径留在原处。没有记忆的进程拒绝该文件。 |
| `ask <pid> -- <task>` | 把一个任务交给该进程。发送方的记忆不附上。对端有记忆时，走它自己的页面回合，因此任务和回答写入对端的记忆。对端没有记忆时，收到的是任务原文。结果写回发送方的记忆。双方记为 `with`，然后回到 `sleeping`。必须恰好还有一个活着的进程充当发送方。 |
| `ping <pid>` | 询问该进程。`pong` 必须带相同的序号和 pid。沉默、错误序号或不同 pid 都是没有回答。 |
| `list` | 打印窗口里进程的 `pid`、活动和记录状态。 |
| `show <pid> [address]` | 打印进程页。进程有记忆时，页面包含该地址的记忆内容。 |
| `trace <pid>` | 打印该进程的活动行。 |

有记忆的进程收到 `load message` 时，总会走一个页面回合。窗口能不能启动另一个进程，不决定这一点。只有窗口能够启动进程时，页面才提供 `process start`。对自己说 `load message` 时，调用期间活动记为 `self`，返回后记为 `sleeping`。人说的话、模型输出、工具输出，以及交回来的任务结果，在该进程有记忆时写入那份记忆。这些正文不写入进程账本。工具加载原样发送它的正文。

窗口关闭之后，`show` 读取已保存的账本。对话正文留在记忆实体里，不在账本文件里。

## 已知限制与暂缓事项

- **窗口里的 `ping` 需要 pid** — 没有 pid 的 `ping` 是用法错误。启动时的 `--ping` 询问这次启动打开的每一个进程。
- **任务移交需要恰好一个发送方** — 只有恰好还有一个活着的进程可以充当发送方时，`ask` 才成功。
