# Sliding-window compression atomic functions

本目录是无 Host、无 facade 的原子函数集合。它们不是 compose 自动发现的
capability；当前由 Host 显式 import 和组合。函数只处理
`list[dict]` 消息；彼此没有项目内 import，也不依赖
`semantic_compression`、`summary_compression` 或 `model/token`。

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

未来 Host 负责导入这些模块并绑定策略函数：

1. `estimate_message_tokens(message) -> int`
   - `tail_token_cut` 强制注入此 callable；
   - 本目录不提供任何 token 计算或估算实现。
2. 摘要识别：
   - `is_context_summary_content(content) -> bool`
   - `is_context_summary_message(message) -> bool`
   - `has_compressed_summary_metadata(message) -> bool`
   - `is_synthetic_compression_user_turn(message) -> bool`
3. 组合函数：
   - tool-group 前向/后向对齐；
   - last user、last assistant、last-N users anchor；
   - turn-pair end；
   - head size 与 tail cut。

注入使消息格式判定、token 策略及组合顺序留在 Host，同时每个插件可单独测试。

## 关键边界

- 首次压缩保护 `system + protect_first_n`；已有压缩或恢复头部出现 handoff
  后，`protect_first_n` 衰减为零。
- tool result 组不会被边界切开。
- 空 user 行仅在其后紧接 assistant 时视为可删除的平台 echo。
- 尾部 token cut 保留原 1.5 倍软上限、消息数下限、raw-budget 重走和
  progress floor；最后必须前向对齐，避免 floor 再次切入 tool group。
- latest user 的 head-floor 冲突通过完整 turn-pair 前推解决，避免已完成任务
  被压成 pending ask。
- preflight 只判断 `compress_start < compress_end`，不修改消息。
