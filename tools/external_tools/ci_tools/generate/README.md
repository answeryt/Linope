# generate

Generate 的 CI：审查仓库插件约定，并生成 allow / deny 清单；另外四层脚本只写 kernel 架构，不写代码合同。

## 定位

- 介于仓库源码与 CI 门禁之间
- 审查（`plugin/*_check.py`）：检查 facade、隔离、入口表面、SDK 边界、provider 配置、kernel 代码分层
- 生成（`plugin/*_generate.py`）：写出 allow / deny list card（json / yaml / toml / md）
- 架构（`services` / `process` / `async` / `thred`）：写出该层的词汇、结构树和架构要求；代码形状仍由 `plugin` 审查
- Host 只负责发现插件并共享 context，不静态导入各检查项

## 文件说明

| 路径 | 职责 |
| --- | --- |
| `plugin/plugin_generate.py` | Host：发现 `*_check.py` / `*_generate.py`，组装 context，执行审查与生成 |
| `plugin/list/deny_list/` | 审查 plugin family 的原子性与隔离，生成 deny list card |
| `plugin/list/allow_list/` | 手写豁免清单；审查注入参数，生成 allow list card |
| `plugin/host_sibling/` | Host 旁路审查：入口表面、SDK 薄封装、provider 配置等价性、kernel 代码分层 |
| `services/` | Microservice / Task 架构卡 |
| `process/` | Process / State / Resources / Memory 架构卡 |
| `async/` | Scheduler / Execution / Loop / Event 架构卡 |
| `thred/` | Thread 作为等待上下文的架构卡（结构图上不是 Work Unit） |
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

四层脚本各自写出同一套词汇和结构树，再补本层要求。它们不检查代码。

```text
python tools/external_tools/ci_tools/generate/services/services_generate.py
python tools/external_tools/ci_tools/generate/process/process_generate.py
python tools/external_tools/ci_tools/generate/async/async_generate.py
python tools/external_tools/ci_tools/generate/thred/thred_generate.py
```

| 词 | 含义 |
| --- | --- |
| Microservice | 部署边界。微服务指 Agent 本体 |
| Process | 具有独立目标、状态、资源和生命周期的 Agent Work Unit |
| Execution | Process 内部可被 Scheduler 独立调度的最小执行单元 |
| Task | 用户/Agent 想要完成的目标 |
| Loop | Execution 使用的控制机制 |
| Event | Runtime 中发生的状态变化 |

```text
Microservice
  └── Process
        ├── State
        ├── Resources ── Scheduler ── Execution × N
        └── Memory                      ├── Agent Loop
                                        ├── Tool Loop
                                        └── Event Loop
```

## 设计思想

将审查与生成分离：检查项只追加违规，生成项只写清单；手写 allow list，deny list 由发现结果减去豁免路径自动得出。架构卡只写分层含义，代码合同留在 `plugin`。
