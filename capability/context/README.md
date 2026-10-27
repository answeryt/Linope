# context/ — compression functions a process can load

English | [中文](README.cn.md)

`load_in_directory` picks the one public function in a folder whose signature accepts the body's keys and no extra keys. Zero matches or more than one match raises `ValueError`. `capability_profile` and `load` are not candidates. A string body becomes one user message.

Each compression package claims a `memory` resource whose `scope` is the capability id. `--change` values are not applied to that declaration.

| Directory | Role |
|---|---|
| [`context_compression/`](context_compression/README.md) | Semantic, summary, and sliding-window functions |
