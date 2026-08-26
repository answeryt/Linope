# sandbox/ — process-sandbox capability family

English | [中文](README.zh.md)

This family applies per-session file-write policy to same-world process execution. Isolated environments such as Docker or Modal do not register here.

| Directory | Role | Status |
|---|---|---|
| [`sandbox/`](sandbox/README.md) | Three modes, confine contract, escalation vocabulary | Converted to Linope plugins |
| [`sandbox-local/`](sandbox-local/README.md) | Local platform confinement backends | Converted to Linope plugins |
| [`sandbox-policy/`](sandbox-policy/README.md) | Per-session policy resolution | Converted to Linope plugins |
| [`sandbox-windows-acl/`](sandbox-windows-acl/README.md) | Windows ACL backend | Converted to Linope plugins |

Modes: `read-only` / `workspace-write` / `danger-full-access`.
