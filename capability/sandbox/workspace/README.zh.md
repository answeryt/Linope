# workspace：Docker 隔离环境

[English](README.md) | 中文

容器工作区家族。它构建或复用按内容哈希打标的镜像，启动长期存活的 `sleep infinity` 容器，并可选地把宿主机目录 bind-mount 到 `/workspace`。它**不**注册到进程沙箱的 `confine` 合同。

| 插件 | 文件 | 职责 |
|---|---|---|
| `sandbox_workspace_dockerfile` | [`src/dockerfile_plugin.py`](src/dockerfile_plugin.py) | Dockerfile 文本、镜像 tag 哈希、临时 build context |
| `sandbox_workspace_backend` | [`src/backend_plugin.py`](src/backend_plugin.py) | 对已启动容器做 `exec_shell` / `read_file` / `write_file` |
| `sandbox_workspace` | [`src/workspace_plugin.py`](src/workspace_plugin.py) | 生命周期；Host 注入 `prepare_build_context` 与 `build_backend` |

运行时需要 Docker 和 `aiodocker`。叶测试注入假 client，不启动 daemon。

从 AgentScope 副本中去掉：MCP gateway、skills、FastAPI、uv、镜像内安装 `agentscope`。保留：镜像缓存、bind-mount 持久化、环境变量/标签、Linux 下拆除时对 bind-mount 做 `chown`。
