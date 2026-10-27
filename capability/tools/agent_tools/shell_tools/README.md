# shell_tools

English | [中文](README.cn.md)

Shell tools. Each `load` accepts kind `tool`. A string body for bash is treated as both `command` and `description`.

| Plugin | Schema name | Role |
|---|---|---|
| `pwsh_plugin.py` | `pwsh` | One `pwsh -Command` process. Looks for `pwsh`, then `powershell`, then `powershell.exe`. |
| `bash_plugin.py` | `bash` | One `bash -c` process. The module has no `PLUGIN_NAME`. |
| `bash_persistent_plugin.py` | `bash` | `PLUGIN_NAME` is `bash_persistent`. The schema name is `bash`. State survives across calls for that agent. |

One-shot calls require `command` and `description`. `timeoutMs` defaults to 60000. `workdir` is the working directory for that call. `run_in_background: true` returns a job id and applies no timeout. Output longer than 100000 characters keeps the tail. A non-zero exit is marked `[exit code: N]`.

## Model Experience

### Tool schema

#### What the model sees

The schema text says each one-shot call is a fresh process: working directory, variables, and functions do not carry over. Use `workdir` for the directory. The Windows routing line in [`system_02_tools.md`](../../../prompt/prompt_card/system/system_02_tools.md) names `tools.pwsh`. Other systems are told to use `tools.bash`.

#### Token effect

A fixed schema while the tool is visible. The result is stdout and stderr, truncated to the tail past 100000 characters.

#### KV Cache effect

The schema is prefix-stable while the plugin is unchanged. Each result appends. A background job id is a short result. Later output is not pushed into the conversation by this plugin.

## Known Limitations and Deferred Work

- **`bash_persistent` publishes the schema name `bash`** — the same name `bash_plugin.py` uses. `PLUGIN_NAME` on the persistent plugin is `bash_persistent`.
- **Background jobs stay inside the one-shot tool** — the schema says there is no separate tool here to read or stop that job. `system_02_tools.md` still names `tools.job_output` and `tools.job_kill`, which are not plugins in this tree.
- **`bash` has no `PLUGIN_NAME`** — discovery that keys on `PLUGIN_NAME` will not see `bash_plugin.py`. `load` still dispatches the name `bash`.
