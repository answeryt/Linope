# sandbox — 进程沙箱用词

[English](README.md) | 中文

Linope 同一世界的进程沙箱用词插件。它们拥有三种文件效果模式和 `confine` 契约。它们不实现平台运行器，也不依赖 Cordis。

| 插件 | 文件 | 职责 |
|---|---|---|
| `sandbox_provider` | [`src/sandbox_plugin.py`](src/sandbox_plugin.py) | 模式用词、`SANDBOX_UNAVAILABLE`、被禁闭的 argv 形状 |
| `sandbox_roots` | [`src/roots_plugin.py`](src/roots_plugin.py) | `canonical_path` / `writable_roots` |
| `sandbox_escalation` | [`src/escalation_plugin.py`](src/escalation_plugin.py) | 升级阶梯和失败即关闭的批准 |

模式：

- `read-only` — 除 `/dev/null` 这类必需的汇之外不写
- `workspace-write` — 工作区根加上平台临时区
- `danger-full-access` — 跳过 confine；按原来的 argv 启动

宿主注入 `confine`。被禁闭的模式必须返回包好的 argv，或抛出 `SANDBOX_UNAVAILABLE`。静默地原样放行是禁止的。兄弟插件互不导入；模式名在本地各写一份。

## 已知限制与暂缓事项

- **模式字符串在每个兄弟里各抄一份** — 本包不导入 `sandbox-policy` 或 `sandbox-local` 来共享这三个名字。
