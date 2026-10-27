# services

English | [中文](README.cn.md)

A service is a saved list of process ids that are already running. The list is a file. It is not a process, and it does not start or stop one.

## Scripts

| Script | Role |
|---|---|
| `__init__.py` | Exports `ServiceBook` and `ServiceGroup` |
| `collection.py` | Reads and writes the service file |

`__init__.py` re-exports the two names from `collection.py`. Callers import them from `kernel.services`.

`collection.py` holds the list.

`ServiceGroup` is one group: a positive integer `service_id`, and the process ids in `pids`.

`ServiceBook` is the file copy. The caller passes the path. The command uses `.linope/services.json`. The file looks like this:

```json
{"services": [{"id": 1, "pids": [11, 12]}]}
```

| Entry | What it does |
|---|---|
| `groups` | Reads every group. A missing file is an empty tuple. |
| `get` | Finds one group by id. Returns nothing when the id is absent. |
| `add` | Gives the next id, one past the highest id already in the file, and writes the new group. The first id is 1. |

A record may contain only `id` and `pids`. An extra field, a missing field, an id or pid of 0 or less, an empty pid list, or the same pid twice refuses the file. `add` writes a temporary file beside the real one, then replaces the real file, so a half-written list is not left behind.

Checking that a pid is still open, and handing a line to the one model in the group, is [`kernel/command/service.py`](../command/service.py). `service start` checks the process ledger, then calls `add`. One bad pid writes nothing. `service load` calls `get`, then `entry_of` picks the single `model.` process in that group that is still open and rewrites the line as `load message <pid> -- <body>`. No open model, or more than one, refuses the line. Each member keeps its own pid and resource record. See [`kernel/process`](../process/README.md).
