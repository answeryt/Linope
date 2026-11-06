# generate/ — list cards and architecture cards

English | [中文](README.cn.md)

Plugin review writes the allow and deny lists. The layer scripts write architecture cards and do not check source.

| Directory | Role |
|---|---|
| [`plugin/`](plugin/README.md) | Discover families, run `*_check.py`, write allow and deny cards |
| [`services/`](services/README.md) | Services-layer architecture card |
| [`process/`](process/README.md) | Process-layer architecture card |
| [`compose/`](compose/README.md) | Compose-layer architecture card |

Review and generation are separate. A check only appends violations. A generator only writes lists or cards. The allow list is written by hand. The deny list is the discovery result minus the exempt paths.

```text
python capability/tools/external_tools/ci_tools/generate/plugin/plugin_generate.py --check
python capability/tools/external_tools/ci_tools/generate/services/services_generate.py
python capability/tools/external_tools/ci_tools/generate/process/process_generate.py
python capability/tools/external_tools/ci_tools/generate/compose/compose_generate.py
```

## Known Limitations and Deferred Work

- **Architecture cards do not check the tree** — `services`, `process`, and `compose` write vocabulary. A mismatch with `kernel/` is invisible to those scripts.
- **The marker walk is not this layout** — `find_repo_root` returns the first ancestor that has `.gates/isolation-allowlist.json`, a top-level `model/` and `tools/`, and `kernel/compose/capability`, next to `capability/`. This repository keeps model and tools under `capability/`. When no ancestor matches, the function returns six parents above `plugin_generate.py`, which is the repository root at the current path.
