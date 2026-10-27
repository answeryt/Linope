# plugin

[English](README.md) | 中文

插件约定 CI：审查仓库里的插件家族是否原子、隔离、入口正确，并生成允许清单和拒绝清单。

宿主是组合层，不是检查。它用 importlib 按文件名加载 `*_check.py` / `*_generate.py`（与 pypyr 按名字加载一步的方式相同）。它不静态导入每个插件。

## 位置

- 扫描范围：Open-Linux 仓库根（它同时看到 `kernel/` 和 `capability/`）。跳过缓存、点目录、`*-main` 第三方树、嵌套 SDK 和参考实现（`temporal-sdk-python`、`restate-sdk-python`、`temporal`、`restate`），以及测试目录。新的插件根不需要改宿主。默认 `--root` 走到包含 `kernel/compose/capability/composition.yaml` 的目录。
- 审查：每个 `*_check.py` 共享一个上下文，并且只把违规追加到 `violations`。
- 生成：每个 `*_generate.py` 为 `--format`（json / yaml / toml / md）写一张清单卡片。
- 唯一手写的清单是允许清单。拒绝清单是发现到的家族减去允许路径。
- `--check`：已提交的清单卡片过期，或某条违规的 `severity=error` 时失败。

## 要安装的包

这些是第三方 PyPI 包，不是仓库模块之间的导入。CI 只静态解析源码，不导入它们。安装它们是为了运行审查，或加载内置的 `sphinxext`。

| 包 | 用途 | 谁使用 |
| --- | --- | --- |
| `PyYAML` | 读宿主 `composition.yaml` 和清单卡片 | `host_sibling/lip_check.py`，允许和拒绝生成器 |
| `sphinx` | Sphinx 文档引擎（也会安装 `sphinxcontrib-*`、`alabaster`、`babel` 等） | `kernel/compose/plugin/vendor/stevedore/src/stevedore/sphinxext.py` |
| `docutils` | reStructuredText 解析（`sphinx` 的依赖） | 同一文件：`nodes` / `rst` / `directives` / `StringList` |

```text
python -m pip install PyYAML sphinx docutils
```

`sphinxext.py` 顶部的 `from sphinx ...` / `from docutils ...` 是文档扩展的第三方依赖。`from stevedore import extension` 是内置包内部的引用。叶子插件仍然不得导入 `stevedore`。如果不写 Sphinx 插件清单，不需要安装 `sphinx`。

## 布局

```text
plugin/
  plugin_generate.py          宿主
  README.md
  list/
    deny_list/                默认约束 + 拒绝卡片生成
      deny_check.py
      deny_list_generate.py
      deny_list_crad/list.*
    allow_list/               手写豁免 + 允许卡片生成
      allow_check.py
      allow_list_generate.py
      allow_list_card/list.*
    host_sibling/             从磁盘上的家族形状推断契约
      surface_check.py
      sdk_boundary_check.py
      provider_config_check.py
      kernel_check.py
      lip_check.py
      assembly_check.py
      descriptor_check.py
```

## 文件

| 文件 | 插件名 | 职责 |
| --- | --- | --- |
| `plugin_generate.py` | `plugin_generate_host` | 发现家族，拆分拒绝/允许，加载并运行插件 |
| `list/deny_list/deny_check.py` | `plugin_deny` | 门面不得是聚合层；不得跨插件或兄弟文件导入 |
| `list/deny_list/deny_list_generate.py` | `plugin_deny_generate` | 写拒绝清单卡片 |
| `list/allow_list/allow_check.py` | `plugin_allow` | 赦免 `.gates` 隔离边；检查必需的注入参数 |
| `list/allow_list/allow_list_generate.py` | `plugin_allow_generate` | 读写手写的允许清单卡片 |
| `host_sibling/surface_check.py` | `plugin_surface` | 从文件形状推断入口契约 |
| `host_sibling/sdk_boundary_check.py` | `plugin_sdk_boundary` | `call_api` 家族惰性加载 SDK。消息格式化、响应解析和窗口恢复重试留在叶子。禁止工具 schema 转换 |
| `host_sibling/provider_config_check.py` | `plugin_provider_config` | 提供者卡片是一份 JSON，并且不得当作代码使用 |
| `host_sibling/kernel_check.py` | `plugin_kernel` | 内核层、ProcessRun/Activation，以及操作系统/部署边界。架构用词和结构树在每一层的生成器里 |
| `host_sibling/lip_check.py` | `plugin_lip` | 套接字路径：`composition.yaml` 里的 `sockets` / `modules` / `sources`。叶子插件不得导入 pluggy/stevedore/lip |
| `host_sibling/assembly_check.py` | `plugin_assembly` | 能力图路径：组合者只能把东西接在一起。它必须使用组合 Source。`register_adapter` 必须直接接到 `FunctionModelAdapter`。禁止手写 discover、种类翻译、按能力前缀扫描，以及反射成员之后的动态分发 |
| `host_sibling/descriptor_check.py` | `plugin_descriptor` | 叶子的 `CAPABILITY` / `MODEL_CAPABILITY`，以及 `plugin.json` 里开放簇的 kind、requires 和 entry |

## 审查规则

### deny：原子且隔离

- `facade.filename`：一个家族不得包含 `host.py` / `facade.py`
- `facade.barrel_init`：`__init__.py` 不得重新导出兄弟插件
- `isolation.sibling_import`：不得导入同一家族里的另一个插件文件
- `isolation.cross_plugin_import` / `isolation.project_import`：不得导入另一个项目的插件
- 标准库，以及无法解析到仓库内文件的第三方导入，是允许的。明确的例外放进允许清单

### allow：豁免与注入

- `paths`：这些路径不进入生成的拒绝清单（包括套接字引擎 `kernel/compose/plugin` 和能力图引擎 `kernel/compose/capability`）
- `.gates/isolation-allowlist.json` 里的边：deny 结束后，赦免匹配的隔离违规
- `inject`：某个具名主干必须接收的参数（例如 `sandbox_policy` 必须注入 `canonical_path`），这样插件就不导入兄弟实现
- `kernel_layers`：内核结构清单，由 `kernel_check` 读取
- `sockets`：套接字名到插头名再到叶子插件路径，由 `lip_check` 读取。宿主按名字加载。叶子插件不得导入一个实现
- `injection.estimator_param`：缺少必需的注入参数时记为错误

### host_sibling：契约从磁盘推断，不是宿主里写死的种类表

| 形状 | 要求 |
| --- | --- |
| `*_plugin.py` | `PLUGIN_NAME`、`PLUGIN_VERSION`。`PLUGIN_NAME` 全局唯一 |
| `*_check.py` / `*_generate.py` | `PLUGIN_NAME`、`PLUGIN_VERSION`、`run(context)` |
| 家族已经有 `call_api` | 每个模块都暴露 `call_api` |
| 家族已经有 `apply_*` | 模块暴露 `apply_*`。模型请求字段写在对应的 `model_interface` 文件里，不是一个字段一个文件 |
| 其他 | 至少一个公开函数或类 |

已经有 `call_api` 的家族的额外约束：

- 提供者 SDK（`openai` / `anthropic` / `google` / `genai`）必须在 `call_api` 内部导入，不在模块顶层
- 消息格式化、响应解析和上下文窗口恢复重试留在对应叶子（`format_messages` / `parse_response` / `parse_stream_chunk`；重试在 `call_api` 内部）
- 不得提供 `convert_tools` / `tool_choice_convert` 这类工具 schema 转换帮手

看起来像提供者根的家族：每个提供者子目录有一份 `<名称>.json` 卡片。顶层键 `provider` / `interface` / `model` / `api_key_env` / `parameters` 都在。`interface` 必须对应 `model/model_API/model_interface/<interface>.py`。

`kernel_check.py` 约束 `kernel/`：顶层只能包含允许卡片声明的层；插件放在叶子目录；一次 ProcessRun 必须包含进程/运行 id、定义版本、状态、Activation 和资源租约；Activation 必须可序列化；Process/Task/Resource 层不得使用操作系统进程/线程或部署 API。`kernel/compose/plugin/` 是套接字引擎（pluggy / stevedore / lip），不检查操作系统或部署导入。

不要混用两条组装路径：

- 套接字路径：`kernel/compose/capability/composition.yaml` 里的 `sockets` / `modules` / `sources`，由 `lip_check.py` 审查。
- 能力图路径：`ComposeSpec` 加上 Sources，由 `assembly_check.py` 审查。叶子描述符由 `descriptor_check.py` 审查。

`lip_check.py` 约束能力查找：组合里的一条 `sockets` 必须指向存在的插头文件，并且该文件里的 `PLUGIN_NAME` 必须与插头名相符。`*_plugin.py`、宿主 `manager/lip/board.py`，以及其他非引擎家族文件，不得导入 `pluggy` / `stevedore` / `lip`。套接字板是 `manager/stevedore` 的本地分叉（包内相对导入）。宿主只按文件路径加载。跨插件文件的导入仍是 deny_check 的事。如果有 `sources`，`type` 必须能被 `source_from_mapping` 识别。

`assembly_check.py` 约束能力图组装：导入 `CapabilityCatalog` / `CapabilityGraphResolver` / `ComposeSpec`，并且不在 `kernel/compose/` 或 `tests/kernel/` 下的文件是组合者。组合者必须使用 `inject` / `inject_capabilities` / `CapBus` / `Capability`。它不得 `ast.parse`，不得自己写 `discover()`，不得再写一张种类翻译表，也不得按能力前缀扫描。未使用 `FunctionModelAdapter` 时，它不得 `inspect.signature`，也不得用鸭子类型在四种 ABI 之间做回退。`register_adapter` 必须直接接到 `FunctionModelAdapter`（不能先包一层再登记）。它不得通过 `vars/dir/getmembers + startswith + 动态调用` 反射叶子调用细节。

这条规则是一般的角色边界，不是模型的特例：组合者只应组装。它不应塑造请求、编排重试，或靠反射分发。

`descriptor_check.py` 约束开放簇描述符：`kind` 是插件自己声明的簇（可以用点细化），不是内核允许表。`name` 或 `provides` 必须落在该簇下。`requires` 使用与内核 `parse_requirements` 相同的语法。`entry` 必须指向存在的函数。旧的加载器用词（`recipe` / `module` / `tool` / `model`）不得再用作 `kind`。

## 生成的清单

允许清单是唯一手写的清单。字段：

- `paths`：豁免路径
- `inject`：主干到必需注入参数名（包括内核插件）
- `kernel_layers`：手写清单，由 `kernel_check` 通过 `load()` 读取
- `sockets`：手写清单，由 `lip_check` 读取。宿主按套接字名和插头名加载叶子插件

拒绝清单由宿主的发现结果减去允许路径生成。字段：

- `families`：默认约束下的插件家族根路径

`--check` 不写文件。它只比较已提交卡片是否过期。过期路径记在 `stale`。

## 调用路径

```text
python plugin_generate.py [--check] [--format json|yaml|toml|md] [--root ...]

plugin_generate.py (Host)
  → discover families from disk and split denied / allowed with the allow list
  → review: deny_check → allow_check → surface / sdk_boundary / provider_config / kernel_check / lip_check / assembly_check / descriptor_check
  → generate: allow_list_generate → deny_list_generate
  → --check: stale or an error violation → exit 1
  → default: write the list cards; if an error violation remains → exit 1
```

插件约定：每个 `*_check.py` / `*_generate.py` 暴露 `PLUGIN_NAME`、`PLUGIN_VERSION` 和 `run(context)`。宿主按顺序传递同一个上下文。检查只追加 `violations`。生成器只写卡片。

## 设计

宿主、审查和生成是分开的。宿主只发现和编排。检查不写文件。生成器不判断隔离。允许清单手写，拒绝清单自动。新的插件家族默认进入约束，只有明确豁免才离开拒绝清单。

## 已知限制与暂缓事项

- **默认根使用这棵树没有的标记** — `find_repo_root` 寻找 `.gates/isolation-allowlist.json`、顶层 `model/` 和 `tools/`，以及 `kernel/compose/capability`。这些路径在这里不存在，因此函数回退到本文件之上的六层父目录。
- **`sphinx` 是为一个内置扩展路径点名的** — `kernel/compose/plugin/vendor/stevedore` 不在这棵树里。只有那个扩展在场时才安装 `sphinx`。清单卡片需要的是 `PyYAML`。
