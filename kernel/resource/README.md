# resource

`kernel/resource` 是资源的规章制度，也是资源自己的账。

一份资源从声明到能用，经过这几步：能力说自己要哪一种，这次启动写明具体是谁，系统算出是不是同一份实体，资源池批准占用并发一张句柄。进程只拿句柄，看不到实体的内部编号。调用参数（比如 temperature）留在进程里，不拿来区分是不是同一份模型。

本包负责：

- 资源种类、需求和批准后的句柄视图；
- 把声明编译成实体身份；
- 租约、引用计数、fencing token；
- 资源池的装载和卸载；
- 长期页和上下文窗口；
- 资源这一段怎么存进账本。

本包不负责进程的启动和停止、进程是否还活着、信箱和通道、Agent 委派、命令行。这些在 `kernel/process`。本包不导入 `kernel.process`。

进程登记、信箱、通道和布局仍和资源写在同一个 `resources.json` 里，但各自成段。那些段由进程和通信模块登记进来。旧的整包 JSON 仍能读入；新写入的文件是第 2 版，按段分开。

## 根目录

- [`__init__.py`](__init__.py)：把种类、上下文、租约和资源池按需导出。这里不在导入时立刻装上资源池，避免和进程声明互相引用。
- [`definition.py`](definition.py)：资源种类和一份批准。`ResourceKind` 列出 context、model、memory、workspace、tool、network、identity、persistence、lifecycle、communication、prompt。`ResourceDefinition` 是能力需要的一种资源。`ResourceGrant` 是批给某个进程的句柄、限额和调用参数；交给进程的视图里没有内部编号。`validate_grants` 检查批准是否盖住了声明。
- [`context.py`](context.py)：一个进程拿到的资源视图。里面是进程号、能力号和全部句柄，可以序列化后放进启动包。
- [`compile.py`](compile.py)：把这次声明编译成实体钥匙。身份参数（提供商、模型名）相同就是同一份；没被点名共享时，钥匙里带上进程号，于是每个进程一份。`CompiledResource` 先记下种类、身份、限额和调用参数，句柄要等资源池再发。
- [`lease.py`](lease.py)：内存里的租约账。独占会把 fencing token 加一，已有占用时不能再独占；共享不推进这个号。引用计数从 0 变成 1 时记成待装载，回到 0 时可以卸载。句柄被作废后，旧凭证不能再写。这里只按进程号归还租约，不登记进程、不判断进程是否还活着。
- [`pool.py`](pool.py)：资源池。`bind` 一次拿下全部租约，引用计数离开 0 时调用装载器，失败就收回已经拿到的东西。`release` 归还一个进程的租约，最后一个占用者离开后才卸载。`revoke` 作废一张句柄。`RecordingLoader` 只把实体记成「已装上」，还不会真的去请求模型或启动工具。进程行要由调用方先写好，池子不负责登记进程。

## `memory/`

这个目录是上下文窗口里的长期页，不是账本文件。

没被跟随的目标不建页，不占窗口。跟随之后才写成一页。还在窗口里的页和钉住的页计入已用；换出的页地址还在，已用不再加它。几个模型读同一组页时，各用各的窗口，窗口不相加，页也不按模型个数去乘。

- [`__init__.py`](memory/__init__.py)：导出页、页表、用量和任务类型。
- [`task_kind.py`](memory/task_kind.py)：任务只有两类。不跟随是 `free`，不占内存。跟随并建页是 `occupy`。
- [`page.py`](memory/page.py)：一页长期记忆。地址、篇幅和状态。状态是 `resident`（还在窗口里）、`pinned`（钉住，不能换出）、`swapped`（已换出）。
- [`page_table.py`](memory/page_table.py)：一份上下文的页表。地址不能重复。`place` 拒绝已有地址；`put` 遇到同一地址就换掉那一页的篇幅和状态。
- [`ledger.py`](memory/ledger.py)：一个模型窗口里的已用篇幅。换出的页不计入。`fits` 表示已用没有超过窗口。
- [`readers.py`](memory/readers.py)：多个模型各自量同一组页。`tightest_window` 取其中最小的窗口。
- [`file_page.py`](memory/file_page.py)：为刚写好的文件做一页。地址用落盘路径，篇幅用字节数。需要长期留下时钉住，否则留在窗口里。

## `store/`

这个目录只保存资源段：实体、租约、句柄、待装载名单和长期页。文件库和数据库每次操作都包在同一把锁或同一次事务里。定位串仍是 `memory:`、`file:`、`postgresql:`、`mysql:`。

打开完整账本（连同进程、信箱、通道）要用 `kernel.process.ledger`。那里把各段装进同一份文件。本目录的 `open_store` 只认识已经登记的存储工厂，不自己去导入进程。

- [`__init__.py`](store/__init__.py)：导出定位串、存储登记和页上的链接字段。
- [`page_link.py`](store/page_link.py)：页旁边记下的关系、资源编号和句柄。这是账本里的字段，不是超媒体链接对象。
- [`sections.py`](store/sections.py)：分段信封。第 2 版按段写出；读到旧的整包文件时，按各段声明的字段名拆开。
- [`resource_section.py`](store/resource_section.py)：资源这一段的读写。批准、归还、作废句柄、装上或卸下实体，以及保存和查找长期页。
- [`contracts.py`](store/contracts.py)：别人只依赖自己用到的那一块。租约、长期页、存储身份和持久化各有一份小接口。
- [`state_codec.py`](store/state_codec.py)：把内存账本编码成 JSON，或从 JSON 填回去。
- [`persistent_store.py`](store/persistent_store.py)：文件库和数据库的公共外壳。真正的规则在内存账本里，外壳只负责一次操作的读入和写回。
- [`file_store.py`](store/file_store.py)：用一个 JSON 文件保存账本。写入先落到临时文件，再原子替换。只读的查看不会把整本账重写一遍。
- [`database_store.py`](store/database_store.py)：PostgreSQL 和 MySQL 的公共实现。状态存在一行 JSON 里，读写包在事务中。
- [`postgres_store.py`](store/postgres_store.py)：PostgreSQL 连接。只有使用 PostgreSQL 定位串时才需要对应驱动。
- [`mysql_store.py`](store/mysql_store.py)：MySQL 连接。优先用 PyMySQL，否则用 MySQL Connector。
- [`locator.py`](store/locator.py)：解析和规范化定位串，并记住项目默认存储和环境文件路径。默认文件是 `file:.linope/resources.json`。环境变量 `LINOPE_RESOURCE_STORE` 可以盖过它。默认配置不保存数据库密码。
- [`registry.py`](store/registry.py)：按定位串的方案名打开存储。内置名字是 `file`、`memory`、`postgresql`、`mysql`，`local` 视为 `file`，`postgres` 视为 `postgresql`。可以登记新的方案，不能覆盖内置名字。内置工厂由 `kernel.process.ledger` 在启动时装上。

### `store/migrations/`

- [`__init__.py`](store/migrations/__init__.py)：导出当前 schema 版本。
- [`common.py`](store/migrations/common.py)：持久化账本共用的版本号。现在是 2，表示分段文档。
- [`postgres.py`](store/migrations/postgres.py)：让 PostgreSQL 账本做幂等的建表。
- [`mysql.py`](store/migrations/mysql.py)：让 MySQL 账本做幂等的建表。

存储定位串示例：

```text
file:.linope/resources.json
memory:
postgresql://user:password@host/database
mysql://user:password@host/database
```

可以用 `linope stores` 查看实现，用 `linope store check` 检查默认存储，用 `linope store init <定位串>` 初始化，用 `linope store migrate <定位串>` 迁移。
