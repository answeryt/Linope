# thread

[English](README.md) | 中文

`kernel/thread` 在一个能力进程里面跑工作。异步插件在这个进程的事件循环上等待。同步插件、会堵住的 SDK、文件操作和外部命令交给工作线程池，循环才能继续往下走。

对外的身份是 `process_id`。这些脚本不取得资源租约，也不读资源实体 id。环境、资源句柄、适配器和 `call_params` 用进程已经准备好的那一份。这个循环的准入是 [`run_runtime`](../scheduler/README.cn.md)，在 `kernel/scheduler/threads.py`。工作线程池在 [`kernel/load_balancing/workers.py`](../load_balancing/workers.py)。

## 脚本

| 脚本 | 作用 |
|---|---|
| `__init__.py` | 第一次用到某个名字时才导出 |
| `contracts.py` | 限额、一条已认领的请求，以及运行时要调用的收件箱 |
| `limiter.py` | 同时可以跑几条请求 |
| `runtime.py` | 跑一条请求：异步插件直接等待，同步插件交给线程池 |

`__init__.py` 通过 `__getattr__` 导出 `ThreadPolicy`、`ClaimedRequest`、`ThreadInbox` 和 `ThreadRuntime`。第一次用到某个名字时，才导入定义它的模块，这样导入本包不会把运行时拉进进程的导入关系里。

`contracts.py` 放这几种形状。

`ThreadPolicy` 是一个进程的一组数字。默认是同时一条任务、一个同步工作线程。数字超出允许范围时，策略在创建时被拒绝。

| 字段 | 默认 | 含义 |
|---|---|---|
| `max_concurrent_tasks` | 1 | 同时进行的请求上限，异步和同步算在一起 |
| `min_concurrent_tasks` | 1 | 和策略一起保存。至少为 1，并且不能高于上限。本目录准入时用的是上限，以及账本上的在途上限 |
| `max_sync_workers` | 1 | 同步线程池最多用几条操作系统线程 |
| `claim_lease_seconds` | 120 | 交给 `inbox.claim` 的一次认领时长 |
| `shutdown_timeout_seconds` | 5 | 进程要停时，等待已经在跑的请求多久 |
| `poll_interval_seconds` | 0.05 | 收件箱没有可认领的请求时，循环睡多久 |
| `session_affinity` | 关 | 打开后，同一个 `session_id` 的请求一个接一个跑 |

`ClaimedRequest` 是从收件箱取到的一条请求：`request_id`、`process_id`、`body`、新的 `claim_token`，以及认领它的 `worker_id`。`ThreadInbox` 是运行时用的三个调用。`claim` 为本进程取下一条请求，没有就什么都不返回。`complete` 带着这个 `claim_token` 把回复写回去。`lookup` 按 id 读一条请求。收件箱的实现必须让同一个进程 id 的 `claim` 是原子的。`ThreadAdapter` 是可选的插件形状：同步插件实现 `handle`。

`limiter.py` 是 `AsyncTaskLimiter`。它是一个 asyncio 信号量。`slot` 在一条请求开始前占一个位置，结束时还回去。`expand_to` 把上限调高。更小的数字不会把信号量缩小。`available` 是现在还空着的位置数。运行时用 `max_concurrent_tasks` 创建它。

`runtime.py` 是 `ThreadRuntime`。`run` 把循环交给 `kernel.scheduler.threads.run_runtime`。那个循环从收件箱认领，再回调本文件来执行每一条请求、对齐上限，并在进程要求停止时把在途请求排空。

一条请求走 `_execute_request`。它先占一个限额位置，再进入 `_dispatch`：

| 消息 | 发生什么 |
|---|---|
| `operation` 是 `ping` | 返回 `pong`，带上本进程的 pid、`seq` 和 `channel`。消息里的 `pid` 不是本进程，就是错误。 |
| 适配器是异步的 | 在循环上等待 `handle_async`；没有它就等待 `handle`。等网络时不占操作系统工作线程。 |
| 适配器是同步的 | `adapter.handle` 在 `WorkerPool` 上跑。池必须已经启动。 |
| 没有适配器 | 返回错误 `This process has no load`。 |

设了 `is_async` 的适配器，或者 `handle_async` 是协程函数的适配器，算异步。没有标成 `sync_thread_safe` 的同步适配器最多一个工作线程。异步适配器不用同步工作线程。

第一次认领之后，`_align` 从进程账本读 `worker_ceiling` 和 `inflight_ceiling`。在途数至少为 1 时，用 `expand_to` 抬高限额。工作线程数经过上面的同步插件上限之后，用 `set_max_workers` 设到池上。

`session_affinity` 打开时，带着同一个 `session_id` 的请求共用一把锁，当前这条做完，下一条才开始。

`_drain` 最多等 `shutdown_timeout_seconds`，等已经在跑的请求。到时还在跑的会被取消，同步池随后关掉，不再等待。
