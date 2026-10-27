# generate/ — 清单卡片与架构卡片

[English](README.md) | 中文

插件审查写出允许清单和拒绝清单。层脚本写出架构卡片，不检查源码。

| 目录 | 职责 |
|---|---|
| [`plugin/`](plugin/README.cn.md) | 发现家族，运行 `*_check.py`，写出允许和拒绝卡片 |
| [`services/`](services/README.cn.md) | 服务层架构卡片 |
| [`process/`](process/README.cn.md) | 进程层架构卡片 |
| [`compose/`](compose/README.cn.md) | 组合层架构卡片 |

审查和生成是分开的。检查只追加违规。生成器只写清单或卡片。允许清单是手写的。拒绝清单是发现结果减去豁免路径。

```text
python capability/tools/external_tools/ci_tools/generate/plugin/plugin_generate.py --check
python capability/tools/external_tools/ci_tools/generate/services/services_generate.py
python capability/tools/external_tools/ci_tools/generate/process/process_generate.py
python capability/tools/external_tools/ci_tools/generate/compose/compose_generate.py
```

## 已知限制与暂缓事项

- **架构卡片不检查这棵树** — `services`、`process` 和 `compose` 写的是用词。与 `kernel/` 不符时，那些脚本看不见。
- **标记行走不是这个布局** — `find_repo_root` 返回第一个同时具有 `.gates/isolation-allowlist.json`、顶层 `model/` 和 `tools/`，以及紧挨 `capability/` 的 `kernel/compose/capability` 的祖先。本仓库把模型和工具放在 `capability/` 下。没有祖先匹配时，函数返回 `plugin_generate.py` 之上的六层父目录，按当前路径那就是仓库根。
