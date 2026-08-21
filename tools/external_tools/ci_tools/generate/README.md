# generate

Generate 的 CI：审查仓库插件约定，并生成 allow / deny 清单。

## 定位

- 介于仓库源码与 CI 门禁之间
- 审查（`*_check.py`）：检查 facade、隔离、入口表面、SDK 边界、provider 配置
- 生成（`*_generate.py`）：写出 allow / deny list card（json / yaml / toml / md）
- Host 只负责发现插件并共享 context，不静态导入各检查项

## 文件说明

| 路径 | 职责 |
| --- | --- |
| `plugin/plugin_generate.py` | Host：发现 `*_check.py` / `*_generate.py`，组装 context，执行审查与生成 |
| `plugin/list/deny_list/` | 审查 plugin family 的原子性与隔离，生成 deny list card |
| `plugin/list/allow_list/` | 手写豁免清单；审查注入参数，生成 allow list card |
| `plugin/host_sibling/` | Host 旁路审查：入口表面、SDK 薄封装、provider 配置等价性 |
| `serve_generate/` | Serve 相关生成（预留） |
| `session_generate/` | Session 相关生成（预留） |
| `third_party_generate.py` | 第三方相关生成（预留） |

## 调用关系

```text
plugin_generate.py (Host)
  → 扫描 model / context / prompt / tools / kernel，划分 deny / allow family
  → 审查：deny_check → allow_check → host_sibling/*_check
  → 生成：allow_list_generate → deny_list_generate
  → --check：清单过期或 error 级违规则失败
  → 默认：写出 list card
```

## 设计思想

将审查与生成分离：检查项只追加违规，生成项只写清单；手写 allow list，deny list 由发现结果减去豁免路径自动得出。
