# sandbox-policy — 按会话的沙箱策略

[English](README.md) | 中文

策略解析的唯一所有者。部署默认是 `read-only`。每次调用：已批准的模式 > 最近的 `sandbox/mode` 事件 > 默认。

| 插件 | 文件 | 职责 |
|---|---|---|
| `sandbox_session_mode` | [`src/session_mode_plugin.py`](src/session_mode_plugin.py) | 三种模式、折叠、写入路径 |
| `sandbox_policy` | [`src/sandbox_policy_plugin.py`](src/sandbox_policy_plugin.py) | `resolve()`；宿主注入 `canonical_path` 和 `effective_mode` |

`danger-full-access` 在这里解析，并跳过 `confine`。

## 已知限制与暂缓事项

- **部署默认是 `read-only`** — 没有已批准模式、也没有 `sandbox/mode` 事件的会话保持只读。
