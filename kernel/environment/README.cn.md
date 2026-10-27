# environment

[English](README.md) | 中文

一个能力进程能碰到的工作目录、能读写的路径、能读的密钥名字、能跑多久、外部命令要不要套沙箱，都记在这里。进程启动时按资源记录装好这一份，之后不再放宽。

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

这个进程能看见哪些地方：工作区、它自己的文件、临时目录。每个地方有一条：路径，以及能不能写。必须有一块名叫 `workspace`。`locate` 把一条路径收进允许的地方，收不进去就拒绝。

`file_io.py`

真正读文件、写文件的入口。先问 `filesystem.py` 这条路径能不能碰，再读或写。相对路径从工作区算起。写的时候父目录不存在会先建出来。

`identity.py`

这个进程是谁：pid、能力名、当前文件模式。密钥只记名字和文件位置。`resolve_secret` 在要用的那一刻才从文件里读出值。名字里带 `KEY`、`PASSWORD`、`SECRET`、`TOKEN` 的变量，在启动外部程序之前会被拿掉。

`compute.py`

外部程序能不能开、在哪个目录开、最长跑多久。工作目录必须在允许的地方里。模式要求套沙箱时，没有包装器就拒绝直接跑。线程池在 [`kernel/thread`](../thread/README.cn.md)，这里不负责开线程。

`mount.py`

路径规则。工作区根从 `--change workspace=`、`workspace_root` 或 `cwd` 来，没有就用后备路径。每个进程自己的临时目录在项目根下的 `.linope-tmp/<pid>`。主目录、`.git`、`.ssh`、`.aws`、`.env`、私钥和证书文件不让进这个视图。

`sandbox_vocab.py`

从 `capability/sandbox/sandbox/src` 读模式表和可写根规则。`check_mode` 拒绝不认识的模式。`confines` 回答这条命令要不要包起来。`writes` 回答这个模式允不允许写。

`session_mode.py`

会话当前用哪种沙箱模式。`effective_mode` 读最后一条 `sandbox/mode` 记录。`remember_mode` 往回合日志里追加一条。日志在 [`kernel/trace`](../trace/README.cn.md)。

`confine.py`

把工作区根和文件模式交给平台包装器。`read-only` 和 `workspace-write` 会改写要执行的命令行。`danger-full-access` 保持原来的命令行。Linux 用 bwrap 再 Landlock，macOS 用 Seatbelt，Windows 用 ACL 运行器。包装器本身在 [`capability/sandbox`](../../capability/sandbox/README.cn.md)。

`__init__.py`

对外给出 `KernelEnvironment`、`ProcessEnvironment`、`HostExecutionPolicy`，以及 `bind_room`、`current_room`、`using_room`。

## 已知限制与暂缓事项

- **房间在启动时定下来** — 进程已经 `apply()` 之后，再声明一条资源，不会把已经允许的路径或模式放宽。
