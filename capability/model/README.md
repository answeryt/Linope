# model/ — provider cards and SDK calls

English | [中文](README.cn.md)

This family turns a provider card into a process declaration and a provider SDK call. It does not walk a model turn. The turn is [`kernel/scheduler`](../../kernel/scheduler/README.md).

| Directory | Role |
|---|---|
| [`model_provider/`](model_provider/README.md) | One card and `capability_profile` per provider |
| [`model_API/`](model_API/README.md) | SDK wrappers, rough token estimates, and context-window recovery |
| [`model_message/`](model_message/README.md) | In-process content blocks |
| [`model_runtime/`](model_runtime/README.md) | Load a named card and assemble a streamed turn |
