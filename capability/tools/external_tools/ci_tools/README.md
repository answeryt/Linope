# ci_tools

插件约定门禁。入口：

```text
python tools/external_tools/ci_tools/generate/plugin/plugin_generate.py --check
```

手写库存是 `generate/plugin/list/allow_list/allow_list_card`（`paths` / `inject` / `kernel_layers` / `sockets`）。deny list 由扫描结果减去豁免路径生成。代码规则在各 `*_check.py`。插座路径由 `lip_check` 审查，能力图拼装由 `assembly_check` / `descriptor_check` 审查。kernel 架构（Microservice / Process / Execution / Task / Loop / Event）写在 `generate/services`、`generate/process`、`generate/async`、`generate/compose`，不进代码检查。
