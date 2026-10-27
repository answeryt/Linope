# system

English | [中文](README.cn.md)

The system prompt text for the linope agent.

| File | Role |
|---|---|
| [`identity.md`](identity.md) | One identity line: the linope agent in the linope terminal |
| [`system_02_tools.md`](system_02_tools.md) | Routing text for file, shell, web, goals, and subagent calls |

## Model Experience

### System prompt

#### What the model sees

`identity.md` and `system_02_tools.md` are the stable prompt text. Tool JSON shapes in `system_02_tools.md` name capability ids such as `tools.read` and `tools.pwsh`. The tool schemas the process actually exposes are on each plugin under [`capability/tools/agent_tools`](../../../tools/agent_tools/README.md).

#### Token effect

The full text of both files, when a host inserts them. This directory does not truncate them.

#### KV Cache effect

Prefix-stable while both files are unchanged. Editing either file changes the prefix from that point.

## Known Limitations and Deferred Work

- **No loader in this directory** — nothing here copies the markdown into a model request or a memory `system` row.
- **Some named tools have no plugin here** — `system_02_tools.md` tells the model to call `tools.job_output`, `tools.job_kill`, `tools.get_goal`, `tools.create_goal`, and `tools.update_goal`. Those plugins are not in `agent_tools`.
