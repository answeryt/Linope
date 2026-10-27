# process_manager

English | [中文](README.cn.md)

Looks after one capability process that is already running: ask it, wait for the answer, check that it is still alive, and stop it. Compiling the declaration is [`reconcile.py`](../reconcile.py). Choosing which process receives new work is [`kernel/load_balancing`](../../load_balancing/README.md). The resource ledger is [`resource_record.py`](../resource_record.py).

One process is one `CapabilityProcess`. It holds the activation from start and its own resource record. Several copies of one capability are several operating-system pids, one per copy, opened by the reconciler. They are not stopped as a parent and its children.

## Each script

`capability_process.py`

The process itself. `ask` sends one message and waits for the reply. `submit` accepts one call and returns a `Receipt`. It does not append a row to the resource ledger. `answer_ping` returns `pong` with this sequence only when the asked pid is this process. When both sides name a channel, the channels must match. Otherwise it stays quiet. Whether the sequence matches is checked again in [`kernel/command/process`](../../command/process/README.md). `stop` closes this resource record and returns the leases.

`lifecycle.py`

The status names: `created`, `starting`, `running`, `stopping`, `stopped`, `failed`.

`handle.py`

`ProcessHandle`, the view shown outward. It carries this process's pid. It does not carry the resource entity.

`client.py`

A `Receipt` is the ticket for one call. It keeps the request id and the pid. It does not keep the whole process object. `ready` says whether the reply has arrived. `wait` waits until that call is finished.

`liveness.py`

Whether the pid on a ledger row is still that operating-system process. `process_matches` is true only when it still is. `reap_dead` closes a record that is still marked ready after that process is gone.

`reaper.py`

`ProcessReaper` looks at one row. When the status is `starting` or `running` and the process is already gone, it runs the cleanup it was given.

`monitor.py`

Looks at these peer processes and can stop one of them. It does not group them as parent and children. `handle` returns the outward pid view. `reap_if_dead` is handed to `reaper.py`.

`tool_dispatch.py`

Builds one tool call for a process that already exists. The message is `load` with kind `tool`. A name without a `tools.` prefix gets one. `tool_allowed` in [`profiles.py`](../README.md) refuses the call when the current permission or tool list cannot use that tool. Reading `tool_schemas` uses the same check and returns nothing when the tool is refused. This script can also name the capability to start. It does not start it.

`__init__.py`

Exports `CapabilityProcess`, `ProcessActivation`, and `ProcessStatus`.
