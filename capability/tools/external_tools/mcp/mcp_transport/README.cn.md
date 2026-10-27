# mcp_transport

[English](README.md) | 中文

每种传输一次连接尝试。每个模块不导入兄弟项目模块，并且可以从它的文件路径加载。调用方是 [`mcp_runtime.py`](../mcp_runtime.py)。

| 文件 | 职责 |
|---|---|
| `stdio.py` | 启动一条服务器命令，并通过 stdio 说 MCP。使用 `mcp.client.stdio`。 |
| `sse.py` | 服务器发送事件。`MCPClientConnect` 是连接。 |
| `streamable_http.py` | 可流式 HTTP。URL 不是 MCP 端点时抛出 `NonMCPEndpointError`。 |

传输无法使用的配置抛出 `InvalidMCPConfiguration`。配置里的凭据是调用方的。这些模块不读 `mcp_servers.json`。

## 已知限制与暂缓事项

- **必须安装 `mcp` 包** — 每种传输在加载时导入 `mcp`。
