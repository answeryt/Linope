# workspace — Docker isolated environment

English | [中文](README.cn.md)

Container workspace family. It builds or reuses a content-hashed image, starts a long-lived `sleep infinity` container, and optionally bind-mounts a host directory to `/workspace`. It does **not** register on the process-sandbox `confine` contract.

| Plugin | File | Role |
|---|---|---|
| `sandbox_workspace_dockerfile` | [`src/dockerfile_plugin.py`](src/dockerfile_plugin.py) | Dockerfile text, image tag hash, temp build context |
| `sandbox_workspace_backend` | [`src/backend_plugin.py`](src/backend_plugin.py) | `exec_shell` / `read_file` / `write_file` over a started container |
| `sandbox_workspace` | [`src/workspace_plugin.py`](src/workspace_plugin.py) | Lifecycle; Host injects `prepare_build_context` and `build_backend` |

Image cache, bind-mount persistence, env, labels, and a Linux bind-mount `chown` on teardown stay in the backend plugins.

## Known Limitations and Deferred Work

- **Not a `confine` backend** — this family does not wrap a same-world process argv. File-write modes stay in [`sandbox`](../sandbox/README.md).
- **Docker and `aiodocker` are required at runtime** — a missing daemon fails `exec_shell`, `read_file`, and `write_file`.
