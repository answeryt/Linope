# tools/ — agent tools and external tool hosts

English | [中文](README.cn.md)

Tools are capability plugins. A process loads one plugin. `load` accepts kind `tool` and a mapping body. `capability_profile` is what [`kernel/process`](../../kernel/process/README.md) asks for at start.

The directories below group the plugins. Which tools a model may be offered, and the sandbox mode each tool process receives, is decided by the name after `tools.` in [`kernel/process`](../../kernel/process/README.md). `tools.read` is a read tool because its name is `read`.

| Directory | Role |
|---|---|
| [`agent_tools/`](agent_tools/README.md) | File, shell, terminal, code, web, and user-question tools |
| [`external_tools/`](external_tools/README.md) | MCP client plugins and the plugin-convention CI |
