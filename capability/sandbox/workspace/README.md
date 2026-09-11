# workspace — Docker isolated environment

English | [中文](README.zh.md)

Container workspace family. It builds or reuses a content-hashed image, starts a long-lived `sleep infinity` container, and optionally bind-mounts a host directory to `/workspace`. It does **not** register on the process-sandbox `confine` contract.

| Plugin | File | Role |
|---|---|---|
| `sandbox_workspace_dockerfile` | [`src/dockerfile_plugin.py`](src/dockerfile_plugin.py) | Dockerfile text, image tag hash, temp build context |
| `sandbox_workspace_backend` | [`src/backend_plugin.py`](src/backend_plugin.py) | `exec_shell` / `read_file` / `write_file` over a started container |
| `sandbox_workspace` | [`src/workspace_plugin.py`](src/workspace_plugin.py) | Lifecycle; Host injects `prepare_build_context` and `build_backend` |

Runtime needs Docker and `aiodocker`. Leaf tests inject a fake client and do not start a daemon.

Dropped from the AgentScope copy: MCP gateway, skills, FastAPI, uv, and in-image `agentscope`. Kept: image cache, bind-mount persistence, env/labels, Linux bind-mount `chown` on teardown.
