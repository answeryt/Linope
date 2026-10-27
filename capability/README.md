# capability/ — plugins a process can load

English | [中文](README.cn.md)

This tree is the business side. The kernel starts a process and binds its resource record. The plugin file owns the card, the tool arguments, and the prompt text. One operating-system process loads one plugin. A model and the tools it calls are peer processes, each with its own record.

Adding a capability is adding a file this tree's scan can see. The kernel has no registry to edit.

[`process_adapter.py`](process_adapter.py) is loaded with every start. `create_adapter()` finds `load` or `load_async` on the modules already loaded and forwards one request. The only operation it accepts is `load`. It leaves the card, the message shape, and the compression choice in the plugin.

## How the kernel finds a plugin

[`discover_instances`](../kernel/process/process_creat/instances.py) in [`kernel/process/process_creat`](../kernel/process/process_creat/README.md) walks this directory. A file is registered only when both are true:

- The file name ends with `_plugin.py`.
- The file text contains `def load(` or `async def load(`.

`weather.py` with a `load` function stays unseen. A `*_plugin.py` file with no `load` function stays unseen. The scan reads the text. It does not import the file to decide.

The capability name is computed from the path:

| Place | Name |
|---|---|
| `capability/tools/.../glob_plugin.py` | `tools.glob` |
| `capability/model/.../openai_chat_model/*_plugin.py` | `model.openai_chat_model` |
| a plugin nested under `capability/sandbox/` | `sandbox.sandbox` |
| `capability/<family>/.../thing_plugin.py` | `<family>.thing` |

`model` uses the parent directory name. `tools` uses the file name with `_plugin` removed. A plugin sitting directly in `capability/sandbox/` would be `sandbox.<file stem>`; the current entry is nested, so its name is `sandbox.sandbox`. Any other family uses its first directory and the file name. One name keeps one file. Two files that compute the same name leave the later path in sorted order.

A file named `prompt_main.py` under `capability/prompt` is also registered, as `prompt.<group>`, when it defines `load`. This tree has no such file.

`linope process start <capability>` starts one registered name.

## What a startable plugin provides

[`kernel/process`](../kernel/process/README.md) `profile.py` calls `capability_profile(capability_id, changes)` before the record is opened. The function returns a `ProcessDeclaration`: the capability name and the resources it leases. The kinds are `tool`, `sandbox`, `network`, and `memory`. A missing or failing profile raises `ProfileUnavailable`, and the process does not start. The card stays inside the plugin.

A later request calls `load(kind, body, call_params=None)`. `kind` is the resource kind, such as `tool`. `body` is the call. `call_params` is what the lease carried in. An async plugin adds `async def load_async(...)` with the same arguments. A tool the model should be offered also exposes `tool_schemas()`.

`tool_with_workspace` and `tool_only` in [`kernel/process/profiles.py`](../kernel/process/profiles.py) build that declaration for a tool. Which names count as read, command, or write, and how `--change permission=` and `--change capabilities=` choose the tools a model sees, is [`kernel/process`](../kernel/process/README.md).

## Directories

| Directory | Role |
|---|---|
| [`model/`](model/README.md) | Startable provider plugins, named `model.<provider directory>`. The card, the SDK call, the message blocks, and the runtime that loads a named card live here. The turn is [`kernel/scheduler`](../kernel/scheduler/README.md). |
| [`tools/`](tools/README.md) | Startable agent tools and external hosts, named `tools.<file stem>`: files, shell, terminal, code, web search, questions, and MCP. `load` accepts kind `tool`. |
| [`sandbox/`](sandbox/README.md) | File-write modes `read-only`, `workspace-write`, and `danger-full-access`, plus the platform wrappers. The startable entry is `sandbox.sandbox`. Other `*_plugin.py` files here are backends [`kernel/environment`](../kernel/environment/README.md) loads by path. The Docker workspace is a separate contract. |
| [`context/`](context/README.md) | Semantic, summary, and sliding-window compression. Each package's entry is `capability_profile.py`, so the `*_plugin.py` walk does not register it. `load` picks the one function in the folder whose signature fits the body. |
| [`prompt/`](prompt/README.md) | System-prompt markdown. This directory has no `load`. A host that wants the text reads the files itself. |
