# compose

English | [中文](README.cn.md)

Writes the compose-layer architecture card. It does not review plugin source. Code rules stay in [`plugin`](../plugin/README.md).

## Contract

`compose_generate.py` is `PLUGIN_NAME` `compose_architecture`. It writes `architecture_card/list.json`, `.yaml`, `.toml`, and `.md`.

The card records a Task as the journaled side effect: task definition, executor, and resource binding.

```text
python capability/tools/external_tools/ci_tools/generate/compose/compose_generate.py
```

## Known Limitations and Deferred Work

- **The card is vocabulary** — generating it does not check a compose implementation. This repository has no `kernel/compose` tree.
