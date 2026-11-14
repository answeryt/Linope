# sandbox/ — 进程沙箱能力家族

[English](README.md) | 中文

本家族拥有运行时文件访问策略，并把同一份策略应用到文件工具和外部进程执行。默认 scope 是 `host`：启动 Linope 的 cwd 只是相对路径和命令启动目录提示，不是安全边界。Docker 这类隔离环境不登记到 `confine`。

| 目录 | 职责 | 状态 |
|---|---|---|
| [`sandbox/`](sandbox/README.cn.md) | 三种模式、confine 契约、升级用词 | 已改为 Linope 插件 |
| [`sandbox-local/`](sandbox-local/README.cn.md) | 本地平台禁闭后端 | 已改为 Linope 插件 |
| [`sandbox-policy/`](sandbox-policy/README.cn.md) | 按会话解析策略 | 已改为 Linope 插件 |
| [`sandbox-windows-acl/`](sandbox-windows-acl/README.cn.md) | Windows ACL 后端 | 已改为 Linope 插件 |
| [`workspace/`](workspace/README.cn.md) | Docker 容器工作区（镜像、执行、绑定挂载） | 已改为 Linope 插件 |

模式：`read-only` / `workspace-write` / `danger-full-access`。范围：`host` / `workspace`。

`capability/sandbox/access.py` 是文件工具使用的策略入口；`gate.py` 返回策略、根集合、临时目录和敏感路径规则。kernel 只传递策略，不再因为用户从主目录或盘符根启动而拒绝建立房间。

## 已知限制与暂缓事项

- **Docker 工作区是另一份契约** — [`workspace/`](workspace/README.cn.md) 不登记到 `confine`。
- **host scope 是高权限模式** — 它允许访问当前主机的驱动器根；应由上层交互明确展示。`danger-full-access` 仍表示跳过外部命令包装，不能把后端不可用静默降级为该模式。
- **`tool` 和 `sandbox` 实体在打开时只是已加载标记** — 平台包装器稍后才运行，来自 [`kernel/environment`](../../kernel/environment/README.cn.md) 的 `confine`。
