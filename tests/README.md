# 测试目录约定

测试服从插件隔离与 Host 组装边界：谁不该互相 import，测试里也不该互相 import。不为每个插件启动整套 Agent。Kernel 提供测试制度，不提供“插件总测试包”。

静态 CI（`plugin_generate.py --check`）管架构违约。本目录的 unittest 管行为违约。两边不互相替代。

## 三层插件合同（不可混用）

| 合同 | 适用对象 | 行为测试落在哪一层 |
| --- | --- | --- |
| CI 叶合同 | 所有 `*_plugin.py`：`PLUGIN_NAME`、隔离、公开函数 | `plugin-unit` 或 `kernel-unit`，按文件加载 |
| Socket 插头合同 | `lip.get(socket, name)` 的实现，如 `exec_command.dispatch` | 叶测合同形状；compose 测按名查找与换实现 |
| Host 装配合同 | `apply(lip, config)` Recipe；发现 / Fiber / 能力 | 仅 `compose` |

## 三层测试 × 三层合同

| 运行层 | 测什么合同 | 放哪里 | 夹具 |
| --- | --- | --- | --- |
| `plugin-unit` | CI 叶合同：身份、公开函数、注入面；工具另加 `tool_schemas` / `dispatch` | `plugins/<family>/.../tests/`；UI 在 [`tests/ui/`](ui/ui_plugin_test.py) 按文件加载 [`plugins/ui/`](../plugins/ui/) | 按文件加载；假注入对象。**不得** import Host / `lip` 内部 |
| `kernel-unit` | Kernel 叶合同：Journal 重放、Process 终态、Compose 执行、Resource lease | [`tests/kernel/`](kernel/) | 按文件加载 kernel `*_plugin.py`；内存 Store / Journal / Queue。**不得** import Host harness |
| `compose` | Socket 插头合同（`dispatch`）与 Host 装配合同（发现、能力图、`compile_runtime`） | [`tests/kernel/lip_board_test.py`](kernel/lip_board_test.py)、[`tests/kernel/compose_composer_test.py`](kernel/compose_composer_test.py) | `inject_capabilities`；内存 Resource / Compose runtime |

```text
plugin-unit  （秒级，无 Host）
    → kernel-unit  （内存制度）
        → compose  （少量接缝）
```

默认开发循环只跑当前改动所在族的 plugin-unit 与相关 kernel-unit。compose 留给装配改动。从仓库根目录设置 `PYTHONPATH` 后运行对应测试文件，例如：

```text
python plugins/tools/agent_tools/file_tools/tests/read_test.py
python tests/kernel/process_runtime_test.py
python tests/kernel/compose_composer_test.py
```

## 家族合同（plugin-unit 不要用一把 dispatch 套所有叶）

- **agent tools**：`PLUGIN_NAME` / `PLUGIN_VERSION`、`tool_schemas()`、`dispatch(name, arguments, **injected)`；错误走工具 JSON。
- **exec_command 插座**：必须有 `dispatch`；叶测试用假 subprocess 测该插头自己的校验；换实现的查找在 compose 层用假插头，不测真实 bash 发行版。
- **model interface**：`call_api(...)`，测试 mock SDK，禁止真实网络。
- **model 参数叶**：`apply_<stem>(...)`。
- **provider 卡片**：json / yaml / toml 键等价，不当代码执行。
- **context 压缩**：输入 `list[dict]`，不改原列表；token / policy 全部注入。
- **prompt**：卡片多格式键等价；builder 只接受注入的 plugin / 参数，不启动模型。
- **sandbox**：注入 `canonical_path` / `effective_mode` / profiles。
- **MCP**：协作者（`env` / `secret_getter` / cache 目录）作为构造参数注入，不连真实 MCP server。
- **UI**：协作者全部作为参数注入；[`tests/ui/ui_plugin_test.py`](ui/ui_plugin_test.py) 按文件加载 `plugins/ui/` 各叶。

## 夹具规则

1. **按文件加载**：`importlib.util.spec_from_file_location`。叶测试把 `_load()` 写在本族 `tests/`（见 sandbox / `read`）；kernel-unit 用各文件顶部的 `load()`；compose 层用 `inject_capabilities`。
2. **内存制度**：kernel-unit 加载仓库内的内存 Journal / Store / Queue，不 mock 它们的内部，也不引入 FastAPI / Redis / OpenAI。
3. **假插座**：compose 层在测试里注入假插头，不要把假插头写进生产能力图。
4. **叶测试不得 import** `kernel.compose.capability` 的 Host 装配入口，也不得 import 兄弟 `*_plugin.py`。
5. **发现不得执行插件**：`PythonPluginSource` 只做 AST 索引。compose 已覆盖“discover 时 raise 也不该被 import”。
6. **样板优先，禁止铺全矩阵。** 每个家族一份同样加载方式的样板即可。

## Kernel 测什么、不测什么

- 测叶是否满足本族公开面；不把 Host 当 import 入口去测叶。
- 测插座按名查找、换插头后调用方不变；不铺工具 × 模型的集成大网。
- 测 Fiber：依赖消失卸载、回来再激活；不为每个插件启动 Service / Worker / Agent。
- 测 Journal 保证 Task 副作用不在重放时重跑；不在 Process 测试里直接调 `read_plugin.dispatch`。
- 测 CI 隔离 / 命名 / 注入参数；不用静态 CI 代替行为断言。

工具进 Process 的接法是：plugin-unit 保证 `dispatch` → kernel-unit 保证 `ctx.run(task)` 只执行一次并写入 journal → compose 保证 Host 能把对应 kind 接到 `tools` / `llm` / contribution 服务。

## 首批样板

| 目标 | 层 | 文件 |
| --- | --- | --- |
| Compose `compile_runtime` 与能力图 | compose | [`tests/kernel/compose_composer_test.py`](kernel/compose_composer_test.py) |
| 插座板 / 能力注入 | compose | [`tests/kernel/lip_board_test.py`](kernel/lip_board_test.py) |
| Process / Journal 重放 | kernel-unit | [`tests/kernel/process_runtime_test.py`](kernel/process_runtime_test.py) |
| Resource / binding | kernel-unit | [`tests/kernel/resource_thread_test.py`](kernel/resource_thread_test.py) |
| agent tool `read` | plugin-unit | [`plugins/tools/agent_tools/file_tools/tests/read_test.py`](../plugins/tools/agent_tools/file_tools/tests/read_test.py) |
| `exec_command` 叶合同（假 subprocess） | plugin-unit | [`plugins/tools/agent_tools/shell_tools/tests/bash_test.py`](../plugins/tools/agent_tools/shell_tools/tests/bash_test.py) |
| prompt 卡片与注入拼装 | plugin-unit | [`plugins/prompt/system_prompt/tests/parameters_test.py`](../plugins/prompt/system_prompt/tests/parameters_test.py) |
| context 压缩注入面 | plugin-unit | [`plugins/context/context_compression/sliding_window/tests/last_n_users_test.py`](../plugins/context/context_compression/sliding_window/tests/last_n_users_test.py) |
| model `call_api` mock SDK | plugin-unit | [`plugins/model/model_API/model_interface/tests/openai_chat_test.py`](../plugins/model/model_API/model_interface/tests/openai_chat_test.py) |
| MCP 注入面 | plugin-unit | [`plugins/tools/external_tools/mcp/tests/config_test.py`](../plugins/tools/external_tools/mcp/tests/config_test.py) |
| UI 注入面 | plugin-unit | [`tests/ui/ui_plugin_test.py`](ui/ui_plugin_test.py) |
| 真实插座查找（bash/pwsh 合同形状） | compose | [`tests/kernel/lip_board_test.py`](kernel/lip_board_test.py) |
| Compose 重试 / 超时 / binding 回滚 | kernel-unit | [`tests/kernel/resource_thread_test.py`](kernel/resource_thread_test.py) |
