# model_interface

English | [中文](README.cn.md)

Provider-native SDK wrappers. Each file exposes `call_api`, plus message formatting and response parsing for that interface.

## Place

- Between the provider card and the third-party SDK
- Turns internal message blocks into this interface's SDK fields, parses the response, and retries when recovering a context window or an output cap
- Does not convert tool schemas (`convert_tools`)
- A leaf module must not import other modules in the repo. The SDK is imported only inside `call_api`
- `recover_request` is loaded by file path, not as a package import. Rough token estimates are not used to build the request

## Files

| File | SDK | API |
| --- | --- | --- |
| `openai_chat.py` | `openai.AsyncClient` | `chat.completions.create` |
| `openai_response.py` | `openai.AsyncClient` | `responses.create` |
| `anthropic.py` | `anthropic.AsyncAnthropic` | `messages.create` |
| `gemini.py` | `google.genai.Client` | `generate_content`, `generate_content_stream` |

## Call path

```text
model_provider card
  → call_model builds the payload
  → model_interface.format_messages
  → model_interface.call_api (includes window-recovery retry)
  → Provider SDK
  → model_interface.parse_response / parse_stream_chunk
```

`None` / `"UNSET"` is skipped and does not override an SDK default. Field renames that belong to one interface (for example `max_tokens` → `max_completion_tokens`) live in that file's private functions. Window-level retry is this layer's `call_api` calling `recover_request`. Journal-level Task retry still belongs to the kernel.

One model step can receive the full `messages`, plus `tools` and `tool_choice`. A tool call keeps its `id`. The tool result returns to the same step with that `id`. Whether to call the model again is decided by the next action of the agent task, not by a loop in this layer.

## Boundary with the process

Window and output-cap recovery stay inside `call_api`, which calls `recover_request` from [`context_limits`](../model_paramaters/context_limits/README.md). The process record, leases, and the turn journal belong to [`kernel/process`](../../../../kernel/process/README.md) and [`kernel/trace`](../../../../kernel/trace/README.md). This layer does not write the ledger.

## Known Limitations and Deferred Work

- **No tool-schema conversion** — `convert_tools` is not provided. The caller passes tool declarations in the shape that interface already accepts.
- **The SDK import is inside `call_api`** — a missing provider package fails at call time, not at import of the leaf module.
