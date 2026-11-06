# ci_tools/ — 插件约定门

[English](README.md) | 中文

审查插件形状并写出架构卡片。检查入口是 [`generate/plugin`](generate/plugin/README.cn.md)。

| 目录 | 职责 |
|---|---|
| [`generate/`](generate/README.cn.md) | 清单卡片和三张架构卡片 |

```text
python capability/tools/external_tools/ci_tools/generate/plugin/plugin_generate.py --check
```

手写的清单是 `generate/plugin/list/allow_list/allow_list_card`（`paths`、`inject`、`kernel_layers`、`sockets`）。拒绝清单是扫描结果减去豁免路径。代码规则写在每个 `*_check.py` 里。
