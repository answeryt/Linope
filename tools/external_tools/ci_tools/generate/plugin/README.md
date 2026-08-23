# plugin

插件约定 CI：审查仓库里的 plugin family 是否原子、隔离、入口正确，并生成 allow / deny 清单。

Host 是组合层，不是检查项。它用 importlib 按文件名加载 `*_check.py` / `*_generate.py`（与 pypyr 按 step 名加载相同），不静态导入各插件。

## 定位

- 扫描范围：仓库顶层目录（跳过缓存、点目录、`*-main` 第三方树）；新 plugin 根目录无需改 Host
- 审查：各 `*_check.py` 共享一份 context，只向 `violations` 追加违规
- 生成：各 `*_generate.py` 按 `--format` 写出 list card（json / yaml / toml / md）
- 唯一手写清单是 allow list；deny list = 发现到的 family 减去 allow 路径
- `--check`：已提交的 list card 过期，或存在 `severity=error` 的违规时失败

## 目录结构

```text
plugin/
  plugin_generate.py          Host
  README.md
  list/
    deny_list/                默认约束 + deny card 生成
      deny_check.py
      deny_list_generate.py
      deny_list_crad/list.*
    allow_list/               手写豁免 + allow card 生成
      allow_check.py
      allow_list_generate.py
      allow_list_card/list.*
  host_sibling/               按磁盘上的家族形态推断合同
    surface_check.py
    sdk_boundary_check.py
    provider_config_check.py
    kernel_check.py
```

## 文件说明

| 文件 | 插件名 | 职责 |
| --- | --- | --- |
| `plugin_generate.py` | `plugin_generate_host` | 发现 family、划分 deny/allow、加载并执行插件 |
| `list/deny_list/deny_check.py` | `plugin_deny` | facade 禁止聚合层；禁止跨 plugin / 兄弟文件互导 |
| `list/deny_list/deny_list_generate.py` | `plugin_deny_generate` | 写出 deny list card |
| `list/allow_list/allow_check.py` | `plugin_allow` | 赦免 `.gates` 隔离边；检查必注入参数 |
| `list/allow_list/allow_list_generate.py` | `plugin_allow_generate` | 读写手写 allow list card |
| `host_sibling/surface_check.py` | `plugin_surface` | 按文件形态推断入口合同 |
| `host_sibling/sdk_boundary_check.py` | `plugin_sdk_boundary` | `call_api` 家族必须是薄、懒加载的 SDK 封装 |
| `host_sibling/provider_config_check.py` | `plugin_provider_config` | provider 模板多格式等价、禁止当代码用 |
| `host_sibling/kernel_check.py` | `plugin_kernel` | kernel 分层、ProcessRun/Activation、OS/部署边界。架构词汇和结构树在各层生成器 |

## 审查规则

### deny：原子与隔离

- `facade.filename`：family 内不得出现 `host.py` / `facade.py`
- `facade.barrel_init`：`__init__.py` 不得再导出兄弟插件
- `isolation.sibling_import`：不得 import 同 family 其它插件文件
- `isolation.cross_plugin_import` / `isolation.project_import`：不得 import 其它项目插件
- 标准库与未能解析到仓库内文件的第三方 import 放行；显式例外放在 allow list

### allow：豁免与注入

- `paths`：这些路径不进入生成的 deny list
- `.gates/isolation-allowlist.json` 的 edges：在 deny 跑完后赦免对应隔离违规
- `inject`：指定 stem 必须接收的参数（例如 `message_tokens` 必须注入 `text_estimator`），避免插件去 import 兄弟估算器
- `kernel_layers`：kernel 结构图库存，由 `kernel_check` 读取
- `injection.estimator_param`：缺少必注入参数时报错

### host_sibling：合同由磁盘推断，不写死 Host kind 表

| 形态 | 要求 |
| --- | --- |
| `*_plugin.py` | `PLUGIN_NAME`、`PLUGIN_VERSION`；`PLUGIN_NAME` 全局唯一 |
| `*_check.py` / `*_generate.py` | `PLUGIN_NAME`、`PLUGIN_VERSION`、`run(context)` |
| family 中已有 `call_api` | 每个模块都暴露 `call_api` |
| family 中已有 `apply_*` | 每个模块暴露 `apply_<stem>` |
| 其它 | 至少一个公开函数或类 |

对已有 `call_api` 的 family，额外约束：

- Provider SDK（`openai` / `anthropic` / `google` / `genai`）必须在 `call_api` 内 import，不能出现在模块顶层
- 不得提供 retry / format_message / parse_response / convert_tools 这类公开助手

对看起来像 provider 根目录的 family：每个 provider 子目录必须同时有 YAML、JSON、TOML，顶层键 `provider` / `interface` / `model` / `api_key_env` / `parameters` 一致；`interface` 必须对应 `model/model_API/model_interface/<interface>.py`。

`kernel_check.py` 约束 `kernel/`：顶层只允许 allow card 声明的层；插件落在叶目录；ProcessRun 必须包含 process/run ID、定义版本、状态、Activation 与资源 lease；Activation 必须可序列化；Process/Task/Resource 层不得使用 OS process/thread 或部署 API。

## 生成清单

allow list 是唯一手写库存，字段：

- `paths`：豁免路径
- `inject`：stem → 必注入参数名（含 kernel 插件）
- `kernel_layers`：手写库存，由 `kernel_check` 经 `load()` 读取

deny list 由 Host 发现结果减去 allow 路径生成，字段：

- `families`：纳入默认约束的 plugin family 根路径

`--check` 时不写文件，只对比已提交 card 是否过期，过期路径记入 `stale`。

## 调用关系

```text
python plugin_generate.py [--check] [--format json|yaml|toml|md] [--root ...]

plugin_generate.py (Host)
  → 从磁盘发现 family，用 allow list 划分 denied / allowed
  → 审查：deny_check → allow_check → surface / sdk_boundary / provider_config / kernel_check
  → 生成：allow_list_generate → deny_list_generate
  → --check：stale 或 error 违规 → exit 1
  → 默认：写出 list card；仍有 error 违规 → exit 1
```

插件约定：每个 `*_check.py` / `*_generate.py` 暴露 `PLUGIN_NAME`、`PLUGIN_VERSION`、`run(context)`。Host 把同一份 context 依次传入；检查项只追加 `violations`，生成项只写 card。

## 设计思想

将 Host、审查、生成拆开：Host 只发现与编排，检查项不写文件，生成项不判隔离。手写 allow、自动 deny，新增 plugin family 默认进入约束，只有明确豁免才离开 deny list。
