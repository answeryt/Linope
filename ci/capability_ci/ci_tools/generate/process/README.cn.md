# process

[English](README.md) | 中文

写出进程层架构卡片。它不审查插件源码。代码规则留在 [`plugin`](../plugin/README.cn.md)。正在运行的进程记录在 [`kernel/process`](../../../../../../kernel/process/README.cn.md)。

## 契约

`process_generate.py` 的 `PLUGIN_NAME` 是 `process_architecture`。它写出 `architecture_card/list.json`、`.yaml`、`.toml` 和 `.md`。

卡片把 Process 记成可持久重放的函数：定义、运行时、日志、生存期、状态和句柄。

```text
python capability/tools/external_tools/ci_tools/generate/process/process_generate.py
```

## 已知限制与暂缓事项

- **卡片是用词** — 生成它并不检查 `kernel/process` 是否与卡片相符。
