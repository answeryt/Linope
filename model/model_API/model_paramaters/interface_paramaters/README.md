# model_paramaters

模型参数、上下文和 Token 处理的模块化插件层。

## 定位

- `interface_paramaters` 介于 `model_provider` 配置与 `model_interface.call_api` 之间
- `interface_paramaters` 中每个文件对应一种 API 请求参数
- `context_paramaters` 提供相互独立的上下文长度解析插件
- `token_paramaters` 提供相互独立的 Token 估算插件
- `fallback_handlers` 提供静态回退和错误容错插件
- 不包含 SDK 调用、消息格式化、响应解析等逻辑
- 可按需组合，不同 Provider / 接口只引入所需插件

## 设计思想

将接口与接口参数分离，提供高定制化能力：

- **单一职责**：一个文件只处理一种参数
- **按需装配**：上层按 Provider 能力选择要调用的 `apply_*`
- **无副作用约定**：所有函数原地写入 `request_kwargs`，不返回值
- **显式跳过**：参数为 `None` 或未满足条件时不写入，避免覆盖 SDK 默认值

## 统一约定

每个插件遵循相同签名模式：

```python
def apply_<param>(
    request_kwargs: dict,
    ...  # parameters 对象、格式化后的工具、stream 标志等
) -> None:
    ...
```

| 输入来源 | 说明 |
| --- | --- |
| `parameters` | 来自 `model_provider` 配置中的 `parameters` 对象（通过 `getattr` 读取） |
| `formatted_tools` / `formatted_tool_choice` | 由上层完成 schema 转换后的工具定义 |
| `stream` | 是否开启流式响应 |
| `generate_kwargs` / `extra_body` | 配置文件中透传的扩展字段 |

## 文件说明

| 文件 | 函数 | 写入字段 | 触发条件 |
| --- | --- | --- | --- |
| `temperature.py` | `apply_temperature` | `temperature` | `parameters.temperature` 不为 `None` |
| `top_p.py` | `apply_top_p` | `top_p` | `parameters.top_p` 不为 `None` |
| `max_completion_tokens.py` | `apply_max_completion_tokens` | Chat: `max_completion_tokens`；Responses/Gemini: `max_output_tokens` | `parameters.max_tokens` 不为 `None` |
| `reasoning_effort.py` | `apply_reasoning_effort` | `reasoning_effort` | `thinking_enable` 为真且 `reasoning_effort` 不为 `None` |
| `parallel_tool_calls.py` | `apply_parallel_tool_calls` | `parallel_tool_calls` | 仅当 `parallel_tool_calls` 为 `False` 时写入（默认为 `True`） |
| `tools.py` | `apply_tools` | `tools` | `formatted_tools` 不为 `None` |
| `tool_choice.py` | `apply_tool_choice` | `tool_choice` | `formatted_tool_choice` 不为 `None` |
| `stream_options.py` | `apply_stream_options` | `stream_options` | `stream` 为 `True` 时写入 `{"include_usage": True}` |
| `modalities.py` | `apply_modalities` | `modalities` | `parameters.voice` 不为 `None` 时设为 `["text", "audio"]` |
| `audio.py` | `apply_audio` | `audio` | `parameters.voice` 不为 `None` 时写入 `{voice, format: "pcm16"}` |
| `generate_kwargs.py` | `apply_generate_kwargs` | （合并至根级） | 将 `generate_kwargs` 整体 `update` 进 `request_kwargs` |
| `extra_body.py` | `apply_extra_body` | `extra_body` | 合并配置中的 `extra_body`，已有值不会被覆盖 |

## 调用关系

```text
model_provider 配置
  → 解析 parameters / generate_kwargs / extra_body
  → 按需调用 apply_* 插件，组装 request_kwargs
  → model_interface.call_api(..., request_kwargs=request_kwargs)
  → Provider SDK
```

## 扩展新参数

新增一种 API 参数时，在本目录添加独立文件即可：

1. 命名文件为参数语义（如 `frequency_penalty.py`）
2. 实现 `apply_<param>(request_kwargs, ...)`，仅在条件满足时写入
3. 在上层装配处按需 import 并调用

无需修改 `model_interface` 或其他已有插件。

## 上下文与 Token 插件

新增目录中的插件均不负责模块装配、Provider 网络连接或调用顺序：

- `context_paramaters/`：解析显式配置、Endpoint 元数据和本地模型服务响应
- `token_paramaters/`：分别估算文本、消息、图片和工具 Schema Token
- `fallback_handlers/`：处理模型目录回退、Codex OAuth 回退、错误解析和陈旧值保护

插件之间不进行项目内 import。需要组合多个插件时，由未来的连接层显式传入
数据或函数，例如 `message_tokens.py` 通过参数接收文本和图片估算函数。
