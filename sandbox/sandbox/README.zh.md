# sandbox：进程沙箱词汇

[English](README.md) | 中文

Open-Linux 同机进程沙箱的词汇插件。只定义三种文件写入模式和 `confine` 合同，不实现平台 runner，也不依赖 Cordis。

| 插件 | 文件 | 职责 |
|---|---|---|
| `sandbox_provider` | [`src/sandbox_plugin.py`](src/sandbox_plugin.py) | 模式词汇、`SANDBOX_UNAVAILABLE`、confine 结果形状 |
| `sandbox_roots` | [`src/roots_plugin.py`](src/roots_plugin.py) | `canonical_path` / `writable_roots` |
| `sandbox_escalation` | [`src/escalation_plugin.py`](src/escalation_plugin.py) | 升权梯子与失败关闭批准 |

三种模式：

- `read-only`：几乎不能写（只留 `/dev/null` 一类出口）
- `workspace-write`：只能写工作区根目录和平台临时目录
- `danger-full-access`：不套沙箱，调用方直接 spawn 原 argv

约定：Host 注入 `confine`。受限模式必须返回包装后的 argv，或抛 `SANDBOX_UNAVAILABLE`；禁止把原 argv 偷偷放行。`danger-full-access` 不进入 `confine`。

策略按每次调用传入。兄弟插件不得互相 import，常量在各文件内复写。
