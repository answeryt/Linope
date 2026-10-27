# context_limits

[English](README.md) | 中文

默认上下文窗口，以及提供者错误点名更小窗口或输出上限时的恢复。这里的输出上限在模型上下文内部。它不是接口请求的 `max_tokens`。

## 契约

`context_limits.py` 按文件加载。它不导入仓库里的其他模块。

| 函数 | 结果 |
|---|---|
| `resolve_default_context_length` | 模型名的窗口，按 `DEFAULT_CONTEXT_LENGTHS` 中最长的子串匹配。未知名字使用 `256000`。 |
| `parse_context_limit_from_error` | 从错误字符串读出一个上下文长度。 |
| `recover_missing_context_length` | 填上没有上下文长度的请求。 |
| `recover_lower_context_from_error` | 按错误文本降低窗口。 |
| `get_next_context_probe_tier` / `recover_context_probe_tier` | `256000, 128000, 64000, 32000, 16000, 8000` 中下一个更小的档。 |
| `recover_output_token_cap` | 错误是输出上限错误时，降低输出上限。 |
| `recover_request` | 依次尝试上面的恢复，返回新的请求字典；没有适用项时返回 `None`。 |

[`kernel/calculate`](../../../../../kernel/calculate/README.cn.md) 为 `Pressure.context_limit` 调用 `resolve_default_context_length`。`call_api` 内部的窗口重试调用 `recover_request`。

## 模型体验

间接地，通过 `call_api`。恢复后的请求是一次窗口或输出上限更小的新提供者调用。原来的消息仍是调用方的。

## 已知限制与暂缓事项

- **子串匹配** — `resolve_default_context_length` 选取模型名中包含的最长表键。一个名字不含任何键时，得到回退值 `256000`。
- **`MINIMUM_CONTEXT_LENGTH` 不是探测下限** — 该常数是 `64000`。`get_next_context_probe_tier` 仍会返回 `32000`、`16000` 和 `8000`。
