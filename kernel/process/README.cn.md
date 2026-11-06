# process/ — 一个 pid，一份资源记录

[English](README.md) | 中文

能力进程是对等的。没有进程树：一个进程和它启动的进程不会作为一组一起停止。一个操作系统 `pid` 有一份资源记录。线程和服务不是资源所有者。

操作系统仍会在创建时记下创建者。本目录不从这层关系继承管道，不把进程放进作业对象或进程组，也不据此向进程发信号。新进程仍会收到创建时的环境变量，因此能在 Windows 上启动。隔离来自这份记录上的句柄。

一个进程加载一个插件。需要模型和工具的代理是若干对等进程，各自有自己的记录。

| 目录 | 职责 |
|---|---|
| [`process_creat/`](process_creat/README.cn.md) | 解析能力名，并打包一份 `ProcessActivation` |
| [`process_runtime/`](process_runtime/README.cn.md) | 加载插件，并在进程内处理请求 |
| [`process_manager/`](process_manager/README.cn.md) | 一个 `CapabilityProcess` 的生存期 |

## 契约

本目录里的文件拥有记录。启动命令在 [`kernel/command/process`](../command/process/README.cn.md)。四种资源在 [`kernel/resource`](../resource/README.cn.md)。

| 文件 | 职责 |
|---|---|
| `profile.py` | 调用第一个 `capability_profile`。能力没有可用画像时，在协调器之前抛出 `ProfileUnavailable`。这里不读卡片文件。 |
| `declaration.py` | `ProcessDeclaration` 是创建输入：能力、资源声明和 `settings`。提供者、模型 id 和温度留在 `settings` 里，不是租约。`append_chosen` 加上画像尚未声明的种类；已经存在的种类保持画像所写的内容。`stamp_memory_space` 把 `--change space=` 抄到记忆声明上。 |
| `reconcile.py` | `ProcessReconciler` 编译声明、绑定租约、按记录建造房间，然后启动。任一步失败就丢弃该记录。 |
| `resource_record.py` | 每个 pid 一份内存账户。状态为 `opening`、`ready`、`closing` 或 `closed`。 |
| `ledger.py` | 这些账户的一份文件副本，默认 `.linope/processes.json`。调用结果和文件正文不进入该文件。 |

## 模型可以使用哪些工具

[`capability/tools`](../../capability/tools/README.cn.md) 下的文件夹只决定文件放在哪里。这一页提供哪些命令，由 [`capability/agent_loop`](../../capability/agent_loop/pi/main.mjs) 决定。内核不按工具名挑选，也不按工具名改成只读。

沙盒模式在 [`capability/sandbox`](../../capability/sandbox/README.cn.md)。没人表态时默认 `read-only`。`permission` 仍是启动时的 `--change`。`reconcile.py` 把它记成会话的一条 `sandbox/mode` 事件。[`kernel/environment`](../environment/README.cn.md) 按房间上的模式执行：只读房间拒绝写文件，受约束的模式会包装外部命令。

创建顺序是：取得操作系统 pid，打开一份空记录，按声明写入租约，建造房间，然后把记录标为就绪。

`kernel/resource` 里的 `compile_declaration` 把种类和身份哈希成实体键。调用参数留在 `call_params`，不会变成另一个实体。一个种类保持独占，直到这次启动在 `shared` 里点名它。关闭记录会归还其上的每一份租约。池在没有任何记录仍占用某个实体时卸载它。
