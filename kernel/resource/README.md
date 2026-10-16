# resource

`kernel/resource` 是资源的规章制度，也是资源自己的账。

资源是进程租来的设施。内存是其中一种。一份设施本身不等于内存用量。

当前种类在 `ResourceKind`，没有 `prompt`，也没有 `model`。模型名和 temperature 是进程的调用设置，不是租来的设施。

- `context`：上下文设施。压缩能力用自己的能力号当身份。这是租约，不是表示正文。用量是所调模型窗口里的 token。
- `memory`：内存。用量是已经嵌进表示的篇幅。
- `workspace`：工作区设施。身份是项目根。这一份租约分成挂载、地址空间和用量。文件在磁盘上，要等表示嵌进来才计入用量。
- `tool`：工具设施。工具能力用自己的能力号当身份。进程拉起来不计入内存用量。
- `network`：网络设施。记下允许访问的外网主机。用量是发出去和收回来的字节。
- `communication`：通信设施。通道和队列在资源侧的记录。送信在 `kernel/communication`。用量是送出正文的篇幅。

能力现在会来申请的是 `context`、`workspace`、`tool`。`memory`、`network`、`communication` 已经列在名单里。

是不是同一份，这样算：把种类和身份排好序，写成一段 JSON，再取 SHA-256，得到内部编号。点了名要共用时，身份相同就是同一份，几个进程一起用。没点名时，这段 JSON 里再放上进程号，于是每个进程一份。限额和调用参数不参与这个编号。编号算完，资源池再发句柄。进程只拿句柄，看不到内部编号。

用量在 [`account/`](account/README.md) 计算。能问整机、一个服务，或一个进程。嵌进表示的篇幅才计入内存、工作区和工具。换出之后地址还在，那是一条链接，用量不再加它。链接菜单仍在 `kernel/hypermedia`，由表示的状态决定现在能跟随哪些关系。

往来正文是消息，不是一种资源。角色是 `user_msg`、`tool_msg`、`model_msg`、`system_msg`。`model_msg` 是模型说出来的话。`system_msg` 是交给模型的规矩。组装说明的能力仍在 `capability/prompt`，它不占用一种资源。发给模型厂家时，接口再译回 `user`、`assistant`、`tool`、`system`。

本包负责：

- 资源种类、需求和批准后的句柄视图；
- 把声明编译成实体身份；
- 租约、引用计数、fencing token；
- 资源池的装载和卸载；
- 资源用量，算在 [`account/`](account/README.md)；
- 被留下的表示；
- 资源这一段怎么存进账本。

本包不负责进程的启动和停止、进程是否还活着、信箱和通道、服务成员关系、命令行，也不负责链接菜单。送信在 `kernel/communication`，进程在 `kernel/process`，链接菜单在 `kernel/hypermedia`。本包不导入 `kernel.communication`、`kernel.process`，也不导入 `kernel.hypermedia`。

进程登记、信箱、通道和布局仍和资源写在同一个 `resources.json` 里，但各自成段。那些段由进程和通信模块登记进来。旧的整包 JSON 仍能读入；新写入的文件是第 2 版，按段分开。

## 根目录

- [`__init__.py`](__init__.py)：把种类、句柄视图、租约和资源池按需导出。这里不在导入时立刻装上资源池，避免和进程声明互相引用。
- [`definition.py`](definition.py)：资源种类和一份批准。`ResourceDefinition` 是能力需要的一种资源。`ResourceGrant` 是批给某个进程的句柄、限额和调用参数；交给进程的视图里没有内部编号。`validate_grants` 检查批准是否盖住了声明。
- [`handle_view.py`](handle_view.py)：一个进程拿到的句柄视图。里面是进程号、能力号和全部句柄，可以序列化后放进启动包。这不是 `context` 设施。
- [`compile.py`](compile.py)：按开头的算法把这次声明编译成内部编号。`CompiledResource` 先记下种类、身份、限额和调用参数，句柄要等资源池再发。
- [`lease.py`](lease.py)：内存里的租约账。独占会把 fencing token 加一，已有占用时不能再独占；共享不推进这个号。引用计数从 0 变成 1 时记成待装载，回到 0 时可以卸载。`authorize` 核对句柄属于这个进程，并且代数还对得上。句柄被作废后，旧凭证不能再写。这里只按进程号归还租约，不登记进程、不判断进程是否还活着。
- [`pool.py`](pool.py)：资源池。`bind` 一次拿下全部租约，引用计数离开 0 时调用装载器，失败就收回已经拿到的东西。`release` 归还一个进程的租约，最后一个占用者离开后才卸载。`revoke` 作废一张句柄。`RecordingLoader` 只把实体记成「已装上」，还不会真的去请求模型或启动工具。进程行要由调用方先写好，池子不负责登记进程。
- [`account/`](account/README.md)：用量。整机、一个服务，或一个进程。

## 设施目录

每种设施一个目录，里面是这种租约的身份规则。能力插件不搬进来。

- [`context/`](context/kind.py)：压缩能力的租约。身份是能力号。
- [`tool/`](tool/kind.py)：工具能力的租约。身份是能力号。
- [`workspace/`](workspace/)：项目根上的一份租约，里面再分成挂载、地址空间和用量。见下一节。
- [`network/`](network/kind.py)：外网主机名单。身份是排好序的主机名。空名单不能当成已经断网。
- [`communication/`](communication/kind.py)：资源侧记下的通道名。

## `workspace/`

这一份租约只描述工作区。会一起改的规则放在这里。页的三种状态仍在 [`memory/`](memory/page.py)。用量在 [`account/`](account/README.md)。外部命令的包装器在 `capability/sandbox`，这里只交出项目根和档位。

文件、shell、终端来领这份租约。搜索只领 `network`。模型、待办、计划不领挂载。每个进程只看见自己的句柄。

- [`kind.py`](workspace/kind.py)：对外仍导出种类和身份。身份是项目根，实现在 `mount/kind.py`。
- [`mount/`](workspace/mount/)：挂载空间。身份是项目根，碰文件的平级进程可以共用这一份。`view.py` 写可读根、可写根、每个进程自己的临时目录，以及进不去的 `.git`、密钥文件和家目录。`mode.py` 是 `read-only` 和 `workspace-write`。`danger-full-access` 只表示外部命令不包装。
- [`address/`](workspace/address/pages.py)：地址空间。只列出这张 workspace 句柄映进来的文件页。没有这张句柄，这一块是空的。
- [`usage/`](workspace/usage/README.md)：说明用量不在这里算。算法在 [`account/`](account/README.md)。上限是句柄上的 `bytes`。

## `memory/`

这个目录记下跟随并留下的表示，以及它们占了多少内存用量。不是账本文件。

没被跟随的目标不记表示。跟随并留下之后，表示嵌进来，篇幅才计入 [`account/`](account/README.md)。换出的地址还在，已用不再加它。

- [`__init__.py`](memory/__init__.py)：导出表示和任务类型。
- [`task_kind.py`](memory/task_kind.py)：任务只有两类。不跟随是 `free`，只留链接。跟随并留下是 `occupy`。
- [`page.py`](memory/page.py)：一份长期表示。地址、篇幅和状态。状态是 `resident`（正文还在）、`pinned`（钉住）、`swapped`（只剩链接）。`embedded` 在前两种时为真。
- [`file_page.py`](memory/file_page.py)：为刚写好的文件做一份表示。地址用落盘路径，篇幅用字节数。需要长期留下时钉住，否则正文留在表示里。

## `message/`

往来正文。不是租来的设施。

- [`message.py`](message/message.py)：角色 `user_msg`、`tool_msg`、`model_msg`、`system_msg`。

## `store/`

这个目录只保存资源段：实体、租约、句柄、待装载名单和表示。本地定位串是 `memory:` 和 `file:`。数据库连接和建表在 `kernel/database`，本目录不导入它。

打开完整账本（连同进程、信箱、通道）要用 `kernel.process.ledger`。那里把各段装进同一份内存账，再交给文件或数据库保存。本目录的 `open_store` 只认识已经登记的存储工厂，不自己去导入进程。

- [`__init__.py`](store/__init__.py)：导出定位串、存储登记和表示旁边的链接字段。
- [`page_link.py`](store/page_link.py)：表示旁边记下的关系、资源编号和句柄。这是账本里的字段，不是超媒体链接对象。链接菜单在 `kernel/hypermedia`。
- [`sections.py`](store/sections.py)：分段信封。第 2 版按段写出；读到旧的整包文件时，按各段声明的字段名拆开。
- [`resource_section.py`](store/resource_section.py)：资源这一段的读写。批准、归还、作废句柄、装上或卸下实体，保存和查找表示，以及记下上下文、网络和通信的数字。怎么加这些数字在 [`account/`](account/README.md)。
- [`contracts.py`](store/contracts.py)：别人只依赖自己用到的那一块。租约、表示、存储身份和持久化各有一份小接口。
- [`state_codec.py`](store/state_codec.py)：把内存账本编码成 JSON，或从 JSON 填回去。
- [`persistent_store.py`](store/persistent_store.py)：文件库的公共外壳。真正的规则在内存账本里，外壳只负责一次操作的读入和写回。
- [`file_store.py`](store/file_store.py)：用一个 JSON 文件保存账本。写入先落到临时文件，再原子替换。只读的查看不会把整本账重写一遍。
- [`locator.py`](store/locator.py)：解析和规范化定位串，并记住项目默认存储和环境文件路径。默认文件是 `file:.linope/resources.json`。环境变量 `LINOPE_RESOURCE_STORE` 可以盖过它。默认配置不保存带密码的数据库地址。
- [`registry.py`](store/registry.py)：按定位串的方案名打开存储。内置名字是 `file`、`memory`，`local` 视为 `file`。可以登记新的方案，不能覆盖内置名字。带 `://` 的数据库地址交给进程账本登记的数据库工厂。内置工厂由 `kernel.process.ledger` 在启动时装上。

存储定位串示例：

```text
file:.linope/resources.json
memory:
```

数据库地址的写法见 `kernel/database`。

可以用 `linope stores` 查看实现，用 `linope store check` 检查默认存储，用 `linope store init <定位串>` 初始化，用 `linope store migrate <定位串>` 迁移。
