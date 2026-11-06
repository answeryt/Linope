# compose

[English](README.md) | 中文

写出组合层架构卡片。它不审查插件源码。代码规则留在 [`plugin`](../plugin/README.cn.md)。

## 契约

`compose_generate.py` 的 `PLUGIN_NAME` 是 `compose_architecture`。它写出 `architecture_card/list.json`、`.yaml`、`.toml` 和 `.md`。

卡片把 Task 记成记入日志的副作用：任务定义、执行器和资源绑定。

```text
python capability/tools/external_tools/ci_tools/generate/compose/compose_generate.py
```

## 已知限制与暂缓事项

- **卡片是用词** — 生成它并不检查一个组合实现。本仓库没有 `kernel/compose` 树。
