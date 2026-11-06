# process/ — one pid, one resource record

English | [中文](README.cn.md)

Capability processes are peers. There is no process tree: a process and the processes it started are not stopped as one group. One operating-system `pid` has one resource record. A thread and a service are not resource owners.

The operating system still records the creator at creation. This directory does not inherit pipes, place the process in a job object or a process group, or signal the process from that relationship. A new process still receives the environment variables from creation, so it can start on Windows. Isolation is the handles on this record.

One process loads one plugin. An agent that needs a model and tools is several peer processes, each with its own record.

| Directory | Role |
|---|---|
| [`process_creat/`](process_creat/README.md) | Resolve the capability name and pack one `ProcessActivation` |
| [`process_runtime/`](process_runtime/README.md) | Load the plugin and serve requests inside the process |
| [`process_manager/`](process_manager/README.md) | Lifetime of one `CapabilityProcess` |

## Contract

Files in this directory own the record. The start command is [`kernel/command/process`](../command/process/README.md). The four resource kinds are [`kernel/resource`](../resource/README.md).

| File | Role |
|---|---|
| `profile.py` | Calls the first `capability_profile`. `ProfileUnavailable` is raised before the reconciler when the capability has no usable profile. The card file is not read here. |
| `declaration.py` | `ProcessDeclaration` is the creation input: a capability, resource claims, and `settings`. Provider, model id, and temperature stay in `settings` and are not a lease. `append_chosen` adds a kind the profile did not claim; a kind already present stays as the profile wrote it. `stamp_memory_space` copies `--change space=` onto the memory claim. |
| `reconcile.py` | `ProcessReconciler` compiles the declaration, binds leases, builds the room from the record, then spawns. A failed step drops that record. |
| `resource_record.py` | One in-memory account per pid. Status is `opening`, `ready`, `closing`, or `closed`. |
| `ledger.py` | One file copy of those accounts, default `.linope/processes.json`. Call results and file bodies stay out of the file. |

## Which tools a model may use

A folder under [`capability/tools`](../../capability/tools/README.md) only places the file. Which commands a page offers is decided by [`capability/agent_loop`](../../capability/agent_loop/pi/main.mjs). The kernel does not choose by tool name, and it does not mark a tool read-only because of that name.

Sandbox modes live in [`capability/sandbox`](../../capability/sandbox/README.md). When nobody names one, the default is `read-only`. `permission` is still a `--change` on start. `reconcile.py` records it as a `sandbox/mode` event for the session. [`kernel/environment`](../environment/README.md) enforces the mode on the room: a read-only room rejects file writes, and a confined mode wraps external commands.

Creation order is: take the operating-system pid, open an empty record, write leases from the claims, build the room, then mark the record ready.

`compile_declaration` in `kernel/resource` hashes kind and identity into the entity key. Call parameters stay in `call_params` and do not become another entity. A kind stays exclusive until this launch names it in `shared`. Closing the record returns every lease on it. The pool unloads an entity when no record still occupies it.
