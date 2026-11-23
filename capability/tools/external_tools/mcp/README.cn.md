# mcp

[English](README.md) | 中文

本进程只面向本机的 [MCPHub](https://github.com/samanhappy/mcphub)。服务器由 MCPHub 连接。本进程只列出并调用它已经提供的工具。

| 文件 | 职责 |
|---|---|
| `mcp_tool_manager_plugin.py` | 一次工具调用的 `load`，以及进程声明 `capability_profile` |
| `hub.json` | 网关地址。默认是 `http://127.0.0.1:3000/mcp` |

`load` 只接受 `kind: tool`。名字为空或 `list` 时，返回 MCPHub 正在提供的工具。其他名字则调用那个工具。能力名仍是 `tools.mcp_tool_manager`。

第一批服务器是 `time` 和 `fetch`。它们登记在网关里，不在本目录。网关没开时，`load` 会说明 `MCPHub is not running`。
