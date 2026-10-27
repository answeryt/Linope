# hypermedia

[English](README.md) | 中文

设计思想来自 HATEOAS，全称 hypermedia as the engine of application state，超媒体作为应用状态的引擎。

出处是 Roy Thomas Fielding 的博士论文 *Architectural Styles and the Design of Network-based Software Architectures*（加州大学欧文分校，2000；导师 Richard N. Taylor）。第 5 章定义 REST。第 5.1.5 节把统一接口收成四条约束，第四条就是这句话：用资源标识认出资源，用表示去操作资源，消息自己把语义带全，以及超媒体作为应用状态的引擎。第 5.3.3 节把后一条说具体：应用是一台引擎，它查看当前这一组表示里有哪些可选的状态转移，从中选一个，从而走到下一步。这和浏览器点链接一样。论文不假定使用它的一定是浏览器，自动化程序也可以当这个用户代理。论文章节页：<https://ics.uci.edu/~fielding/pubs/dissertation/rest_arch_style.htm>。全文 PDF：<https://ics.uci.edu/~fielding/pubs/dissertation/fielding_dissertation.pdf>。

同一论述的期刊版是 Fielding 与 Taylor 的 *Principled Design of the Modern Web Architecture*，*ACM Transactions on Internet Technology* 2(2)，2002 年 5 月，115–150 页，<https://doi.org/10.1145/514183.514185>。更早的会议稿是 ICSE 2000。命名和展开都在学位论文里，期刊版是同一模型的同行评审文本。

落到本目录：一页就是当前状态。事实写现在是什么样，链接写此刻能转移到哪。下一步只能从这些链接里选。页上没有的关系不能走。

## linope怎么用

调用方不用另记一份「现在允许做什么」。当前页就是这份名单。走完一步，服务返回下一页，新的链接跟着新状态一起换掉。状态因此不会和菜单脱节：菜单过期了，转移就被拒绝。

文件页有三种状态，转移写在 `representation_json.py`，由 `http_server.py` 执行：

| 现在 | 页上的转移 | 走完之后 |
|---|---|---|
| `resident` | `pin`、`swap`，以及读 `content` | `pin` 到 `pinned`，`swap` 到 `swapped` |
| `pinned` | 只留 `self` 和 `content` | 还能读正文，不能再钉住或换出 |
| `swapped` | 只留 `self` 和 `admit` | `admit` 回到 `resident` |

换出之后页上没有 `content`。再去读正文会得到 `409`，正文是 `relation not offered`。钉住之后页上没有 `swap`，再换出同样被拒绝。成功的 POST 把新状态写回账本，响应就是新的一页。

进程页在 `process_page.py`。`activity` 是当前状态，链接是此刻允许的下一步：

| 状态 | 多出来的链接 |
|---|---|
| `sleeping` | `stop`，句柄里带上这次启动的标记，启动标记变了旧的停就不能用 |
| `with` | `with`，指向正在一起工作的那个进程 |
| 有共享记忆的活进程 | `share`，指向还持有同一份记忆的进程 |
| 记录上有记忆范围 | `memory`，指向那份记忆 |

`closed` 不再提供 `stop`。`show` 打出的就是这一页：事实加上这些链接。

记忆页在 `memory_page.py`。每一行是一条链接，句柄里含有当前序号。记忆又写了一行，序号变了，旧页上的句柄就对不上。这是同一件事：状态往前走了，旧的转移不再有效。

模型要执行的命令菜单不在这里拼，在 [`kernel/communication`](../communication/README.cn.md)。它用这里的页和链接，把「现在能 `process start`、`load tool` 还是 `ask`」写进模型看到的那一页。本目录给出页、链接和本地 HTTP。启动服务的命令在 [`kernel/command/screen`](../command/screen/README.cn.md)。

## 每个脚本

`link.py`

一条链接：关系名、指向的资源、句柄。没有句柄的链接不能走。

`representation.py`

一页文档。`facts` 是事实，`links` 是链接。链接只点名别的资源，不把那些资源的正文夹进来。

`handle.py`

把若干部分收成一个十六进制句柄。pid 或地址本身不是跟随的权利。序号这类部分变了，句柄就变。

`uri.py`

把句柄写成只在本机用的 URI：资源是 `/resources/<句柄>`，正文和动作各有自己的路径。基址必须是 `http` 或 `https`。解析时只认回环主机 `127.0.0.1`、`localhost`、`::1`。URI 里看不到文件系统路径。

`representation_json.py`

把一页收成 JSON。`self` 和 `content` 是 GET，`pin`、`swap`、`admit` 是 POST。文件页按状态只给这些关系：

| 状态 | 关系 |
|---|---|
| `resident` | `self`、`content`、`pin`、`swap` |
| `pinned` | `self`、`content` |
| `swapped` | `self`、`admit` |

`file_link.py`

磁盘上的一个文件收成一页，只有一条 `self`。句柄为空就不能跟随。

`memory_page.py`

把记忆行收成一页。当前这一问的行带着原文，更早的行只留地址、种类和时间。这一页不授权进入那些地址。指针空间仍在 [`kernel/scheduler`](../scheduler/README.cn.md)。

`process_page.py`

`show` 打印的进程页。事实是这个进程现在在做什么。链接只列此刻允许的下一步。

`link_selector.py`

从一页里挑链接。选中的、并且带句柄的，放进 `followed`。没有句柄的留在 `left`。这里只返回链接，不读记忆，不开进程，不调工具。

`follow.py`

旧名字。新代码用 `link_selector`。模型回合在 [`kernel/scheduler`](../scheduler/README.cn.md)。

`http_server.py`

本机 HTTP。`serve_resources` 只听 `127.0.0.1`、`localhost`、`::1`。空的存储路径用 `file:.linope/resources.json`。`memory:` 存储不能单独起这个服务。同一份存储已经有服务在跑，就拒绝。页上没有的关系返回 `409`，正文是 `relation not offered`。

`__init__.py`

标明这个包是本地的 HATEOAS 表示。

## 已知限制与暂缓事项

- **HTTP 只在回环上提供文件存储** — 没有私网绑定，没有动态认证，也没有 CAS 或 ETag。
