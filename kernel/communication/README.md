# communication

这是内核的送信层。进程和服务都通过它通信。进程怎么启动、怎么停、租约怎么还、编制怎么算，仍在 `kernel/process`。

两边都按账本上的 `process_id` 认人。没有父进程和子进程。拉起进程时不继承管道。

没选择通道时用 `ledger`，也就是原来的账本信箱。`linope channels` 列出已登记的名字，`linope channel 名字` 记下选择，`linope channel off` 回到账本信箱。选择写进启动包，发出请求的进程和被点名的进程读同一份名字。

## 抽象层

大家只依赖 [channel.py](channel.py)。一种通道要能完成这些动作：

- `bind(process_id)`：这个进程开始接收发给自己的消息。账本信箱这里什么都不做。
- `submit(process_id, body, sender_id)`：把一条消息交给该进程，马上返回回执号。
- `take(process_id)`：取出一条，里面有 `request_id` 和 `body`。没有就返回空。
- `claim(process_id, worker_id, lease_seconds)`：原子认领一条请求，返回
  `claim_token`。没有档位、依赖、服务或最晚开始时间的请求仍按到达顺序认领。
  带了这些字段的请求要先被标成已预定，并且已经选中这个进程，才会被认领。
  过期认领可以重新排队，供进程内异步任务或同步插件线程使用。
- `complete(request_id, reply)`：写上回复。
- `lookup(request_id)`：调用方查看 `status` 和 `reply`。
- `close()`：关掉这个进程自己打开的套接字或订阅。

登记和取出在 [registry.py](registry.py)：

- `register_channel(name, factory)`：用一个名字记住工厂。工厂接收 `ChannelOpen`，返回一个通道。`off` 是保留名。名字不能是空白。
- `unregister_channel(name)`：去掉后加的通道。`ledger`、`zeromq`、`grpc`、`nats` 去不掉。
- `load_channel(name, opened)`：按名字造出一份通道。没有这个名字会报 `KeyError`，并列出已知名字。
- `channel_names()`：按字母顺序列出已登记的名字。

开发者接入自己的方法时，写一个有上面动作的对象，调用 `register_channel("自己的名字", 工厂)`。调和器和运行时之后只通过 `load_channel` 使用它。

## 内置

- `ledger`：间接通信。请求和回复写在账本的 `process_requests` 表里。这是默认方法。
- `zeromq`：进程间通信。被点名的进程自己绑定 `tcp://127.0.0.1:0`，把地址写入账本。其他进程按 `process_id` 查到地址再发。用 DEALER/ROUTER，`submit` 不等待回复。
- `grpc`：远程调用。代码放在 `grpc_channel`，登记名仍是 `grpc`，这样不会挡住第三方库 `grpc`。一个通用的 `Call`，正文仍是原来的 JSON 字典。监听地址同样按 `process_id` 写入账本。装入仍是正文里的 `operation: load`，探活仍是 `ping`。
- `nats`：间接通信。主题是 `linope.{process_id}`，回复走收件箱。需要本机已经有 NATS 服务器。`linope channel nats` 默认使用 `nats://127.0.0.1:4222`，后面可以再写一个地址。

`process_id` 仍然是唯一公开的通信身份。`worker_id` 和 `claim_token` 只用于
进程内部认领和防止过期执行单元覆盖新结果，不会成为新的通道地址。

关联字段可以放进同一条正文。通道只负责把正文送到目标进程。请求是否还在等待、已被认领或已经回复，只看信箱里的这条记录。

超媒体表示可以放进现有正文，不另开一种通道。观察的形状是：

```json
{
  "operation": "observe",
  "href": "http://127.0.0.1:49152/resources/<id>",
  "representation": {}
}
```

`submit` 把这份表示交给一个 `process_id`。两个模块各看一份时，对两个进程各提交一次。`take` 和 `claim` 只表示这封信到了谁手上，不调用 `pin`、`swap`、`admit` 或 `compress`。副本里的菜单可能已经过期，执行前要重新读取 `href`。

ZeroMQ 和 gRPC 只在账本里记录监听地址，业务正文不进那张表。

## 安装

默认账本信箱不需要额外的包。选中下面的方法时才要安装：

```powershell
pip install pyzmq grpcio nats-py
```

没装对应的包就选中它，会说明要执行的安装命令。
