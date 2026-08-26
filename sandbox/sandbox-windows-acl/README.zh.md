# sandbox-windows-acl：Windows 写入限制后端

[English](README.md) | 中文

Linope 同机沙箱的 Windows 后端。机制仍是 `WRITE_RESTRICTED` 令牌 + 工作区/临时 SID，koffi 换成 ctypes。兄弟插件不互导，由 Host 或 `runner_plugin` 按路径装配。

三种模式里这里强制执行的是 `read-only` 和 `workspace-write`（`danger-full-access` 不进 runner）。

```text
python runner_plugin.py --workspace <dir> --temp <dir> --mode <read-only|workspace-write> -- <argv...>
```
