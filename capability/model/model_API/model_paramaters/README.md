# model_paramaters/ — estimates and context recovery

English | [中文](README.cn.md)

Rough token estimates and context-limit handling. These modules are loaded by file. They are not replaceable plugins, and they do not import each other.

Parameter translation (`max_tokens` renaming, `stream_options`, and so on) is written in the matching [`model_interface`](../model_interface/README.md) `call_api`. It does not pass through this directory.

| Directory | Role |
|---|---|
| [`tokens/`](tokens/README.md) | Rough estimates for text, images, messages, and tool schemas |
| [`context_limits/`](context_limits/README.md) | Default model windows and recovery from a provider error |

The maximum output length in `context_limits` is the output cap inside the model context. It is not the interface request's `max_tokens`.
