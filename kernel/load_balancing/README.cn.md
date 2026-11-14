# load_balancing

[English](README.md) | 中文

一个请求点名资源种类和身份，不点名 pid。本目录从账本上读出谁还占着这份资源、谁还接得下新工作，然后选一个。它不领取租约。真正把请求送出去的是 [`kernel/scheduler`](../scheduler/README.cn.md) 的 `route`，它调用这里的选择和开进程。线程是 [`kernel/thread`](../thread/README.cn.md) 里的 task。

## 每个脚本

`hints.py`

从账本里列出还占着这份资源的进程。代码里这一行叫 `Seat`，就是该进程此刻的负荷：几件还在等、几件已经领走、上下文窗口满了没有、最近一次来回花了多久、这份资源能不能和别人共用。不另做一张忙闲表。`one_resource` 要求这些进程占的是同一份资源。各拿各的副本不能当成一池来分活。

`pick.py`

在还接得下新工作的进程里挑一个。两个或更少时，挑手头活更少的。多于两个时，随机抽两个，留下手头活更少的。比较顺序是：已经领走的件数、还在等的件数、最近来回时间、进程 id。

`process_scale.py`

开一个新的对等进程，或请空闲的对等进程停掉。`open_peer` 调用协调器去开；进程数已经到上限就拒绝。`close_idle` 请空闲进程停止，至少留下下限那么多个。还在干活的不停。属于某个服务的不停。`reconciler_opener` 把一次 `reconciler.start` 包成「再开一个」的函数。

`inflight.py`

同时可以等多少个模型回复。`sample` 记一次往返时间，把下一次允许的等待数夹在最小值和最大值之间。往返变长就收紧，变短就放开。

`relieve.py`

[`kernel/calculate`](../calculate/README.cn.md) 报压力时，为该进程再开一条线程。好几条理由同时成立也只加一条。找不到记录时保持 1。

`route.py`

把 `kernel.scheduler.route` 再导出一次。选择算法不写在这个文件里。

`__init__.py`

对外只给 `route`。

## 已知限制与暂缓事项

- **`relieve` 自己没有帮手上限** — 每次压力成立都加一。线程数的天花板在 `workers.raise_on_process` 和 `scheduler.route`。
