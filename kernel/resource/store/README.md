# store

资源这一段怎么存：实体、租约、句柄、待装载名单和表示。本地定位串是 `memory:` 和 `file:`。数据库连接和建表在 `kernel/database`，本目录不导入它。

打开完整账本（连同进程、信箱、通道）要用 `kernel.process.ledger`。那里把各段装进同一份内存账，再交给文件或数据库保存。本目录的 `open_store` 只认识已经登记的存储工厂，不自己去导入进程。

嵌进表示的篇幅、上下文 token、网络字节和通信篇幅都由 [`../account/`](../account/README.md) 计算。换出的链接不加。本段只保存页和已经记下的数字。

- [`__init__.py`](__init__.py)：导出定位串、存储登记和表示旁边的链接字段。
- [`page_link.py`](page_link.py)：表示旁边记下的关系、资源编号和句柄。这是账本里的字段，不是超媒体链接对象。链接菜单在 `kernel/hypermedia`。本目录不导入它。
- [`sections.py`](sections.py)：分段信封。第 2 版按段写出；读到旧的整包文件时，按各段声明的字段名拆开。
- [`resource_section.py`](resource_section.py)：资源这一段的读写。批准、归还、作废句柄、装上或卸下实体，以及保存和查找表示。`pages_for_handle` 按句柄取出它映进来的页。
- [`contracts.py`](contracts.py)：别人只依赖自己用到的那一块。租约、表示、存储身份和持久化各有一份小接口。
- [`state_codec.py`](state_codec.py)：把内存账本编码成 JSON，或从 JSON 填回去。
- [`persistent_store.py`](persistent_store.py)：文件库的公共外壳。真正的规则在内存账本里，外壳只负责一次操作的读入和写回。
- [`file_store.py`](file_store.py)：用一个 JSON 文件保存账本。写入先落到临时文件，再原子替换。只读的查看不会把整本账重写一遍。
- [`locator.py`](locator.py)：解析和规范化定位串。项目配置只保存相对项目根目录的账本路径；环境文件记在用户配置目录里，不写进可复制的项目文件。默认文件是 `file:.linope/resources.json`。环境变量 `LINOPE_RESOURCE_STORE` 和 `LINOPE_ENV_FILE` 可以临时盖过默认值。默认配置不保存带密码的数据库地址。
- [`registry.py`](registry.py)：按定位串的方案名打开存储。内置名字是 `file`、`memory`，`local` 视为 `file`。可以登记新的方案，不能覆盖内置名字。带 `://` 的数据库地址交给进程账本登记的数据库工厂。内置工厂由 `kernel.process.ledger` 在启动时装上。

存储定位串示例：

```text
file:.linope/resources.json
memory:
```

数据库地址的写法见 `kernel/database`。

可以用 `linope stores` 查看实现，用 `linope store check` 检查默认存储，用 `linope store init <定位串>` 初始化，用 `linope store migrate <定位串>` 迁移。
