# agent_tools/ — model-facing tools

English | [中文](README.cn.md)

Each directory is one family of plugins. A plugin exposes `load`, `capability_profile`, and usually `tool_schemas()`. The string `load` returns is the tool result. Routing prose that names these tools is [`system_02_tools.md`](../../prompt/prompt_card/system/system_02_tools.md).

| Directory | Role |
|---|---|
| [`file_tools/`](file_tools/README.md) | Read, write, edit, search, and image files |
| [`shell_tools/`](shell_tools/README.md) | One-shot and persistent shells |
| [`terminal_tools/`](terminal_tools/README.md) | Persistent terminal sessions and desktop panes |
| [`code_tools/`](code_tools/README.md) | Run a Python program that calls other tools |
| [`web_search_tools/`](web_search_tools/README.md) | Provider-specific web search |
| [`interaction_tools/`](interaction_tools/README.md) | Ask the user a question |
