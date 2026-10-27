# workspace — Docker 隔离环境

[English](README.md) | 中文

容器工作区家族。它构建或复用按内容哈希的镜像，启动一个长期 `sleep infinity` 的容器，并可以选择把宿主目录绑定挂载到 `/workspace`。它不登记到进程沙箱的 `confine` 契约。

| 插件 | 文件 | 职责 |
|---|---|---|
| `sandbox_workspace_dockerfile` | [`src/dockerfile_plugin.py`](src/dockerfile_plugin.py) | Dockerfile 文本、镜像标签哈希、临时构建上下文 |
| `sandbox_workspace_backend` | [`src/backend_plugin.py`](src/backend_plugin.py) | 在已启动的容器上做 `exec_shell` / `read_file` / `write_file` |
| `sandbox_workspace` | [`src/workspace_plugin.py`](src/workspace_plugin.py) | 生存期；宿主注入 `prepare_build_context` 和 `build_backend` |

镜像缓存、绑定挂载的持久化、环境、标签，以及拆除时对 Linux 绑定挂载的 `chown`，留在后端插件里。

## 已知限制与暂缓事项

- **不是 `confine` 后端** — 本家族不包裹同一世界进程的 argv。文件写入模式留在 [`sandbox`](../sandbox/README.cn.md)。
- **运行时需要 Docker 和 `aiodocker`** — 缺少守护进程时，`exec_shell`、`read_file` 和 `write_file` 失败。
