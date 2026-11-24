# mcp

English | [中文](README.cn.md)

One tool process in front of a local [MCPHub](https://github.com/samanhappy/mcphub). MCPHub connects the servers. This process only lists and calls the tools that hub is serving.

| File | Role |
|---|---|
| `mcp_tool_manager_plugin.py` | `load` for one tool call, and `capability_profile` for the process |
| `hub.json` | The hub address. The default is `http://127.0.0.1:3000/mcp` |

`load` accepts `kind: tool`. An empty name or `list` returns the tools MCPHub is serving. Any other name calls that tool. The capability name stays `tools.mcp_tool_manager`.

`discover_tools()` returns that same list. The agent process calls it once after `ready`, before the first turn. The loop does not send `list`.

The first servers are `time` and `fetch`. They are registered in the hub, not in this directory. If the hub is not running, `load` says `MCPHub is not running`.
