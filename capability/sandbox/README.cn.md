# sandbox/ — 进程沙箱能力家族

[English](README.md) | 中文

本家族把按会话的文件写入策略应用到同一世界的进程执行。Docker 这类隔离环境不登记到 `confine`。

| 目录 | 职责 | 状态 |
|---|---|---|
| [`sandbox/`](sandbox/README.cn.md) | 三种模式、confine 契约、升级用词 | 已改为 Linope 插件 |
| [`sandbox-local/`](sandbox-local/README.cn.md) | 本地平台禁闭后端 | 已改为 Linope 插件 |
| [`sandbox-policy/`](sandbox-policy/README.cn.md) | 按会话解析策略 | 已改为 Linope 插件 |
| [`sandbox-windows-acl/`](sandbox-windows-acl/README.cn.md) | Windows ACL 后端 | 已改为 Linope 插件 |
| [`workspace/`](workspace/README.cn.md) | Docker 容器工作区（镜像、执行、绑定挂载） | 已改为 Linope 插件 |

模式：`read-only` / `workspace-write` / `danger-full-access`。

## 已知限制与暂缓事项

- **Docker 工作区是另一份契约** — [`workspace/`](workspace/README.cn.md) 不登记到 `confine`。
- **`tool` 和 `sandbox` 实体在打开时只是已加载标记** — 平台包装器稍后才运行，来自 [`kernel/environment`](../../kernel/environment/README.cn.md) 的 `confine`。
