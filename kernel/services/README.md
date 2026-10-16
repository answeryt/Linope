# services

`kernel/services` 把已经启动的进程编成一个服务。服务不启动进程，也不在关闭时停下进程。客户端和服务端只是一次通信中的角色。

进程、线程、租约、句柄、通道和编制都不从这里出去。

## 对外

```python
from kernel.services import LaunchOptions, ServiceRequest, open_service

service = open_service("coder", LaunchOptions(store_locator="file:.linope/resources.json"))
ticket = service.submit(ServiceRequest(kind="message", body="你好", role="model"))
print(service.wait(ticket))
service.close()
```

| 方法 | 做什么 |
| --- | --- |
| `submit(request)` | 先把请求记在账上。这一轮预定成功后，才放进某个成员的信箱，返回 `Ticket` |
| `wait(ticket)` | 等待这条请求完成，再取回回复；已绑定服务不会设置固定截止时间 |
| `members()` | 每个成员的角色、能力名、进程号、pid、是否还在 |
| `close()` | 关掉这次打开的账本视图。不解除绑定，也不停止进程 |

`ServiceRequest` 由种类、正文、可选角色和操作组成。操作默认是 `load`。`ping` 这种内核操作把 `operation` 写成 `ping`。

命令行先创建空服务，再把已经启动的进程绑进去。同一服务可以分多次绑定不同进程。一个进程也可以属于多个服务。

```text
linope service create coder
linope process start model.openai_chat_model
linope service bind coder --process <进程号> --role model
linope service bind coder --process <另一个进程号> --role tool
linope service call coder --role model --kind message -- 修改登录模块
```

`service unbind` 和 `service delete` 只删除关系。`process stop` 才停止进程。

`process start`、`load`、`call`、`file` 仍会拉起能力进程。那是进程自己的生命周期，不是服务拥有这些进程。拉起使用 `launch_session`。`open_service` 只打开已经绑定的服务。

## 种类

一个种类是一个蓝图，只有 `plan(spec) -> ServicePlan`。`ServicePlan` 写出成员（角色、能力名、change 子句、份数）、要追加的共享名单，以及「请求种类 → 角色」。

| 种类 | 成员 |
| --- | --- |
| `capability` | 命令行点名的那一个能力，请求直接送达 |
| `model` | 一个 `model.*`，`message` 和 `context` 都交给它 |
| `mcp` | 默认 `tools.mcp_tool_manager`，`tool` 请求交给它 |

这些种类只用于 `launch_session` 拉起进程。服务成员的关系由 `service bind --role` 写下，不从能力名前缀推断。

`changes` 和末尾的份数给第一个模型成员。份数原样交给进程层的编制，这里不算该开谁、该关谁。

同一关系有多份进程时，挑选交给 `kernel/load_balancing`。读不到座位就送给第一个还活着的成员。挑选发生在这一轮已经预定之后。一个服务的公平用量，是它当前绑定的全部进程加在一起的账。

## 登记自己的种类

```python
from kernel.services import register_service_kind
from kernel.services.spec import MemberPlan, ServicePlan

class PlannerBlueprint:
    def plan(self, spec):
        return ServicePlan(
            members=(MemberPlan("planner", spec.members[0]),),
            route={"message": "planner"},
        )

register_service_kind("planner", PlannerBlueprint())
```

内置的 `capability`、`model`、`mcp` 去不掉。核心按名字取出蓝图，不导入某一种类的类。

## 这一层不做

- 不规划副本，不判断该关哪一份。
- 不写挑选规则，不另记忙闲表。
- 不做存活判断、不回收、不发信号。`Member.alive` 只是转述进程自己的状态。
- 不碰租约、句柄、通道选择、编制选择。
