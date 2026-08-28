# sandbox-policy：逐会话沙箱策略

[English](README.md) | 中文

策略解析的唯一归属。部署默认模式是 `read-only`。每次调用：显式批准 > 会话最后一条 `sandbox/mode` > 默认。

| 插件 | 文件 | 职责 |
|---|---|---|
| `sandbox_session_mode` | [`src/session_mode_plugin.py`](src/session_mode_plugin.py) | 三种模式、fold、写入事件 |
| `sandbox_policy` | [`src/sandbox_policy_plugin.py`](src/sandbox_policy_plugin.py) | `resolve()`；Host 注入 `canonical_path` 与 `effective_mode` |

`danger-full-access` 会解析出来，但不进入 `confine`。
