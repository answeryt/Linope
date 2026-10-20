# process_manager

`kernel/process/process_manager` 管一个能力进程的生命周期。

一个进程对应一份 `CapabilityProcess`。它拿着启动时的激活信息和资源记录。`stop` 关闭这份记录并退回租约。`submit` 在当前进程里应答；`ping` 回 `pong`，其它调用回一条结果，不追加资源行，也不调用模型。

进程已经消失、又没自己关闭时，`reaper.py` 按传入的清理动作关闭它的记录。`liveness.py` 用来判断那一行记录对应的进程是否还在。

这里没有副本布局、自动扩缩，也没有父子进程管理。同一能力开多份，由调和器按份数各建一个 `process_id`。

文件：

- `capability_process.py`：一个能力进程、它的状态、停止和本地调用。
- `lifecycle.py`：进程状态。
- `handle.py`：对外只露出句柄视图。
- `client.py`：一次调用的回执。
- `liveness.py`、`reaper.py`：存活检查，以及进程已死时关闭记录。
- `monitor.py`：把进程收成可观察的句柄。
- `tool_dispatch.py`：给已经存在的进程准备一条工具请求。资源总账不在这里，而在 `kernel/process/resource_record.py`。
