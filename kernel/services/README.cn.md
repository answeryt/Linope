# services

[English](README.md) | 中文

服务是一份已经在跑的进程号名单。名单是一个文件。它不是进程，也不会去启动或停止进程。

## 脚本

| 脚本 | 作用 |
|---|---|
| `__init__.py` | 导出 `ServiceBook` 和 `ServiceGroup` |
| `collection.py` | 读写服务名单文件 |

`__init__.py` 从 `collection.py` 把这两个名字再导出一次。调用方从 `kernel.services` 导入即可。

`collection.py` 放这份名单。

`ServiceGroup` 是一组：一个正整数编号 `service_id`，以及里面的进程号 `pids`。

`ServiceBook` 是这份名单的文件。路径由调用方传入。命令用的是 `.linope/services.json`。文件长这样：

```json
{"services": [{"id": 1, "pids": [11, 12]}]}
```

| 入口 | 做什么 |
|---|---|
| `groups` | 读出全部分组。文件不在时得到空元组。 |
| `get` | 按编号找一组。没有这个编号就什么都不返回。 |
| `add` | 取文件里已有的最大编号再加 1，写成新的一组。第一个编号是 1。 |

一条记录只能有 `id` 和 `pids`。多出来的字段、缺字段、编号或进程号小于等于 0、空的进程号列表、同一个进程号出现两次，都会拒绝这个文件。`add` 先写到旁边的临时文件，再替换正式文件，这样写到一半不会留下半份名单。

进程号是否还开着、一句话交给组里的哪一个模型，在 [`kernel/command/service.py`](../command/service.py)。`service start` 先查进程账本，再调用 `add`。有一个坏的 pid，就什么都不写。`service load` 调用 `get`，然后 `entry_of` 选出该组里仍打开的那一个 `model.` 进程，把这一行改写成 `load message <pid> -- <body>`。没有仍打开的模型，或者多于一个，就拒绝这一行。每个成员保留自己的 pid 和资源记录。见 [`kernel/process`](../process/README.cn.md)。
