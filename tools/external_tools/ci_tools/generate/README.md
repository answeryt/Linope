# generate

Generate 的 CI：审查仓库插件约定，并生成 allow / deny 清单；分层脚本只写 kernel 架构，不写代码合同。

## 定位

- 介于仓库源码与 CI 门禁之间
- 审查（`plugin/*_check.py`）：检查 facade、隔离、入口表面、SDK 边界、provider 配置、kernel 代码分层
- 生成（`plugin/*_generate.py`）：写出 allow / deny list card（json / yaml / toml / md）
- 架构（`services` / `process` / `thred`）：写出 Host Adapter、持久 Process Runtime、Task Function 与资源需求；代码形状仍由 `plugin` 审查
- Host 只负责发现插件并共享 context，不静态导入各检查项

## 文件说明

| 路径 | 职责 |
| --- | --- |
| `plugin/plugin_generate.py` | Host：发现 `*_check.py` / `*_generate.py`，组装 context，执行审查与生成 |
| `plugin/list/deny_list/` | 审查 plugin family 的原子性与隔离，生成 deny list card |
| `plugin/list/allow_list/` | 手写豁免清单；审查注入参数，生成 allow list card |
| `plugin/host_sibling/` | Host 旁路审查：入口表面、SDK 薄封装、provider 配置等价性、kernel 代码分层 |
| `services/` | App、Ingress、Worker、Queue 与 Store 架构卡 |
| `process/` | Definition、Runtime、Journal、Lifecycle、State 与 Handle 架构卡 |
| `thred/` | Task Definition、Executor 与 Resource Binding 架构卡 |
| `serve_generate/` | Serve 相关生成（预留） |
| `session_generate/` | Session 相关生成（预留） |
| `third_party_generate.py` | 第三方相关生成（预留） |

## 调用关系

```text
plugin_generate.py (Host)
  → 扫描仓库顶层目录（跳过缓存、点目录、``*-main`` 第三方树），划分 deny / allow family
  → 审查：deny_check → allow_check → host_sibling/*_check
  → 生成：allow_list_generate → deny_list_generate
  → --check：清单过期或 error 级违规则失败
  → 默认：写出 list card
```

## 架构卡

三层脚本各自写出同一套词汇和结构树，再补本层要求。它们不检查代码。

```text
python tools/external_tools/ci_tools/generate/services/services_generate.py
python tools/external_tools/ci_tools/generate/process/process_generate.py
python tools/external_tools/ci_tools/generate/thred/thred_generate.py
```

| 词 | 含义 |
| --- | --- |
| Agent | Service 与 Resources 的最终装配结果 |
| Service | 唯一部署边界；接收 Activation 并运行 Process |
| Process | 从 Journal 重放的 durable function |
| Task Function | 有稳定名称、版本和资源边界的副作用函数 |
| Resources | 容器资源与模型资源的统一容量池 |

```text
Agent
├── Service
│   ├── Ingress / Worker / Queue / Store
│   └── Process Runtime × N
│       └── Task Function × N
└── Resources
    ├── Container Resources
    └── Model Resources
```

## 设计思想

将审查与生成分离：检查项只追加违规，生成项只写清单；手写 allow list，deny list 由发现结果减去豁免路径自动得出。架构卡只写分层含义，代码合同留在 `plugin`。
