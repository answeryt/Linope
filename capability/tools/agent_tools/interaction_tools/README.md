# interaction_tools

English | [中文](README.cn.md)

Ask the user a question and wait for an answer the host injects.

## Contract

`ask_user_plugin.py` is `PLUGIN_NAME` `ask_user`. The schema name is `ask_user_question`. `load` accepts kind `tool`.

The body is `questions`, a list. Each item has a stable `id` and a `question`. Optional fields include `header` and `options`. If one option is the recommended choice, the schema tells the model to put it first and append `(Recommended)` to that label.

The answer is produced by the host-injected provider. This plugin does not read the terminal itself.

## Model Experience

### Tool schema

#### What the model sees

`tool_schemas()`: one or more questions, each echoed back by `id`. This tool is for a confirmation, a choice, or missing information. It is not a subagent `ask`. Subagent handoff is [`kernel/command/process`](../../../../kernel/command/process/README.md).

#### Token effect

A fixed schema while the plugin is visible. The result is the answer object the host returns.

#### KV Cache effect

The schema is prefix-stable while the plugin is unchanged. The answer appends after the model returns.

## Known Limitations and Deferred Work

- **No answer without an injected provider** — the plugin waits on the host function. A missing provider fails the call instead of reading stdin.
