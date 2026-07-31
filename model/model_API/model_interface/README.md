# model_interface

Provider 原生 SDK 的薄封装层，只负责发起模型 API 请求。

## 定位

- 介于 `_xxx/_model.py` 与第三方 SDK 之间
- 不包含 `Msg` 格式化、响应解析、重试、工具转换等业务逻辑
- 每个文件对应一种 Provider API，暴露统一的 `call_api` 函数

## 文件说明

| 文件 | SDK | API |
| --- | --- | --- |
| `openai_chat.py` | `openai.AsyncClient` | `chat.completions.create` |
| `openai_response.py` | `openai.AsyncClient` | `responses.create` |
| `anthropic.py` | `anthropic.AsyncAnthropic` | `messages.create` |
| `gemini.py` | `google.genai.Client` | `generate_content`, `generate_content_stream` |

## 调用关系

```text
ChatModelBase / _xxx/_model.py
  → 组装 credential、参数、格式化后的消息
  → model_client.call_api(...)
  → Provider SDK
  → 原始 API 响应
```

## 设计思想

将接口与接口的相关参数分离，提供高定制化能力。
