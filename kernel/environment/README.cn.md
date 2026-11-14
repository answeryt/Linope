# environment

[English](README.md) | 中文

一个能力进程的工作目录、sandbox 返回的访问策略、能跑多久、外部命令要不要套沙箱，都在这里传递。访问范围由 [`capability/sandbox`](../../capability/sandbox/README.cn.md) 决定；kernel 不再把启动 cwd 自动当成必须安全的 workspace。

聊天内容和记忆行不在这里。[`kernel/communication`](../communication/README.cn.md) 管模型页，[`kernel/resource`](../resource/README.cn.md) 管记忆。本目录不复制那两处。

三种文件模式的名字来自 [`capability/sandbox`](../../capability/sandbox/README.cn.md)：`read-only`、`workspace-write`、`danger-full-access`。本目录不自己再定义一套。工具进程拿到哪一种模式，由 [`kernel/process`](../process/README.cn.md) 在建造房间之前选定，并写在沙箱租约上。

## 每个脚本

`room.py`

把下面几块拼成一个 `KernelEnvironment`。`apply()` 只做一件事：把工作目录和明确写出的环境变量应用到当前进程。

`current.py`

记下这个进程现在用的是哪一间。`bind_room` 装上，`current_room` 取出，`using_room` 临时换一间，用完换回原来的。

`policy.py`

这次启动的时间数字：启动最多等多久、停的时候最多等多久、整个进程最长跑多久、内存上限、心跳间隔。负数会被拒绝。这些数字是宿主的限制，不是资源池里的一种资源。

`lifecycle.py`

拿 `policy.py` 里的数字做判断。到点了就请进程停止。内存超了只报告超了，不自己杀进程。心跳该来没来，也在这里看。

`shell.py`

工作目录、命令行参数、环境变量、标准输入输出接到哪里。`load env` 记住的那份文件记在 `env_file` 里，只记下要读哪些名字。密钥的值留在文件里，不放进启动时交给进程的那包数据。`apply()` 会先检查这些名字在文件里都有，然后从进程环境里拿掉，用到时再读。

`filesystem.py`

这个进程能看见哪些地方由 sandbox policy 的 roots/scope 决定。`FilesystemView` 只是把策略变成房间里的可序列化视图；host scope 可以覆盖当前主机的驱动器根，`locate` 仍执行策略返回的路径和写权限检查。

`file_io.py`

真正读文件、写文件的入口。先问 `filesystem.py` 这条路径能不能碰，再读或写。相对路径从工作区算起。写的时候父目录不存在会先建出来。

`identity.py`

这个进程是谁：pid、能力名、当前文件模式。密钥只记名字和文件位置。`resolve_secret` 在要用的那一刻才从文件里读出值。名字里带 `KEY`、`PASSWORD`、`SECRET`、`TOKEN` 的变量，在启动外部程序之前会被拿掉。

`compute.py`

外部程序能不能开、在哪个目录开、最长跑多久。工作目录必须在允许的地方里。模式要求套沙箱时，没有包装器就拒绝直接跑。线程池在 [`kernel/thread`](../thread/README.cn.md)，这里不负责开线程。

`mount.py`

路径规则和敏感路径名称由 sandbox policy 提供。`cwd` 只作为相对路径和命令启动目录；host scope 不把主目录或盘符根视为错误。`.git`、`.ssh`、`.aws`、`.env`、私钥和证书等仍可由策略列入阻止规则。

`sandbox_vocab.py`

从 `capability/sandbox/gate.py` 读取模式表、roots 和运行时 policy。`check_mode` 拒绝不认识的模式，`resolve_policy` 获取本次访问范围；`confines` 回答外部命令要不要包起来。

`session_mode.py`

会话当前用哪种沙箱模式。`effective_mode` 读最后一条 `sandbox/mode` 记录。`remember_mode` 往回合日志里追加一条。日志在 [`kernel/trace`](../trace/README.cn.md)。

`confine.py`

把工作区根和文件模式交给平台包装器。`read-only` 和 `workspace-write` 会改写要执行的命令行。`danger-full-access` 保持原来的命令行。Linux 用 bwrap 再 Landlock，macOS 用 Seatbelt，Windows 用 ACL 运行器。包装器本身在 [`capability/sandbox`](../../capability/sandbox/README.cn.md)。

`__init__.py`

对外给出 `KernelEnvironment`、`ProcessEnvironment`、`HostExecutionPolicy`，以及 `bind_room`、`current_room`、`using_room`。

## 已知限制与暂缓事项

- **房间在启动时定下来** — 进程已经 `apply()` 之后，再声明一条资源，不会把已经允许的路径或模式放宽。
