# model_API/ — SDK 调用与请求恢复

[English](README.md) | 中文

位于提供者卡片和第三方 SDK 之间。属于某一个接口的参数名留在该接口文件里。本家族里的粗略估计不会作为 `max_tokens` 写入请求。

| 目录 | 职责 |
|---|---|
| [`model_interface/`](model_interface/README.cn.md) | `call_api`、消息格式化和响应解析 |
| [`model_paramaters/`](model_paramaters/README.cn.md) | 粗略 token 估计和上下文上限恢复 |
