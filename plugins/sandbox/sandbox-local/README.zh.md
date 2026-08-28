# sandbox-local：本机 runner 选择

[English](README.md) | 中文

`confine(argv, policy)` 按平台包装 argv：Linux 优先 bwrap，否则 Landlock；macOS Seatbelt；Windows 走 `sandbox-windows-acl` 的 `runner_plugin.py`。

没有可用后端时抛 `SANDBOX_UNAVAILABLE`。`danger-full-access` 不进入 `confine`。
