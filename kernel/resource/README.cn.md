# resource/ — 种类、租约与句柄

[English](README.md) | 中文

`kernel/resource` 是进程与资源的关系：

`需求 → 声明 → 实体 → 租约 → 句柄`

进程看到句柄、种类和调用参数。实体 id 留在本进程内的授予上。句柄没有配额。目录能否读写是 [`kernel/environment`](../environment/README.cn.md) 里的房间。每个进程的账户是 [`kernel/process/resource_record.py`](../process/resource_record.py)。磁盘上，[`kernel/process/ledger.py`](../process/ledger.py) 保存该账户的一份副本。

## memory/

[`memory/`](memory/README.cn.md) 是一个记忆实体持有的那本字典。

`state.py` 把它打开为 `{"address_space": {"scope": ...}}`。行放在 `items` 下。一行的键就是它的真名：`message/0`、`task/0`、`artifact/0`，或 `system`。`next` 是 `message`、`task`、`artifact` 各自的下一个编号。`seq` 是整本字典的一个计数器。`store.py` 追加一行，并把有名字的提示文件拼进 system 行。`token_meter.py` 把已经存下的文本的 token 数加总。这个数在询问时算出来。

持有该实体的每个进程共用这些真名。一个进程自己的 `message/0` 可以指向另一个真名。那张地址表，以及谁可以读或写，在 [`kernel/scheduler`](../scheduler/README.cn.md)。

## 脚本

| 脚本 | 作用 |
|---|---|
| `__init__.py` | 本包的公开名字，第一次使用时才导入 |
| `resource_contract.py` | 种类登记表 |
| `definition.py` | 一个能力需要什么，以及一个进程拿到的授予 |
| `compile.py` | 把一份声明变成实体键 |
| `handle_view.py` | 一个进程的授予的可序列化视图 |
| `lease.py` | 内存里的租约表、引用计数和句柄检查 |
| `pool.py` | 绑定一个进程：铸造句柄、取得租约、加载并卸载实体 |

`__init__.py` 通过 `__getattr__` 导出定义、授予、上下文、租约和池。第一次用到某个名字时，才导入定义它的模块。本包若在导入时就载入池，会和进程声明互相引用，因为 `compile.py` 指向那份声明。

`resource_contract.py` 是唯一的登记表。`register` 增加一种：名字、必需的身份键、是否可以共享，以及可选的打开和关闭函数。`require` 拒绝不在表上的名字。`validate_claim` 拒绝缺少必需身份键的声明，并在 `allow_shared` 为假时拒绝 `shared=True`。导入时装上这些内置种类：

| 种类 | 身份 | 打开 |
|---|---|---|
| `memory` | `scope` | `memory.state.open_state`，实体就是 scope 所命名的地址范围 |
| `tool` | `id` | 无 |
| `sandbox` | `root` | 无 |
| `network` | `channel` | 无 |

`open_entity` 调用该种类的打开函数。没有打开函数、也没有加载器时，它记下 `loaded: true`、种类和身份。`close_entity` 调用该种类的关闭函数；传入了加载器时，改为调用加载器的 `unload`。

`definition.py` 放两种形状。`ResourceDefinition` 是一个能力需要的一种资源：种类、是否必需，以及可选的实体 id。`ResourceKind` 点名四种内置种类。`ResourceShareMode` 是 `exclusive` 或 `shared`。`ResourceGrant` 是一个进程拿到的一份授予：实体 id、种类、句柄、调用参数和共享方式。`process_payload` 保留句柄、种类和调用参数。`validate_grants` 拒绝重复的句柄。需求点名了实体 id 时，按该 id 配对，并且种类必须相同。否则按种类配对：每个必需种类都要在，能力没有声明的种类被拒绝。

`compile.py` 运行 `compile_declaration`。它把每条声明和能力的需求配对，拒绝重复的种类、缺少的必需种类，以及能力没有声明的种类。`entity_key` 用 SHA-256 哈希种类和身份。调用参数留在 `CompiledResource` 上，不进入键。出现在这次启动的 `shared` 列表里的种类，对那个身份使用一个键，`share_mode` 为 `shared`。其余声明的键还包含 pid，`share_mode` 为 `exclusive`。因此两个身份相同的独占声明得到两个实体键。只是被允许共享的种类，在这次启动点名它之前仍是独占。句柄稍后才铸造。

`handle_view.py` 是 `ResourceContext`：pid、能力 id、授予、时间和设置。`create` 先运行 `validate_grants`，再做成这个视图。`payload` 通过每份授予的 `process_payload` 序列化。`from_payload` 重建上下文时，每份授予的实体 id 都是空的。`get` 按实体 id 找一份授予。`get_handle` 按句柄找。

`lease.py` 是 `ResourceLeaseManager`，池背后的内存表。`acquire` 在第一次使用时创建 `ResourceEntity`，追加一条 `ResourceLease`，并把句柄记为该 pid 的活动句柄。实体的 `refcount` 加一。第一个占用者被标成待加载，供池去加载。独占取得会推进 fencing token，并且已有任何租约时拒绝。共享取得保持当前 token，并且已有独占租约时拒绝。`authorize` 拒绝缺失的句柄、不是活动状态的句柄、属于别的 pid 的句柄，以及 fencing token 旧于实体当前 token 的句柄。`release` 放下该 pid 的每一条活动租约，把它的句柄标成已释放，并返回那些引用计数降到零且当时已加载的实体。`revoke` 把一个句柄标成已撤销，并释放该 pid 在其实体上的租约。`memory_named` 拒绝按 scope 查找。按名字读记忆由 [`kernel/scheduler`](../scheduler/README.cn.md) 批准。

`pool.py` 是 `ResourcePool`。`bind` 收下编译好的声明，用 `secrets.token_hex(16)` 为每条声明铸造一个句柄，然后请租约表取得它们。接着加载每一个引用计数刚离开零的实体。加载调用 `open_entity`。默认加载器是 `RecordingLoader`，它记下 `loaded: true` 和身份。`release` 询问租约表哪些实体的引用计数到了零，再通过 `close_entity` 关闭它们。`authorize` 和 `revoke` 在池的锁里走租约表。监听器会收到 `resource_load_succeeded`、`resource_load_failed`、`resource_unloaded` 和 `handle_revoked`。

## 已知限制与暂缓事项

- **`tool`、`sandbox` 和 `network` 打开时只是一个已加载标记** — 这些种类没有登记打开函数，因此 `open_entity` 记下 `loaded: true` 和身份。真正的调用发生在稍后的 `load`。
