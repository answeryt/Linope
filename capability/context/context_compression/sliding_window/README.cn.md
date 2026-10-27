# 滑动窗口压缩的原子函数

[English](README.md) | 中文

本目录是一组没有门面的原子函数。`load` 通过 [`load_in_directory`](../../README.cn.md) 选出其中一个。宿主也可以导入它们并组合。函数只处理 `list[dict]` 消息。它们互不导入，也不导入 `semantic_compression`、`summary_compression` 或 token 估计器。

## 文件与 API

- `head_protection.py`
  - `restart_handoff_probe_bounds(...)`
  - `effective_protect_first_n(...)`
  - `protect_head_size(...)`
- `tool_group_boundary.py`
  - `align_boundary_forward(...)`
  - `align_boundary_backward(...)`
- `user_turns.py`
  - `is_blank_user_turn(...)`
  - `is_actionable_user_turn(...)`
  - `blank_echo_indices_after(...)`
- `user_anchor.py`
  - `find_last_user_message_index(...)`
  - `ensure_last_user_message_in_tail(...)`
- `assistant_anchor.py`
  - `find_last_assistant_message_index(...)`
  - `ensure_last_assistant_message_in_tail(...)`
- `last_n_users.py`
  - `ensure_last_n_user_messages_in_tail(...)`
- `turn_pair.py`
  - `find_turn_pair_end(...)`
- `tail_token_cut.py`
  - `find_tail_cut_by_tokens(...)`
- `preflight.py`
  - `has_compressible_window(...)`

## 调用方必须注入的策略

宿主负责导入这些模块并绑定策略函数：

1. `estimate_message_tokens(message) -> int`
   - `tail_token_cut` 需要这个可调用对象。
   - 本目录不提供 token 计数或估计。
2. 摘要识别：
   - `is_context_summary_content(content) -> bool`
   - `is_context_summary_message(message) -> bool`
   - `has_compressed_summary_metadata(message) -> bool`
   - `is_synthetic_compression_user_turn(message) -> bool`
3. 组合：
   - 工具组的向前和向后对齐
   - 最后一条用户、最后一条助手，以及最后 N 条用户的锚点
   - 回合对的结束
   - 头部大小和尾部裁剪

注入把消息格式决定、token 策略和组合顺序留在宿主，同时每个插件可以单独测试。

## 重要边界

- 第一次压缩保护 `system + protect_first_n`。已有压缩之后，或交接出现在恢复的头部之后，`protect_first_n` 衰减到零。
- 工具结果组不在边界上被切开。
- 空白用户行只有在紧跟着一条助手消息时，才算可移除的平台回声。
- 尾部 token 裁剪保留原来的 1.5 倍软上限、最少消息数、原始预算重试和进度下限。最后一步必须向前对齐，因此下限不会再次切进工具组。
- 最新用户上的头部下限冲突，通过把一整对回合向前推来解决，因此已完成的任务不会被压进一个尚未回答的提问。
- 预检只检查 `compress_start < compress_end`。它不修改消息。

## 已知限制与暂缓事项

- **由宿主挑选函数** — `load` 对本文件夹调用 `load_in_directory`。正文字段必须恰好匹配一个公开函数。这些模块互不导入，因此这里没有流水线对象。
- **没有 token 计数器** — `tail_token_cut` 使用调用方传入的估计器。本目录不导入 [`tokens`](../../../model/model_API/model_paramaters/tokens/README.cn.md)。
