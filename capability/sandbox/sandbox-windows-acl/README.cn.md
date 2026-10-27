# sandbox-windows-acl — Windows 写入限制后端

[English](README.md) | 中文

Linope 同一世界的 Windows 后端。机制仍是 `WRITE_RESTRICTED` 令牌加上工作区/临时 SID；koffi 是 ctypes。兄弟插件互不导入。

`read-only` 和 `workspace-write` 在这里执行。`danger-full-access` 跳过运行器。

```text
python runner_plugin.py --workspace <dir> --temp <dir> --mode <read-only|workspace-write> -- <argv...>
```

## 已知限制与暂缓事项

- **只有 Windows ACL** — Linux 的 `bwrap` / Landlock 和 macOS 的 Seatbelt 在 [`sandbox-local`](../sandbox-local/README.cn.md)。这个运行器是那些选择器调用的 Windows 路径。
