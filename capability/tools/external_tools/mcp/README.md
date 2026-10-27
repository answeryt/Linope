# mcp

English | [中文](README.cn.md)

MCP client plugins for this process. Transports live in [`mcp_transport/`](mcp_transport/README.md). Plugins do not import sibling project modules by package path. `mcp_runtime.py` loads them by file.

| File | `PLUGIN_NAME` | Role |
|---|---|---|
| `mcp_config_plugin.py` | `mcp_configuration` | Server configuration |
| `mcp_auth_security_plugin.py` | `mcp_auth_security` | Authentication and server-config checks |
| `mcp_host_manager_plugin.py` | `mcp_host_manager` | Server processes and their state |
| `mcp_client.py` | | `MCPClient` session |
| `mcp_client_lifecycle.py` | | Connect and disconnect states |
| `mcp_protocol_plugin.py` | `mcp_protocol_resources` | Resources, prompts, and pagination |
| `mcp_content_plugin.py` | `mcp_content_results` | Tool-result content |
| `mcp_tool_manager_plugin.py` | `mcp_tool_manager` | Prefixed tool names and `load` for a tool call |
| `mcp_interaction_plugin.py` | `mcp_bidirectional_interaction` | Server-initiated interaction |
| `mcp_resilience_plugin.py` | `mcp_resilience` | Circuit breaker and failure class |
| `mcp_runtime.py` | | `call(manager, name, arguments)` and transport selection |
| `mcp_servers.json` | | Server list the config plugin reads |

`mcp_tool_manager.load` accepts a tool call and dispatches through the runtime. `capability_profile` on each plugin is the process declaration.

## Model Experience

### Tool schema

#### What the model sees

Tools advertised by a connected server, with names prefixed by `prefixed_tool_name`. The input schema is normalized by `normalize_input_schema`. Server instructions are not copied into [`system_02_tools.md`](../../../prompt/prompt_card/system/system_02_tools.md).

#### Token effect

One schema per visible MCP tool, plus the text `call` returns.

#### KV Cache effect

A stable server tool list keeps a stable schema prefix. Connecting, disconnecting, or renaming a tool changes that prefix.

## Known Limitations and Deferred Work

- **A tool call needs a connected server** — `mcp_runtime.call` fails when the named server is not up. This directory does not start a server binary by itself unless that server's config names a command the stdio transport can spawn.
