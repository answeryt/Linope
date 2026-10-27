# command/ — `linope` 命令入口

[English](README.md) | 中文

`dispatch.py` 只认第一个词，把后面的参数交给对应脚本。不认识的词，或用法不对，退出码是 2。

命令分成两层。第一词是对象：建文件、开进程、看进程、把几个已经在跑的进程记成一个服务。窗口开着之后再敲的短行，是对那个已经打开的进程说话，例如 `load message`。短行不新开进程。

这一层不读模型卡片，不执行工具，也不从模型输出里再挑命令。卡片在能力插件里。工具在工具进程里。模型回复怎么解析，在 [`kernel/communication`](../communication/README.cn.md)。

| 目录 | 管哪些命令 |
|---|---|
| [`file/`](file/README.cn.md) | `create`、`load env` |
| [`process/`](process/README.cn.md) | `process start`，以及窗口里的 `load`、`ask`、`ping`、`list`、`show`、`trace` |
| [`screen/`](screen/README.cn.md) | `resource serve`，以及把模型正在吐出的一段文字打到终端 |

`service` 的规则在 [`kernel/services`](../services/README.cn.md)。`log` 打的回合日志在 [`kernel/trace`](../trace/README.cn.md)。

## 对象命令

这些是对象命令，窗口外也能敲。标志的完整表在上面各目录的 README 里。

`create <path> [-- name=value]`

在本机建一个文件。`--` 后面可以跟一条 `name=value`，写进这个文件，用来准备环境变量。这不是开进程。

`load env <path>`

记住这份环境文件。同一窗口里，下一次 `process start` 没写 `--env-file` 时就用它。值留在文件里，命令只打印路径。

`process start <capability>`

按能力名开进程。例如 `process start model.openai_chat_model` 开一个模型进程，`process start tools.read` 开一个读文件的工具进程。能力自己的 `capability_profile` 说明这次要哪些资源。一个操作系统 pid 一份资源记录。命令打印 `pid=`，然后留在当前窗口里，等你把正文送进去。它不自己去调模型。

`--count 2` 开两份，两份是对等进程，不是父子。`--share memory` 才让这次启动共用记忆；不写的话，每份各有各的。`--with memory=chat` 是在画像之外再要一种资源。`--once` 表示送完一次 `load` 就关掉。`--ping` 是开完之后问一声，没人回答就失败。

`process list`

列出窗口里的进程：pid、在忙还是在闲、记录状态。不启动进程。

`process show <pid> [address]`

看这一个进程的页面。它有记忆时，带上该地址上的内容。

`process trace <pid>`

看这个进程从闲到忙的活动记录。

窗口关掉之后，`list`、`show`、`trace` 改读磁盘上的账本和日志。对话正文在记忆里，不在账本文件里。

`service start <pid> [<pid> ...]`

把几个已经在跑的 pid 记成一个服务，写入 `.linope/services.json`。缺一个、死一个、重复一个，整次都不写。它不负责把进程开起来。开进程仍是 `process start`。

`service load <服务编号> -- <正文>`

只在窗口里用。它找出这个服务里唯一还开着的模型进程，把这一行改写成 `load message <那个 pid> -- <正文>`，再交给那个进程。没有模型，或有两个模型，就拒绝。服务不决定下一步叫哪个工具。

`resource serve [--host 127.0.0.1] [--port 0]`

在本机起 HTTP 服务，开发者用浏览器看资源页。模型要搜东西或改文件时不要写它。

`log [pid]`

按时间打印回合日志：人敲过的每一行，以及模型每次写完时的原文。`log <pid>` 只留这个进程的行。人敲的那一行没有 pid，所以只出现在不带 pid 的 `log` 里。

`terminal` 和 `session`

打开同一个窗口。要接着对进程说话，就在这个窗口里写下面的短行。

## 窗口里的短行

`process start` 留下窗口之后，由 [`process/listen.py`](process/listen.py) 读这些行。它们不写入资源账本。参数和失败情况见 [`process/`](process/README.cn.md)。

`load message <pid> -- <正文>`

把这一句送给那个模型进程。进程必须已经开着，并且是模型。有记忆时，这一句记进它的记忆，并作为页面回合走完，直到模型回答。更早的行在这一页上只保留地址。窗口能不能启动进程，不决定这一问是否走页面；只有它能够启动时，页面才提供 `process start`。

`load message <pid> <地址> -- <问题>`

把该地址上的原文放进模型看到的第一页，然后把问题记入记忆并走完这一问。地址写成 `message/0`、`message/0-3` 或 `chat/message/0`。几个地址用空格分开。地址不对时，问题不会写入记忆。列出这个进程能看见的全部行，仍是 `show <pid>`。

`load tool <pid> -- <JSON>`

把这一次调用送给那个工具进程。进程必须已经开着，并且是工具。

`load message <pid> -- <序号> <文件>`

把一个 `.txt`、`.md` 或 `.json` 文件抄进该进程记忆的 `system`。这一步不调用模型。没有记忆的进程会拒绝。

第二个词不是 `env` 的 `load`，`dispatch.py` 不把它当成 `load env`，而是交给还开着的窗口。所以 `load env` 和 `load message` 是两件事：前者记住环境文件，后者对进程说话。

`ask <pid> -- <任务>`

把任务交给另一个已经开着的进程。对方看不到发送方的记忆。对方有记忆时，走它自己的页面回合，任务和回答都写入它的记忆。对方没有记忆时，收到任务原文。结果写回发送方。窗口里除了对方，还必须正好还有一个活着的进程当发送方。

`ping <pid>`

问这个进程还在不在。回答必须是带同一序号、同一 pid 的 `pong`。

`list`、`show <pid>`、`trace <pid>`

和上面的 `process list`、`process show`、`process trace` 相同，只是写在窗口里，看的是这个窗口里的进程。
