# mcp_transport

English | [中文](README.cn.md)

One connection attempt per transport. Each module imports no sibling project module and can be loaded from its file path. The caller is [`mcp_runtime.py`](../mcp_runtime.py).

| File | Role |
|---|---|
| `stdio.py` | Spawn a server command and speak MCP over stdio. Uses `mcp.client.stdio`. |
| `sse.py` | Server-sent events. `MCPClientConnect` is the connection. |
| `streamable_http.py` | Streamable HTTP. `NonMCPEndpointError` is raised when the URL is not an MCP endpoint. |

`InvalidMCPConfiguration` is raised for a config the transport cannot use. Credentials in the config are the caller's. These modules do not read `mcp_servers.json`.

## Known Limitations and Deferred Work

- **The `mcp` package must be installed** — each transport imports `mcp` at load time.
