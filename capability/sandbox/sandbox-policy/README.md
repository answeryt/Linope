# sandbox-policy — per-session sandbox policy

English | [中文](README.cn.md)

Single owner of policy resolution. The deployment default is `read-only`. Each call: approved mode > last `sandbox/mode` event > default.

| Plugin | File | Role |
|---|---|---|
| `sandbox_session_mode` | [`src/session_mode_plugin.py`](src/session_mode_plugin.py) | Three modes, fold, write path |
| `sandbox_policy` | [`src/sandbox_policy_plugin.py`](src/sandbox_policy_plugin.py) | `resolve()`; Host injects `canonical_path` and `effective_mode` |

`danger-full-access` is resolved here and skips `confine`.

## Known Limitations and Deferred Work

- **The deployment default is `read-only`** — a session with no approved mode and no `sandbox/mode` event stays read-only.
