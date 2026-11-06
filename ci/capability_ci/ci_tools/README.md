# ci_tools/ — plugin-convention gate

English | [中文](README.cn.md)

Review plugin shape and write architecture cards. The check entry is [`generate/plugin`](generate/plugin/README.md).

| Directory | Role |
|---|---|
| [`generate/`](generate/README.md) | List cards and the three architecture cards |

```text
python capability/tools/external_tools/ci_tools/generate/plugin/plugin_generate.py --check
```

The hand-written inventory is `generate/plugin/list/allow_list/allow_list_card` (`paths`, `inject`, `kernel_layers`, `sockets`). The deny list is the scan result minus exempt paths. Code rules live in each `*_check.py`.
