# scheduler

[English](README.md) | 中文

一个调度器，负责模型回合、指针步骤、资源路由和线程准入。原始记忆字典在 [`kernel/resource/memory`](../resource/memory/README.cn.md)。选择哪一个对等进程在 [`kernel/load_balancing`](../load_balancing/README.cn.md)。

## 契约

| 入口 | 职责 |
|---|---|
| `turn` | 跑完一次 `load message`，直到模型回答。返回终端要显示的内容。 |
| `classify` | 把一个已检查的步骤分成 `MemoryRead`、`ActionCall` 或 `Answer`。解析不运行该步骤。 |
| `route` | 把正文交给持有所点名资源种类和身份的对等进程。调用方提供通道和打开器。 |
| `run_runtime` | 认领并准入请求到一个进程运行时，直到该进程要求停止。 |

`memory_space.py` 是指针空间。记忆授予上的 `space` 点名哪些类属于这个指针。类是 `system`、`message`、`task` 和 `artifact`。指针是进入一份记忆资源的权利。`message/0` 和 `message/0-10` 是该资源内部的选择器。

## 用地址共享一份记忆

共享的笔记本是同一个记忆实体。这次启动在 `shared` 里点名 `memory`，并且声明用的是同一个 scope 时，[`kernel/resource`](../resource/README.cn.md) 给出这一个实体。行和真名存在 [`kernel/resource/memory`](../resource/memory/README.cn.md)。本目录为每个还持有该实体的进程保留一张自己的地址表。

`access.py` 把这些表放在 `_MAPS` 里，先按进程 id 和资源 id，再按类。`remember` 让记忆模块追加一行。真名由实体自己的计数器给出，先是 `message/0`，再是 `message/1`。`_map_real` 把这个真名追加到每一个当前持有者的表上，条件是它的 `space` 包含这个类：

```python
for pid, grant in holders:
    if class_name not in visible_classes(grant):
        continue
    rows = _rows(pid, resource_id).setdefault(class_name, [])
    rows.append(real)
```

返回给写入者的地址，是它自己这张表上的下标，前面加上 scope，例如 `chat/message/0`。下标是写入者那张表的 `len(rows) - 1`。另一个已经有行的持有者，会在自己的下一个下标上拿到同一个真名。

读取 `message/0` 时，用的是本进程的表，再按真名取出那一行：

```python
rows = list(mapping.get(class_name) or [])
real = rows[index]
item = stored.get(real)
```

`memory_contents` 两个都返回。`address` 是本进程用的下标。`real` 是存下去的真名。

两个进程都可以说 `message/0`，指到的真名可以不同。后启动的进程地址表是空的。它持有这份记忆之前写下的行，不会补进这张表。它的 `message/0` 是它持有期间、并且它看得到该类时写下的下一行。

| 何时 | 真名 | 进程 A 的地址 | 进程 B 的地址 |
|---|---|---|---|
| A 写下第一行。B 还没启动。 | `message/0` | `message/0` | — |
| B 启动之后，A 写下下一行。 | `message/1` | `message/1` | `message/0` |

A 的 `message/1` 和 B 的 `message/0` 是同一行。某个类不在一个进程的 `space` 里，就不会追加到那个进程的表上。

带 scope 的读取，例如 `chat/message/0`，不用这张私有表。`real_slice` 按真名走 scope 为 `chat` 的那个实体。本进程有指向该 scope 的指针时，这次走访才被允许。

`access.py` 批准并执行这些访问。token 数达到一个正的上下文上限时，`capacity_full` 为真。token 数来自 [`kernel/calculate`](../calculate/README.cn.md)。地址表留在这次运行的 `_MAPS` 里。记忆字典保存那些行。

`turn` 给模型一页，页面来自 [`kernel/communication`](../communication/README.cn.md)。有记忆的进程，每一次 `load message` 都进入 `turn`；接收方有记忆的 `ask` 也是接收方自己的 `turn`。窗口能不能启动另一个进程，只决定页面是否提供 `process start`。回复在 communication 里检查，然后本目录决定它是否可以运行。一次读取仍是读取：它不启动进程，也不调用工具。只有通过的步骤才会执行。结果写回记忆，然后给出下一页。没有步骤上限。

`route` 拒绝缺失的通道，以及低于 1 的进程上限。它不取得租约。需要新进程时，由调用方提供的打开器启动。那个打开器是现有的协调器。

## 已知限制与暂缓事项

- **一个回合没有步骤上限** — `turn` 一直走，直到模型回答或调用失败。
- **地址表只在这次运行里** — 新的一次运行里 `_MAPS` 是空的。已经存下的行仍在记忆字典里。之后的写入只把这一次的真名追加进去，所以该进程的 `message/0` 是这一新行。已经存下的行用带 scope 的地址来读，例如 `chat/message/0`。
