# sandbox-local — 本地运行器选择

[English](README.md) | 中文

`confine(argv, policy)` 按平台包裹 argv：Linux 先 `bwrap` 再 Landlock；macOS 用 Seatbelt；Windows 用 ACL 的 `runner_plugin.py`。

没有可用后端时抛出 `SANDBOX_UNAVAILABLE`。`danger-full-access` 跳过 `confine`。

## 已知限制与暂缓事项

- **缺少一个后端就会使被禁闭的调用失败** — 没有从缺失的 `bwrap` 或 Landlock 帮手回退到未禁闭 argv。`danger-full-access` 是跳过 `confine` 的模式，在 [`sandbox-policy`](../sandbox-policy/README.cn.md) 解析。
