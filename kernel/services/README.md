# services

Service 是多个平级能力进程的成员集合，不是新的进程、资源或调度账。

`open` 对每个成员调用调和器，因此每个成员有自己的 `process_id` 和资源记录。服务自己没有记录。对外操作是 `submit`、`wait`、`members` 和 `close`。`close` 逐个调用成员的 `stop`，从而关闭各自的记录。

命令层没有 `service create`、`bind` 或 `call`。`process start` 会打开一个只有一个成员的服务，并停在那里。多个同角色副本由 `kernel/load_balancing` 做确定性选择。model/mcp 特化蓝图、组合调用、服务公平用量和预定调度已经删除。
