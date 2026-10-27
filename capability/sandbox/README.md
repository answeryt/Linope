# sandbox/ — process-sandbox capability family

English | [中文](README.cn.md)

This family applies per-session file-write policy to same-world process execution. Isolated environments such as Docker do not register on `confine`.

| Directory | Role | Status |
|---|---|---|
| [`sandbox/`](sandbox/README.md) | Three modes, confine contract, escalation vocabulary | Converted to Linope plugins |
| [`sandbox-local/`](sandbox-local/README.md) | Local platform confinement backends | Converted to Linope plugins |
| [`sandbox-policy/`](sandbox-policy/README.md) | Per-session policy resolution | Converted to Linope plugins |
| [`sandbox-windows-acl/`](sandbox-windows-acl/README.md) | Windows ACL backend | Converted to Linope plugins |
| [`workspace/`](workspace/README.md) | Docker container workspace (image, exec, bind-mount) | Converted to Linope plugins |

Modes: `read-only` / `workspace-write` / `danger-full-access`.

## Known Limitations and Deferred Work

- **Docker workspace is a separate contract** — [`workspace/`](workspace/README.md) does not register on `confine`.
- **`tool` and `sandbox` entities are marked loaded at open** — the platform wrapper runs later, from [`kernel/environment`](../../kernel/environment/README.md) `confine`.
