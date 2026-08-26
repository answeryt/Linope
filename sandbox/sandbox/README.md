# sandbox — process-sandbox vocabulary

English | [中文](README.zh.md)

Linope same-world process-sandbox vocabulary plugins. They own the three file-effect modes and the `confine` contract. They do not implement a platform runner and do not depend on Cordis.

| Plugin | File | Role |
|---|---|---|
| `sandbox_provider` | [`src/sandbox_plugin.py`](src/sandbox_plugin.py) | Mode vocabulary, `SANDBOX_UNAVAILABLE`, confined-argv shape |
| `sandbox_roots` | [`src/roots_plugin.py`](src/roots_plugin.py) | `canonical_path` / `writable_roots` |
| `sandbox_escalation` | [`src/escalation_plugin.py`](src/escalation_plugin.py) | Escalation ladder and fail-closed approval |

Modes:

- `read-only` — no writes except required sinks such as `/dev/null`
- `workspace-write` — workspace root plus platform temp areas
- `danger-full-access` — skip confine; spawn the original argv

Host injects `confine`. A confined mode must return wrapped argv or raise `SANDBOX_UNAVAILABLE`. Silent unconfined passthrough is forbidden. Sibling plugins do not import each other; mode names are duplicated locally.
