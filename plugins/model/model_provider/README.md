# model_provider

面向用户的模型接口配置模板目录，提供开箱即用的 Provider 配置清单，支持 **YAML**、**JSON**、**TOML** 三种格式。

## 定位

- 用户配置层，描述「用哪个 Provider、连哪个接口、传哪些参数」
- 每种 Provider 提供等价的三种格式文件，Schema 完全一致，可按偏好任选其一
- 不包含 SDK 调用或参数转换逻辑，解析后交由 `model_paramaters` 与 `model_interface` 处理

每个子目录对应一种 Provider 配置模板，三种格式内容等价，仅序列化方式不同。

## 配置清单

| 目录 | provider | interface | 对应 SDK 接口 |
| --- | --- | --- | --- |
| `openai_chat_model/` | `openai` | `openai_chat` | `chat.completions.create` |
| `openai_response_model/` | `openai` | `openai_response` | `responses.create` |
| `anthropic_model/` | `anthropic` | `anthropic` | `messages.create` |
| `gemini_model/` | `gemini` | `gemini` | `generate_content` |

## 配置 Schema

### 顶层字段

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `provider` | string | Provider 标识，如 `openai`、`anthropic`、`gemini` |
| `interface` | string | 接口模块名，对应 `model_interface/` 下的实现文件 |
| `model` | string | 模型 ID，替换为实际使用的模型名 |
| `api_key_env` | string | 存放 API Key 的环境变量名 |
| `organization_env` | string | （OpenAI 专用）Organization 环境变量名 |
| `base_url` | string | API 端点地址，兼容代理或私有部署 |
| `stream` | bool / `"UNSET"` | 是否启用流式响应 |
| `parameters` | object | 模型生成参数，见下表 |
| `client_kwargs` | object | 透传给 SDK Client 构造函数的额外参数 |
| `generate_kwargs` | object | 透传给 API 请求的顶层扩展字段 |
| `extra_body` | object | 写入请求体 `extra_body` 的扩展字段 |

### parameters 字段

各 Provider 支持的参数子集不同，公共字段如下：

| 字段 | 说明 |
| --- | --- |
| `max_tokens` | 最大生成 token 数 |
| `temperature` | 采样温度 |
| `top_p` | 核采样概率 |
| `tools` | 工具定义列表 |
| `tool_choice` | 工具选择策略 |

OpenAI 系列额外支持：

| 字段 | 说明 | 适用 |
| --- | --- | --- |
| `thinking_enable` | 是否启用推理模式 | Chat / Response |
| `reasoning_effort` | 推理强度（如 `low` / `medium` / `high`） | Chat / Response |
| `parallel_tool_calls` | 是否允许并行工具调用 | Chat / Response |
| `voice` | 语音输出音色，启用多模态音频 | Chat 专用 |

### UNSET 约定

模板中未配置的字段统一使用 `UNSET` 占位，表示「不设置，使用运行时或 SDK 默认值」。上层解析时应将 `UNSET` 视为 `None`，不写入最终请求。

## 格式示例

以下三种写法语义相同，以 OpenAI Chat 为例：

### YAML

```yaml
provider: openai
interface: openai_chat
model: gpt-4o
api_key_env: OPENAI_API_KEY
organization_env: OPENAI_ORGANIZATION
base_url: https://api.openai.com/v1
stream: false

parameters:
  max_tokens: 4096
  temperature: 0.7
  top_p: UNSET
  thinking_enable: UNSET
  reasoning_effort: UNSET
  parallel_tool_calls: UNSET
  tools: UNSET
  tool_choice: UNSET
  voice: UNSET

client_kwargs: {}
generate_kwargs: {}
extra_body: {}
```

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

### TOML

```toml
provider = "openai"
interface = "openai_chat"
model = "gpt-4o"
api_key_env = "OPENAI_API_KEY"
stream = false

[parameters]
max_tokens = 4096
temperature = 0.7

[client_kwargs]
[generate_kwargs]
[extra_body]
```
