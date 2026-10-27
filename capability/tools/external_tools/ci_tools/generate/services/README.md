# services

English | [中文](README.cn.md)

Writes the services-layer architecture card. It does not review plugin source. Code rules stay in [`plugin`](../plugin/README.md).

## Contract

`services_generate.py` is `PLUGIN_NAME` `services_architecture`. It writes `architecture_card/list.json`, `.yaml`, `.toml`, and `.md`.

The card records: an Agent is a Service plus Resources. A Service is the deployment boundary. It accepts an Activation and runs Processes. The card also names Ingress, RunQueue, and ProcessStore.

```text
python capability/tools/external_tools/ci_tools/generate/services/services_generate.py
```

## Known Limitations and Deferred Work

- **The card is vocabulary** — generating it does not check that `kernel/` matches the card.
