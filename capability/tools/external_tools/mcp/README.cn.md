# mcp

[English](README.md) | 中文

本进程的 MCP 客户端插件。传输在 [`mcp_transport/`](mcp_transport/README.cn.md)。插件不按包路径导入兄弟项目模块。`mcp_runtime.py` 按文件加载它们。

| 文件 | `PLUGIN_NAME` | 职责 |
|---|---|---|
| `mcp_config_plugin.py` | `mcp_configuration` | 服务器配置 |
| `mcp_auth_security_plugin.py` | `mcp_auth_security` | 认证和服务器配置检查 |
| `mcp_host_manager_plugin.py` | `mcp_host_manager` | 服务器进程及其状态 |
| `mcp_client.py` | | `MCPClient` 会话 |
| `mcp_client_lifecycle.py` | | 连接和断开状态 |
| `mcp_protocol_plugin.py` | `mcp_protocol_resources` | 资源、提示词和分页 |
| `mcp_content_plugin.py` | `mcp_content_results` | 工具结果内容 |
| `mcp_tool_manager_plugin.py` | `mcp_tool_manager` | 带前缀的工具名，以及一次工具调用的 `load` |
| `mcp_interaction_plugin.py` | `mcp_bidirectional_interaction` | 服务器发起的交互 |
| `mcp_resilience_plugin.py` | `mcp_resilience` | 断路器和失败分类 |
| `mcp_runtime.py` | | `call(manager, name, arguments)` 和传输选择 |
| `mcp_servers.json` | | 配置插件读取的服务器列表 |

`mcp_tool_manager.load` 接受一次工具调用，并通过运行时分发。每个插件上的 `capability_profile` 是进程声明。

## 模型体验

### 工具 schema

#### 模型看到什么

已连接服务器公布的工具，名字由 `prefixed_tool_name` 加前缀。输入 schema 由 `normalize_input_schema` 规范化。服务器说明不抄进 [`system_02_tools.md`](../../../prompt/prompt_card/system/system_02_tools.md)。

#### Token 影响

每个可见的 MCP 工具一份 schema，加上 `call` 返回的文本。

#### KV Cache 影响

稳定的服务器工具列表保持稳定的 schema 前缀。连接、断开或重命名一个工具会改变该前缀。

## 已知限制与暂缓事项

- **一次工具调用需要已连接的服务器** — 点名的服务器没起来时，`mcp_runtime.call` 失败。除非该服务器的配置点名一条 stdio 传输可以启动的命令，本目录不会自己启动服务器二进制。
