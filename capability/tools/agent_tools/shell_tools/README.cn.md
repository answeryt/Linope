# shell_tools

[English](README.md) | 中文

Shell 工具。每次 `load` 接受种类 `tool`。bash 的字符串正文同时当作 `command` 和 `description`。

| 插件 | Schema 名 | 职责 |
|---|---|---|
| `pwsh_plugin.py` | `pwsh` | 一个 `pwsh -Command` 进程。先找 `pwsh`，再找 `powershell`，再找 `powershell.exe`。 |
| `bash_plugin.py` | `bash` | 一个 `bash -c` 进程。该模块没有 `PLUGIN_NAME`。 |
| `bash_persistent_plugin.py` | `bash` | `PLUGIN_NAME` 是 `bash_persistent`。schema 名是 `bash`。状态在该代理的多次调用之间保留。 |

一次性调用需要 `command` 和 `description`。`timeoutMs` 默认 60000。`workdir` 是那次调用的工作目录。`run_in_background: true` 返回一个作业 id，并且不施加超时。长于 100000 个字符的输出保留尾部。非零退出标成 `[exit code: N]`。

## 模型体验

### 工具 schema

#### 模型看到什么

schema 文本说每次一次性调用都是一个新进程：工作目录、变量和函数不会带过去。用 `workdir` 指定目录。[`system_02_tools.md`](../../../prompt/prompt_card/system/system_02_tools.md) 里的 Windows 路由行点名 `tools.pwsh`。其他系统被告知使用 `tools.bash`。

#### Token 影响

工具可见时是一份固定 schema。结果是 stdout 和 stderr，超过 100000 个字符时截到尾部。

#### KV Cache 影响

插件不变时 schema 的前缀稳定。每次结果都追加。后台作业 id 是一条短结果。后来的输出不会被这个插件推进对话。

## 已知限制与暂缓事项

- **`bash_persistent` 公布的 schema 名是 `bash`** — 与 `bash_plugin.py` 使用的名字相同。持久插件上的 `PLUGIN_NAME` 是 `bash_persistent`。
- **后台作业留在一次性工具内部** — schema 说这里没有单独的工具去读或停止那个作业。`system_02_tools.md` 仍然点名 `tools.job_output` 和 `tools.job_kill`，它们不是这棵树里的插件。
- **`bash` 没有 `PLUGIN_NAME`** — 按 `PLUGIN_NAME` 查找的发现看不到 `bash_plugin.py`。`load` 仍然按名字 `bash` 分发。
