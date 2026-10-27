# model_interface

[English](README.md) | 中文

提供者原生的 SDK 包装。每个文件暴露 `call_api`，以及该接口的消息格式化和响应解析。

## 位置

- 在提供者卡片和第三方 SDK 之间
- 把内部消息块变成该接口的 SDK 字段，解析响应，并在恢复上下文窗口或输出上限时重试
- 不转换工具 schema（`convert_tools`）
- 叶子模块不得导入仓库里的其他模块。SDK 只在 `call_api` 内部导入
- `recover_request` 按文件路径加载，不是包导入。粗略 token 估计不用于构造请求

## 文件

| 文件 | SDK | API |
| --- | --- | --- |
| `openai_chat.py` | `openai.AsyncClient` | `chat.completions.create` |
| `openai_response.py` | `openai.AsyncClient` | `responses.create` |
| `anthropic.py` | `anthropic.AsyncAnthropic` | `messages.create` |
| `gemini.py` | `google.genai.Client` | `generate_content`、`generate_content_stream` |

## 调用路径

```text
model_provider card
  → call_model builds the payload
  → model_interface.format_messages
  → model_interface.call_api (includes window-recovery retry)
  → Provider SDK
  → model_interface.parse_response / parse_stream_chunk
```

`None` / `"UNSET"` 被跳过，不覆盖 SDK 默认值。属于某一个接口的字段改名（例如 `max_tokens` → `max_completion_tokens`）写在该文件的私有函数里。窗口级重试是本层的 `call_api` 调用 `recover_request`。日志级的 Task 重试仍属于内核。

一个模型步骤可以收到完整的 `messages`，加上 `tools` 和 `tool_choice`。一次工具调用保留它的 `id`。工具结果带着该 `id` 回到同一步。是否再次调用模型，由代理任务的下一步决定，不由本层的循环决定。

## 与进程的边界

窗口和输出上限的恢复留在 `call_api` 里，它调用 [`context_limits`](../model_paramaters/context_limits/README.cn.md) 的 `recover_request`。进程记录、租约和回合日志属于 [`kernel/process`](../../../../kernel/process/README.cn.md) 和 [`kernel/trace`](../../../../kernel/trace/README.cn.md)。本层不写账本。

## 已知限制与暂缓事项

- **没有工具 schema 转换** — 不提供 `convert_tools`。调用方按该接口已经接受的形状传入工具声明。
- **SDK 导入在 `call_api` 内部** — 缺少提供者包时，失败发生在调用时，不是叶子模块导入时。
