# context_limits

English | [中文](README.cn.md)

Default context windows and recovery when a provider error names a smaller window or an output cap. The output cap here is inside the model context. It is not the interface request's `max_tokens`.

## Contract

`context_limits.py` is loaded by file. It does not import another module in the repository.

| Function | Result |
|---|---|
| `resolve_default_context_length` | Window for a model name, matched by the longest substring in `DEFAULT_CONTEXT_LENGTHS`. Unknown names use `256000`. |
| `parse_context_limit_from_error` | Reads a context length from an error string. |
| `recover_missing_context_length` | Fills a request that has no context length. |
| `recover_lower_context_from_error` | Lowers the window from the error text. |
| `get_next_context_probe_tier` / `recover_context_probe_tier` | Next smaller tier in `256000, 128000, 64000, 32000, 16000, 8000`. |
| `recover_output_token_cap` | Lowers the output cap when the error is an output-cap error. |
| `recover_request` | Tries the recoveries above and returns a new request dict, or `None` when nothing applies. |

[`kernel/calculate`](../../../../../kernel/calculate/README.md) calls `resolve_default_context_length` for `Pressure.context_limit`. Window retry inside `call_api` calls `recover_request`.

## Model Experience

Indirectly, through `call_api`. A recovered request is a new provider call with a smaller window or output cap. The original messages stay the caller's.

## Known Limitations and Deferred Work

- **Substring match** — `resolve_default_context_length` picks the longest table key contained in the model name. A name that contains none of the keys gets the fallback `256000`.
- **`MINIMUM_CONTEXT_LENGTH` is not the probe floor** — the constant is `64000`. `get_next_context_probe_tier` still returns `32000`, `16000`, and `8000`.
