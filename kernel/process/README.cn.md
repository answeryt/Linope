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
| `profiles.py` | 模型可以被提供哪些工具，以及工具进程租用的沙箱模式。规则见下文。这不是 `capability_profile`。 |

## 模型可以使用哪些工具

分类看的是 `tools.` 后面的名字。[`capability/tools`](../../capability/tools/README.cn.md) 下的文件夹只决定文件放在哪里。

| 类别 | 名字 | 工具进程上的沙箱 |
|---|---|---|
| 只读 | `read`、`glob`、`grep`、`read_image` | `read-only`，不能再放宽 |
| 命令 | `bash`、`pwsh`、`bash_persistent`、`run_code`、`terminal`，以及任何以 `terminal_` 开头的名字 | 上限 `danger-full-access`，默认 `workspace-write` |
| 写入 | 其余工具名，包括 `write` 和 `edit` | 与命令相同的上限和默认 |

`tool_allowed` 是 [`kernel/communication`](../communication/README.cn.md) 的 `offers.py` 和 [`process_manager`](process_manager/README.cn.md) 的 `tool_dispatch.py` 调用的函数。`tools.` 以外的名字留着不动。模型启动时带了 `capabilities` 名单，就只留下名单上的名字。`permission` 为 `read-only` 时，再只留下只读类。`workspace-write` 和 `danger-full-access` 不按类别删工具。

这两个值都是启动模型时的 `--change`：

```text
linope process start model.openai_chat_model --change permission=read-only --change capabilities=read,glob
```

`permission` 是 `read-only`、`workspace-write` 或 `danger-full-access`。`capabilities` 可以不写。没有这份名单时，权限仍然允许的工具都会被提供。模型卡片把两者记在 `settings` 上。有权限时还会按该模式租一份沙箱。`reconcile.py` 把这个模式记成会话的一条 `sandbox/mode` 事件。

工具进程自己启动时，`tool_with_workspace` 租用工具、沙箱和账本通道。只读工具保持 `read-only`。写入或命令工具从 `workspace-write` 开始，除非这次启动点了模式；结果不会超出该工具的上限，也不会超出已经记下的会话模式。[`kernel/environment`](../environment/README.cn.md) 按房间上的模式执行：只读房间拒绝写文件，受约束的模式会包装外部命令。`tool_only` 只租用工具和账本通道，没有沙箱。

创建顺序是：取得操作系统 pid，打开一份空记录，按声明写入租约，建造房间，然后把记录标为就绪。

`kernel/resource` 里的 `compile_declaration` 把种类和身份哈希成实体键。调用参数留在 `call_params`，不会变成另一个实体。一个种类保持独占，直到这次启动在 `shared` 里点名它。关闭记录会归还其上的每一份租约。池在没有任何记录仍占用某个实体时卸载它。
