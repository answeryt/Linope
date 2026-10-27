# model_provider

[English](README.md) | 中文

面向使用者的模型接口配置模板。每个提供者的卡片是一份 JSON。

## 位置

- 用户配置层。它描述使用哪个提供者、连接哪个接口、传递哪些参数。
- 每个提供者有一份 JSON 卡片。schema 见下文。
- 没有 SDK 调用，也没有参数转换。请求由对应的 `model_interface.call_api` 发送。

每个子目录是一个提供者。面向使用者的卡片是该目录里的 `<provider>.json`。运行时配置跟随对应 `*_plugin.py` 里的 `CARD_CONFIG`。

## 配置清单

每个目录是一个提供者插件。它的 JSON 卡片与插件里的 `CARD_CONFIG` 对应。下面的 schema 是共享字段表。

| 目录 | provider | interface | SDK API |
| --- | --- | --- | --- |
| [`openai_chat_model/`](openai_chat_model/README.cn.md) | `openai` | `openai_chat` | `chat.completions.create` |
| [`openai_response_model/`](openai_response_model/README.cn.md) | `openai` | `openai_response` | `responses.create` |
| [`anthropic_model/`](anthropic_model/README.cn.md) | `anthropic` | `anthropic` | `messages.create` |
| [`gemini_model/`](gemini_model/README.cn.md) | `gemini` | `gemini` | `generate_content` |

## 配置 schema

### 顶层字段

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `provider` | string | 提供者 id，例如 `openai`、`anthropic` 或 `gemini` |
| `interface` | string | 接口模块名，对应 `model_interface/` 下的实现文件 |
| `model` | string | 模型 id。换成实际使用的模型名 |
| `api_key_env` | string | 持有 API 密钥的环境变量名 |
| `organization_env` | string | （仅 OpenAI）组织环境变量名 |
| `base_url` | string | API 端点，包括代理或私有部署 |
| `stream` | bool / `"UNSET"` | 是否启用流式 |
| `parameters` | object | 模型生成参数。见下表 |
| `client_kwargs` | object | 原样传给 SDK 客户端构造函数的额外参数 |
| `generate_kwargs` | object | 原样传给 API 请求的额外顶层字段 |
| `extra_body` | object | 写到请求体 `extra_body` 上的额外字段 |

### parameters 字段

提供者支持的子集不同。共享字段是：

| 字段 | 含义 |
| --- | --- |
| `max_tokens` | 生成 token 的最大数量 |
| `temperature` | 采样温度 |
| `top_p` | 核采样概率 |
| `tools` | 工具定义列表 |
| `tool_choice` | 工具选择策略 |

OpenAI 家族还支持：

| 字段 | 含义 | 适用于 |
| --- | --- | --- |
| `thinking_enable` | 是否启用推理模式 | Chat / Response |
| `reasoning_effort` | 推理力度（例如 `low` / `medium` / `high`） | Chat / Response |
| `parallel_tool_calls` | 是否允许并行工具调用 | Chat / Response |
| `voice` | 启用多模态音频时的输出声音 | 仅 Chat |

### UNSET

模板里没有配置的字段使用 `UNSET`。它的意思是「不要设置；使用运行时或 SDK 默认值」。上层应把 `UNSET` 当作 `None`，不要把它写入最终请求。

## 格式示例

示例是 OpenAI Chat：

### JSON

```json
{
  "provider": "openai",
  "interface": "openai_chat",
  "model": "gpt-4o",
  "api_key_env": "OPENAI_API_KEY",
  "stream": false,
  "parameters": {
    "max_tokens": 4096,
    "temperature": 0.7
  },
  "client_kwargs": {},
  "generate_kwargs": {},
  "extra_body": {}
}
```

活的默认值是每个插件 README 里的 `CARD_CONFIG`。上面的示例展示共享字段。

## 已知限制与暂缓事项

- **画像和调用读的是两份副本** — `capability_profile` 使用插件里的 `CARD_CONFIG`。`call_model` 只读 `<card_id>.json`。两者漂移时，`process start` 声明的是一份，`load` 发送的是另一份。
