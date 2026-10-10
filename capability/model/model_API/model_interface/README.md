# model_interface

Provider 原生 SDK 封装层。每个文件暴露 `call_api`，以及本接口的消息格式化与响应解析。

## 定位

- 介于 provider card 与第三方 SDK 之间
- 负责把内部消息块翻成本接口 SDK 字段、解析响应、以及上下文窗口 / 输出上限恢复重试
- 不负责工具 schema 转换（`convert_tools`）
- 叶模块不得 import 仓库内其它模块；SDK 只在 `call_api` 内 import
- `recover_request` 按文件路径加载，不作为包互导；token 粗估不参与组请求

## 文件说明

| 文件 | SDK | API |
| --- | --- | --- |
| `openai_chat.py` | `openai.AsyncClient` | `chat.completions.create` |
| `openai_response.py` | `openai.AsyncClient` | `responses.create` |
| `anthropic.py` | `anthropic.AsyncAnthropic` | `messages.create` |
| `gemini.py` | `google.genai.Client` | `generate_content`, `generate_content_stream` |

## 调用关系

```text
model_provider card
  → call_model 拼 payload
  → model_interface.format_messages
  → model_interface.call_api（含窗口恢复重试）
  → Provider SDK
  → model_interface.parse_response / parse_stream_chunk
```

`None` / `"UNSET"` 跳过，不覆盖 SDK 默认值。各接口自己的字段改名（如 `max_tokens` → `max_completion_tokens`）写在该文件的私有函数里。窗口级重试由本层 `call_api` 调用 `recover_request`；Journal 级 Task 重试仍归 kernel。

## 与 Kernel 持久执行的边界

模型请求属于有外部副作用的 Task Function，不能直接写在可重放 Process Function
中。窗口/输出上限恢复重试写在 `call_api` 内。Journal 级 Task 重试、资源 lease、结果记录和 Replay 仍由 `kernel/compose/executor` 与 `kernel/process/journal` 负责。

```text
Process Function
  → ctx.run(model_task, input)
  → Task Executor
  → model_interface.call_api(payload)
  → Journal 保存 output / error
  → Process Replay 直接读取历史结果
```
