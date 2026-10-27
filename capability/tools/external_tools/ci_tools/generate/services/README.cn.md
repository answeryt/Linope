# services

[English](README.md) | 中文

写出服务层架构卡片。它不审查插件源码。代码规则留在 [`plugin`](../plugin/README.cn.md)。

## 契约

`services_generate.py` 的 `PLUGIN_NAME` 是 `services_architecture`。它写出 `architecture_card/list.json`、`.yaml`、`.toml` 和 `.md`。

卡片记录：Agent 是 Service 加上 Resources。Service 是部署边界。它接受一份 Activation 并运行 Processes。卡片还点名 Ingress、RunQueue 和 ProcessStore。

```text
python capability/tools/external_tools/ci_tools/generate/services/services_generate.py
```

## 已知限制与暂缓事项

- **卡片是用词** — 生成它并不检查 `kernel/` 是否与卡片相符。
