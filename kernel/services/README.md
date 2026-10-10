# services

`kernel/services` 是一个 Agent 的聚合边界。一个服务由一个或多个平级能力进程组成，对外只露出四个方法。模型服务、Agent 服务、MCP 服务是登记进来的种类，不是三套接口。

进程、线程、租约、句柄、通道和编制都不从这里出去。

## 对外

```python
from kernel.services import LaunchOptions, ServiceRequest, ServiceSpec, open_service

service = open_service(
    ServiceSpec("agent", members=("model.openai_chat_model", "tools.bash")),
    LaunchOptions(store_locator="file:.linope/resources.json"),
)
ticket = service.submit(ServiceRequest(kind="prompt", body="你好"))
print(service.wait(ticket))
service.close()
```

| 方法 | 做什么 |
| --- | --- |
| `submit(request)` | 把一条可序列化请求交到某个成员的信箱，返回 `Ticket` |
| `wait(ticket)` | 取这条请求的回复 |
| `members()` | 每个成员的角色、能力名、进程号、pid、是否还在 |
| `close()` | 逐个成员停下，再关掉这份账本 |

`ServiceRequest` 由种类、正文、可选角色和操作组成。操作默认是 `load`。`ping` 这种内核操作把 `operation` 写成 `ping`。

命令行：

```text
linope services
linope service start model model.openai_chat_model model change - gpt-4o
linope service start agent model.openai_chat_model tools.bash tools.read
linope service start mcp
```

`start`、`load`、`call`、`ask`、`file` 也从这里进去。它们打开的是 `capability` 种类，一次一个能力，行为和以前一样。

## 种类

一个种类是一个蓝图，只有 `plan(spec) -> ServicePlan`。`ServicePlan` 写出成员（角色、能力名、change 子句、份数）、要追加的共享名单，以及「请求种类 → 角色」。

| 种类 | 成员 |
| --- | --- |
| `capability` | 命令行点名的那一个能力，请求直接送达 |
| `model` | 一个 `model.*`，`prompt` 和 `context` 都交给它 |
| `agent` | `model.*` 一个，`tools.*` 各自一个角色，`context.*` 至多一个 |
| `mcp` | 默认 `tools.mcp_tool_manager`，`tool` 请求交给它 |

`changes` 和末尾的份数给第一个模型成员。份数原样交给进程层的编制，这里不算该开谁、该关谁。

同一角色有多份进程时，挑选交给 `kernel/load_balancing`。读不到座位就送给第一个还活着的成员。

## 登记自己的种类

```python
from kernel.services import register_service_kind
from kernel.services.spec import MemberPlan, ServicePlan

class PlannerBlueprint:
    def plan(self, spec):
        return ServicePlan(
            members=(MemberPlan("planner", spec.members[0]),),
            route={"prompt": "planner"},
        )

register_service_kind("planner", PlannerBlueprint())
```

内置的 `capability`、`model`、`agent`、`mcp` 去不掉。核心按名字取出蓝图，不导入某一种类的类。

## 这一层不做

- 不规划副本，不判断该关哪一份。
- 不写挑选规则，不另记忙闲表。
- 不做存活判断、不回收、不发信号。`Member.alive` 只是转述进程自己的状态。
- 不碰租约、句柄、通道选择、编制选择。
