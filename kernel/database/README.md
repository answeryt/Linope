# database

`kernel/database` 只负责连上用户给出的数据库，并保存整本账的一行 JSON。

它不认识资源、进程、信箱或通道。那些段由 `kernel/process/ledger` 装进同一份内存账，再交给这里读写。资源目录不导入这里。

用户自己写连接地址，例如：

```text
sqlite:///.linope/ledger.db
postgresql+psycopg://user@host/database
mysql+pymysql://user@host/database
```

驱动要用户自己安装。这里不选择 PostgreSQL、MySQL 或其他库。没装驱动时停住，并提示安装这个地址对应的驱动。

- [`schema.py`](schema.py)：声明表 `linope_state`，里面是 `id` 和 `state_json`。初始化和迁移都调用 `create_all`。表已经在就跳过。
- [`store.py`](store.py)：按地址建立连接。一次操作在一个事务里读出 JSON、交给外面的内存账修改、再写回。SQLite 没有行锁时，靠事务和线程锁。
