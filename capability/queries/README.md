# queries

English | [中文](README.cn.md)

Read-only answers a kernel process can ask for by starting this module. The kernel does not import these functions.

```text
python -m capability.queries tail-cut
```

stdin is one JSON object: `messages`, an integer `budget`, and a `tokens` list of the same length. stdout is `{"cut": <int>}`. `cut` is the first message index kept when the list is retained from the end until `budget` is spent. `0` means every message fits.
