# sandbox/ — process-sandbox capability family

English | [中文](README.cn.md)

This family owns runtime file-access policy and applies the same policy to file tools and external process execution. The default scope is `host`; the launch cwd is a relative-path and command-directory hint, not a security boundary. Isolated environments such as Docker do not register on `confine`.

| Directory | Role | Status |
|---|---|---|
| [`sandbox/`](sandbox/README.md) | Three modes, confine contract, escalation vocabulary | Converted to Linope plugins |
| [`sandbox-local/`](sandbox-local/README.md) | Local platform confinement backends | Converted to Linope plugins |
| [`sandbox-policy/`](sandbox-policy/README.md) | Per-session policy resolution | Converted to Linope plugins |
| [`sandbox-windows-acl/`](sandbox-windows-acl/README.md) | Windows ACL backend | Converted to Linope plugins |
| [`workspace/`](workspace/README.md) | Docker container workspace (image, exec, bind-mount) | Converted to Linope plugins |

Modes: `read-only` / `workspace-write` / `danger-full-access`. Scopes: `host` / `workspace`.

`access.py` is the policy-backed file API used by file tools. `gate.py` resolves roots, writable roots, temporary paths, and sensitive-path rules. The kernel carries the resolved policy without rejecting a home directory or drive root.

## Known Limitations and Deferred Work

- **Host scope is high privilege** — it can cover the host's drive roots and must be shown as such by the caller. `danger-full-access` still means skipping external-command wrapping; an unavailable backend must not silently fall back to it.
- **Docker workspace is a separate contract** — [`workspace/`](workspace/README.md) does not register on `confine`.
- **`tool` and `sandbox` entities are marked loaded at open** — the platform wrapper runs later, from [`kernel/environment`](../../kernel/environment/README.md) `confine`.
