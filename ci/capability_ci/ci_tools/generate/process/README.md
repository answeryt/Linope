# process

English | [中文](README.cn.md)

Writes the process-layer architecture card. It does not review plugin source. Code rules stay in [`plugin`](../plugin/README.md). The running process record is [`kernel/process`](../../../../../../kernel/process/README.md).

## Contract

`process_generate.py` is `PLUGIN_NAME` `process_architecture`. It writes `architecture_card/list.json`, `.yaml`, `.toml`, and `.md`.

The card records a Process as the durable replayed function: definition, runtime, journal, lifecycle, state, and handle.

```text
python capability/tools/external_tools/ci_tools/generate/process/process_generate.py
```

## Known Limitations and Deferred Work

- **The card is vocabulary** — generating it does not check that `kernel/process` matches the card.
