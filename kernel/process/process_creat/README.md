# process_creat

English | [中文](README.cn.md)

This directory finds the capability to start and packs it into one activation. Opening the resource record is [`reconcile.py`](../reconcile.py). This directory does not decide whether sharing is allowed, and it does not stop or reclaim.

## Contract

`instances.py` resolves one capability name, such as `model.openai_chat_model`, to one `CapabilityDefinition`: plugin paths, entrypoint `load`, and the resource requirements the profile stated. One capability has one entry. This directory does not guess missing requirements.

`activation.py` packs that definition, the resource grants, the pid, the room, host policy, thread policy, and settings into a `ProcessActivation`. The pid must be a positive operating-system process id. If the grants do not match the needs, start is refused here.

## Known Limitations and Deferred Work

- **Lookup is one name to one plugin entry** — there is no second entrypoint selector on the activation.
