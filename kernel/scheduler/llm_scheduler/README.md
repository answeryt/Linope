# llm_scheduler compatibility

English | [中文](README.cn.md)

This directory only keeps the old import path for compatibility. The model
scheduler is [`../model_scheduler`](../model_scheduler/README.md); the model
is not a process and does not enter the queue through `settings.slot`.

Use `model use` to install a card and `model run` to execute a request. Tools
remain capability processes.

[`kernel/scheduler`](../README.md) still hands one request to the process that holds a resource. It does not choose who asks the model next in this window.
