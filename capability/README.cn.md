# capability/ — 进程可以加载的插件

[English](README.md) | 中文

这棵树是业务侧。内核启动进程并绑定它的资源记录。插件文件拥有卡片、工具参数和提示词文本。一个操作系统进程加载一个插件。模型和它调用的工具是对等进程，各自有自己的记录。

增加一个能力，就是增加一个本目录扫描能看见的文件。内核没有一份要去改的登记表。

[`process_adapter.py`](process_adapter.py) 随每次启动一起加载。`create_adapter()` 在已经加载的模块上找到 `load` 或 `load_async`，并转发一次请求。它只接受操作 `load`。卡片、消息形状和压缩选择留在插件里。

## 内核如何找到插件

[`kernel/process/process_creat`](../kernel/process/process_creat/README.cn.md) 里的 [`discover_instances`](../kernel/process/process_creat/instances.py) 遍历本目录。一个文件被登记，需要同时满足两条：

- 文件名以 `_plugin.py` 结尾。
- 文件文本里有 `def load(` 或 `async def load(`。

带了 `load` 函数的 `weather.py` 不会被看见。没有 `load` 函数的 `*_plugin.py` 也不会被看见。扫描读的是文本，不会为了判断而导入该文件。

能力名由路径算出来：

| 位置 | 名字 |
|---|---|
| `capability/tools/.../glob_plugin.py` | `tools.glob` |
| `capability/model/.../openai_chat_model/*_plugin.py` | `model.openai_chat_model` |
| 嵌在 `capability/sandbox/` 下的插件 | `sandbox.sandbox` |
| `capability/<family>/.../thing_plugin.py` | `<family>.thing` |

`model` 用的是上一级目录名。`tools` 用的是去掉 `_plugin` 之后的文件名。直接放在 `capability/sandbox/` 里的插件会叫 `sandbox.<文件名>`；当前的入口是嵌套的，所以名字是 `sandbox.sandbox`。其他家族用第一级目录名和文件名。一个名字只保留一个文件。两个文件算出同一个名字时，留下排序后较后的那条路径。

`capability/prompt` 下名为 `prompt_main.py` 且定义了 `load` 的文件也会被登记，名字是 `prompt.<group>`。这棵树里没有这样的文件。

`linope process start <capability>` 启动一个已登记的名字。

## 可启动的插件要提供什么

[`kernel/process`](../kernel/process/README.cn.md) 的 `profile.py` 在打开记录之前调用 `capability_profile(capability_id, changes)`。该函数返回一份 `ProcessDeclaration`：能力名，以及它要租用的资源。种类是 `tool`、`sandbox`、`network` 和 `memory`。没有可用画像或画像失败时抛出 `ProfileUnavailable`，进程不会启动。卡片留在插件内部。

之后的请求调用 `load(kind, body, call_params=None)`。`kind` 是资源种类，例如 `tool`。`body` 是这次调用。`call_params` 是租约带进来的参数。异步插件再写一个参数相同的 `async def load_async(...)`。希望模型能看见的工具再提供 `tool_schemas()`。

工具的这份声明由 [`kernel/process/profiles.py`](../kernel/process/profiles.py) 里的 `tool_with_workspace` 和 `tool_only` 生成。哪些名字算只读、命令或写入，以及 `--change permission=` 和 `--change capabilities=` 如何选择模型能看见的工具，在 [`kernel/process`](../kernel/process/README.cn.md)。

## 目录

| 目录 | 职责 |
|---|---|
| [`model/`](model/README.cn.md) | 可启动的提供者插件，名字是 `model.<提供者目录>`。卡片、SDK 调用、消息块，以及加载一张点名卡片的运行时都在这里。回合在 [`kernel/scheduler`](../kernel/scheduler/README.cn.md)。 |
| [`tools/`](tools/README.cn.md) | 可启动的代理工具和外部宿主，名字是 `tools.<文件名>`：文件、shell、终端、代码、网页搜索、向用户提问，以及 MCP。`load` 接受种类 `tool`。 |
| [`sandbox/`](sandbox/README.cn.md) | 文件写入模式 `read-only`、`workspace-write`、`danger-full-access`，以及平台包装器。可启动的入口是 `sandbox.sandbox`。这里其余的 `*_plugin.py` 是 [`kernel/environment`](../kernel/environment/README.cn.md) 按路径加载的后端。Docker 工作区是另一份契约。 |
| [`context/`](context/README.cn.md) | 语义、摘要和滑动窗口压缩。每个包的入口文件叫 `capability_profile.py`，因此 `*_plugin.py` 的遍历不会登记它。`load` 在该文件夹里选出签名与正文相符的那一个函数。 |
| [`prompt/`](prompt/README.cn.md) | 系统提示词 Markdown。本目录没有 `load`。想使用这些文本的宿主自己读文件。 |
