# Sliding-window compression atomic functions

English | [中文](README.cn.md)

This directory is a set of atomic functions with no facade. `load` selects one of them through [`load_in_directory`](../../README.md). A host may also import them and combine them. Functions handle only `list[dict]` messages. They do not import each other, and they do not import `semantic_compression`, `summary_compression`, or the token estimators.

## Files and API

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

## Policy the caller must inject

The host is responsible for importing these modules and binding policy functions:

1. `estimate_message_tokens(message) -> int`
   - `tail_token_cut` requires this callable.
   - This directory provides no token counting or estimation.
2. Summary recognition:
   - `is_context_summary_content(content) -> bool`
   - `is_context_summary_message(message) -> bool`
   - `has_compressed_summary_metadata(message) -> bool`
   - `is_synthetic_compression_user_turn(message) -> bool`
3. Composition:
   - forward and backward alignment of a tool group
   - last user, last assistant, and last-N users anchors
   - turn-pair end
   - head size and tail cut

Injection keeps message-format decisions, token policy, and composition order in the host, while each plugin can be tested alone.

## Important boundaries

- The first compression protects `system + protect_first_n`. After an existing compression, or after a handoff appears in a restored head, `protect_first_n` decays to zero.
- A tool-result group is not cut at a boundary.
- A blank user line counts as a removable platform echo only when an assistant message follows it immediately.
- The tail token cut keeps the original 1.5x soft cap, the minimum message count, the raw-budget retry, and the progress floor. The last step must align forward, so the floor does not cut into a tool group again.
- A head-floor conflict on the latest user is resolved by pushing a whole turn pair forward, so a finished task is not compressed into a pending ask.
- Preflight only checks `compress_start < compress_end`. It does not modify messages.

## Known Limitations and Deferred Work

- **The host picks the function** — `load` calls `load_in_directory` on this folder. The body keys must match exactly one public function. These modules do not import each other, so there is no pipeline object here.
- **No token counter** — `tail_token_cut` uses the estimator the caller passes. This directory does not import [`tokens`](../../../model/model_API/model_paramaters/tokens/README.md).
