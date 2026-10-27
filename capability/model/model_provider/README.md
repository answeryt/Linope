# model_provider

English | [中文](README.cn.md)

Configuration templates for the user-facing model interfaces. Each provider card is one JSON file.

## Place

- The user configuration layer. It describes which provider to use, which interface to connect, and which parameters to pass.
- Each provider has one JSON card. The schema is below.
- No SDK calls and no parameter conversion. The request is sent by the matching `model_interface.call_api`.

Each subdirectory is one provider. The user-facing card is `<provider>.json` in that directory. Runtime configuration follows `CARD_CONFIG` in the matching `*_plugin.py`.

## Configuration list

Each directory is one provider plugin. Its JSON card matches `CARD_CONFIG` in the plugin. The schema below is the shared field list.

| Directory | provider | interface | SDK API |
| --- | --- | --- | --- |
| [`openai_chat_model/`](openai_chat_model/README.md) | `openai` | `openai_chat` | `chat.completions.create` |
| [`openai_response_model/`](openai_response_model/README.md) | `openai` | `openai_response` | `responses.create` |
| [`anthropic_model/`](anthropic_model/README.md) | `anthropic` | `anthropic` | `messages.create` |
| [`gemini_model/`](gemini_model/README.md) | `gemini` | `gemini` | `generate_content` |

## Configuration schema

### Top-level fields

| Field | Type | Meaning |
| --- | --- | --- |
| `provider` | string | Provider id, such as `openai`, `anthropic`, or `gemini` |
| `interface` | string | Interface module name, matching an implementation file under `model_interface/` |
| `model` | string | Model id. Replace it with the model name actually used |
| `api_key_env` | string | Name of the environment variable that holds the API key |
| `organization_env` | string | (OpenAI only) name of the organization environment variable |
| `base_url` | string | API endpoint, including a proxy or a private deployment |
| `stream` | bool / `"UNSET"` | Whether streaming is enabled |
| `parameters` | object | Model generation parameters. See the table below |
| `client_kwargs` | object | Extra arguments passed through to the SDK client constructor |
| `generate_kwargs` | object | Extra top-level fields passed through to the API request |
| `extra_body` | object | Extra fields written to `extra_body` on the request body |

### parameters fields

Providers support different subsets. The shared fields are:

| Field | Meaning |
| --- | --- |
| `max_tokens` | Maximum number of generated tokens |
| `temperature` | Sampling temperature |
| `top_p` | Nucleus sampling probability |
| `tools` | Tool definition list |
| `tool_choice` | Tool selection policy |

The OpenAI family also supports:

| Field | Meaning | Applies to |
| --- | --- | --- |
| `thinking_enable` | Whether reasoning mode is enabled | Chat / Response |
| `reasoning_effort` | Reasoning effort (for example `low` / `medium` / `high`) | Chat / Response |
| `parallel_tool_calls` | Whether parallel tool calls are allowed | Chat / Response |
| `voice` | Voice for audio output, when multimodal audio is enabled | Chat only |

### UNSET

A field that is not configured in the template uses `UNSET`. It means "do not set this; use the runtime or SDK default." A higher layer should treat `UNSET` as `None` and not write it into the final request.

## Format example

OpenAI Chat is the example:

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

Live defaults are the `CARD_CONFIG` in each plugin README. The example above shows the shared fields.

## Known Limitations and Deferred Work

- **Profile and call read different copies** — `capability_profile` uses `CARD_CONFIG` in the plugin. `call_model` reads `<card_id>.json` only. A drift between them is what `process start` declares versus what `load` sends.
