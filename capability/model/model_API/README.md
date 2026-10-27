# model_API/ — SDK call and request recovery

English | [中文](README.cn.md)

Between the provider card and the third-party SDK. Parameter names that belong to one interface stay in that interface file. Rough estimates in this family are not written into the request as `max_tokens`.

| Directory | Role |
|---|---|
| [`model_interface/`](model_interface/README.md) | `call_api`, message formatting, and response parsing |
| [`model_paramaters/`](model_paramaters/README.md) | Rough token estimates and context-limit recovery |
