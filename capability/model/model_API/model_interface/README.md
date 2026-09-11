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

## 与 Kernel 持久执行的边界

模型请求属于有外部副作用的 Task Function，不能直接写在可重放 Process Function
中。`model_interface` 继续保持 Provider SDK 薄封装；重试、资源 lease、结果记录
和 Replay 由 `kernel/compose/executor` 与 `kernel/process/journal` 负责。

```text
Process Function
  → ctx.run(model_task, input)
  → Task Executor
  → model_interface.call_api(...)
  → Journal 保存 output / error
  → Process Replay 直接读取历史结果
```

迁移状态：

- [x] 保持 Provider Interface 为无 Journal、无重试的薄 SDK 边界；
- [x] Kernel 已提供 `@task`、Task Executor 和结果/错误 Replay；
- [x] Kernel 已提供模型并发与配额可使用的 Resource lease 接口；
- [ ] 在上层 Model 实现中将各 Provider 调用注册为稳定命名、版本化的 Task；
- [ ] 为 Provider 请求传递稳定幂等键并记录 token/配额指标。
