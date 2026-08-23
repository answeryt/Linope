# sandbox-local — local runner selection

English | [中文](README.zh.md)

`confine(argv, policy)` wraps argv per platform: Linux `bwrap` then Landlock; macOS Seatbelt; Windows the ACL `runner_plugin.py`.

No usable backend raises `SANDBOX_UNAVAILABLE`. `danger-full-access` skips `confine`.
