# fallback_handlers

上下文和输出 Token 的独立回退、容错插件。

- `context_defaults.py`：模型静态上下文目录及未知模型 256K 兜底
- `codex_context_defaults.py`：Codex OAuth 的独立上下文回退
- `context_probe_tiers.py`：向下探测的候选档位
- `context_error_recovery.py`：从 Provider 错误中提取真实上下文上限
- `output_token_recovery.py`：识别输出上限错误并提取可用输出 Token
- `stale_context_guard.py`：拒绝已知低报的缓存或元数据

这些插件不负责重试、压缩、缓存删除或请求调度；相关动作由未来连接层决定。

需要注意的是，该文件中的最大输出长度是模型上下文的最大输出长度，与接口中最大的请求长度不一样。为什么不一样呢？因为模型在处理长上下文的时候往往会“遗忘”导致能力变差，但这时候可能没有到达请求最大值。
