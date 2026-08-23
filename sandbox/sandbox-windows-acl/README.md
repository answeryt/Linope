# sandbox-windows-acl — Windows write-restriction backend

English | [中文](README.zh.md)

Open-Linux same-world Windows backend. Mechanism is still a `WRITE_RESTRICTED` token plus workspace/temp SIDs; koffi is ctypes. Sibling plugins do not import each other.

`read-only` and `workspace-write` are enforced here. `danger-full-access` skips the runner.

```text
python runner_plugin.py --workspace <dir> --temp <dir> --mode <read-only|workspace-write> -- <argv...>
```
