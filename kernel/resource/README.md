# resource

`kernel/resource` 实现进程资源的关系：

`需求 → 声明 → 实体 → 租约 → 句柄`

种类登记在 [`resource_contract.py`](resource_contract.py)。现在有五种：

- `memory`：上下文。身份是 `scope`。地址映射在 `kernel/communication`，这里只留页面和句柄。
- `tool`：一个工具或一条要保活的连接。身份是 `id`。
- `sandbox`：沙箱或持久终端。身份是 `root`。
- `model`：一家厂商的一个模型。身份是 `provider` 和 `id`。
- `network`：进程之间发消息的通道。身份是 `channel`。

以后加一种资源，只在这张表里登记名字、必填身份、能不能共用，以及可选的打开和关掉函数。契约里的「能不能共用」只是资格。这次启动是否共用，由命令行 `--share` 点名，再传进编译。

目录能不能读写属于进程的房间，在 `kernel/environment`，不是一种资源。句柄上没有限额。进程只能看到句柄、种类和调用参数，看不到内部实体编号。

每个进程的资源总账在 `kernel/process/resource_record.py`。磁盘上只由 `kernel/process/ledger.py` 保存这份总账的复印件。
