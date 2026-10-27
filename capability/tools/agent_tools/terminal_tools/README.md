# terminal_tools

English | [中文](README.cn.md)

Persistent terminal sessions, plus desktop pane tools that run only when the host injects a callback.

`load` accepts kind `tool`. Session tools talk to a terminal backend. Pane tools return an error when the host did not inject the emitter or closer.

| Plugin | Role |
|---|---|
| `terminal_open_plugin.py` | Create an owner-isolated session. Requires `type`. Optional `name` and `cwd`. |
| `terminal_send_plugin.py` | Send text into a session. |
| `terminal_read_session_plugin.py` | Read retained output without sending input. |
| `terminal_list_plugin.py` | List sessions owned by the current agent. |
| `terminal_close_session_plugin.py` | Close one session and wait until its process tree is gone. |
| `terminal_signal_plugin.py` | Send an allowed signal to the foreground process group. |
| `terminal_plugin.py` | Combined terminal plugin, `PLUGIN_NAME` `terminal`. |
| `terminal_read_plugin.py` | Read the in-app pane when the host injects a callback. |
| `terminal_preview_plugin.py` | Open a URL or file in the preview pane when the host injects an emitter. |
| `terminal_focus_plugin.py` | Focus a desktop pane when the host injects an emitter. |
| `terminal_close_plugin.py` | Close a background-process tab when the host injects a closer. |

A sandbox or persistent terminal resource is the `sandbox` kind in [`kernel/resource`](../../../../kernel/resource/README.md). These plugins do not open that lease themselves. `capability_profile` does.

## Model Experience

### Tool schema

#### What the model sees

`tool_schemas()` on each plugin. `terminal_open` tells the model the session survives across tool calls. Pane plugins tell the model they need a host callback.

#### Token effect

A fixed schema per visible tool. Session reads return the retained output the plugin collected, not the whole lifetime of the terminal unless the plugin's own limit says so.

#### KV Cache effect

Schemas stay prefix-stable while the plugins are unchanged. Session output appends when a later call returns it.

## Known Limitations and Deferred Work

- **Pane tools need an injected host callback** — `terminal_read`, `terminal_preview`, `terminal_focus`, and `terminal_close` do not reach a desktop on their own.
- **`terminal_plugin.py` is a second terminal surface** — it sits beside the single-purpose session plugins.
