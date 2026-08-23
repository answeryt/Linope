# sandbox/：进程沙箱能力家族

[English](README.md) | 中文

本家族将逐会话限制策略应用于同机进程执行。它覆盖与宿主共享文件系统和内核的子进程；Docker / Modal 等隔离环境不在这里注册。

| 目录 | 职责 | 状态 |
|---|---|---|
| [`sandbox/`](sandbox/README.md) | 三种模式、confine 合同、升权词汇 | 已改为 Open-Linux 插件 |
| [`sandbox-local/`](sandbox-local/README.md) | 本机平台限制后端 | 已改为 Open-Linux 插件 |
| [`sandbox-policy/`](sandbox-policy/README.md) | 逐会话策略解析 | 已改为 Open-Linux 插件 |
| [`sandbox-windows-acl/`](sandbox-windows-acl/README.md) | Windows ACL 后端 | 已改为 Open-Linux 插件 |

三种模式：`read-only` / `workspace-write` / `danger-full-access`。
