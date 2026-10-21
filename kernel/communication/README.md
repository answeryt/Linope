# communication

进程之间通过共享内存看见同一份内容。每个进程有自己的地址表，写在 [`address.py`](address.py)。`message/0` 是这个进程的地址，真名在那一份 memory 实体上。按 `hello/message/0` 可以读另一份记忆。

内存页面和句柄在 `kernel/resource`。通信只通过资源池读写那份实体。

## 消息

一条消息就是记忆里的一行：`kind`、`content`、`time`、`seq`，还可以带一个 `state`。

| state | 谁写 |
|---|---|
| `asked` | 用户问了一句 |
| `continue` | 模型要走一步（命令行或 JSON） |
| `resulted` | 那一步的结果回来了 |
| `rejected` | 模型的输出没通过校验，附详情 |
| `answered` | 模型给了答案，这一问结束 |

进程本身在睡、在做、在和谁说话，看 `kernel/trace`，不在这里。

## 一问走到底

[`follow.py`](follow.py) 把一次 `load message` 走到答案为止：每次给模型一页（`kernel/hypermedia/memory_page.py`），页里列出能读的地址和能走的命令。模型的回答先交 [`verify.py`](verify.py) 校验，只有页上有的那一步才会执行，结果写回记忆，再给下一页。不设步数上限。

能走的命令由 [`offers.py`](offers.py) 列出：没起的工具给 `process start`，起了在睡的给 `load tool <pid> -- `，正在做事的不给。

## 通道

送信走 [`channel.py`](channel.py) 里的通道，用户自己选，内核不造轮子：

| 名字 | 用的库 | 安装 |
|---|---|---|
| `memory` | 共享内存（默认） | 不用装 |
| `zeromq` | pyzmq PUSH/PULL | `pip install pyzmq` |
| `grpc` | grpcio 通用方法 `/linope.Channel/Send` | `pip install grpcio` |
| `nats` | nats-py，还能广播到 `linope.all` | `pip install nats-py` |

```python
from kernel.communication.channel import open_channel
channel = open_channel("memory", pool=pool)
```
