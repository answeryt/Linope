# process_manager

[English](README.md) | 中文

管一个已经开起来的能力进程：问它、等它回答、确认它还活着、关掉它。声明怎么编译在 [`reconcile.py`](../reconcile.py)。新工作交给哪个进程在 [`kernel/load_balancing`](../../load_balancing/README.cn.md)。资源账本在 [`resource_record.py`](../resource_record.py)。

一个进程是一个 `CapabilityProcess`。它拿着启动时的激活和自己的资源记录。同一能力开多份，就是协调器为每一份建一个操作系统 pid。没有父子一起停。

## 每个脚本

`capability_process.py`

这个进程本身。`ask` 送一条消息并等回复。`submit` 接一次调用，交回一张 `Receipt`，不往资源账本追加一行。`answer_ping` 只在被问的 pid 就是自己时回答 `pong`，并带上这次的序号；双方都写了通道时，通道也必须一样，否则不回答。序号对不对，由 [`kernel/command/process`](../../command/process/README.cn.md) 再查一次。`stop` 关掉这份资源记录，把租约还回去。

`lifecycle.py`

进程状态的名字：`created`、`starting`、`running`、`stopping`、`stopped`、`failed`。

`handle.py`

给外面看的 `ProcessHandle`。上面只有这个进程的 pid，看不到资源实体。

`client.py`

`Receipt` 是一次调用的回执。它记请求号和 pid，不把整个进程对象留在手里。`ready` 看回复到了没有，`wait` 等到这次调用结束。

`liveness.py`

账本上的 pid 是否还是当时那个操作系统进程。`process_matches` 对得上才算还活着。`reap_dead` 把已经死掉、但账本仍标着就绪的记录关掉。

`reaper.py`

`ProcessReaper` 看一行记录。状态是 `starting` 或 `running`，而进程已经不在了，就执行传进来的清理。

`monitor.py`

看这些对等进程，并可以停掉其中一个。它不把它们收成父子关系。`handle` 取出对外的 pid 视图。`reap_if_dead` 交给 `reaper.py`。

`tool_dispatch.py`

给一个已经存在的进程准备一次工具调用，消息是 `load`、种类 `tool`。名字前面没有 `tools.` 会补上。[`profiles.py`](../README.cn.md) 的 `tool_allowed` 在当前权限或工具名单不允许时直接拒绝。读取 `tool_schemas` 用同一条检查，被拒绝的工具不返回说明。也可以只给出该启动的能力名，不在这里启动。

`__init__.py`

对外给出 `CapabilityProcess`、`ProcessActivation`、`ProcessStatus`。
