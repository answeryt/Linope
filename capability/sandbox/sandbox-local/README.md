# sandbox-local — local runner selection

English | [中文](README.cn.md)

`confine(argv, policy)` wraps argv per platform: Linux `bwrap` then Landlock; macOS Seatbelt; Windows the ACL `runner_plugin.py`.

No usable backend raises `SANDBOX_UNAVAILABLE`. `danger-full-access` skips `confine`.

## Known Limitations and Deferred Work

- **One missing backend fails the confined call** — there is no fallback from a missing `bwrap` or Landlock helper to an unconfined argv. `danger-full-access` is the mode that skips `confine`, resolved in [`sandbox-policy`](../sandbox-policy/README.md).
