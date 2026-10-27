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
| `profiles.py` | Which tools a model may be offered, and the sandbox mode a tool process leases. The rule is below. This is not `capability_profile`. |

## Which tools a model may use

The class is the name after `tools.`. A folder under [`capability/tools`](../../capability/tools/README.md) only places the file.

| Class | Names | Sandbox on the tool process |
|---|---|---|
| read | `read`, `glob`, `grep`, `read_image` | `read-only`, and it cannot be raised |
| command | `bash`, `pwsh`, `bash_persistent`, `run_code`, `terminal`, and any name that starts with `terminal_` | ceiling `danger-full-access`, default `workspace-write` |
| write | every other tool name, including `write` and `edit` | same ceiling and default as command |

`tool_allowed` is what [`kernel/communication`](../communication/README.md) `offers.py` and [`process_manager`](process_manager/README.md) `tool_dispatch.py` call. A name outside `tools.` is left alone. When the model start included a `capabilities` list, only names on that list remain. `permission` `read-only` then keeps the read class. `workspace-write` and `danger-full-access` leave the class list in place.

Both values are `--change` topics on the model start:

```text
linope process start model.openai_chat_model --change permission=read-only --change capabilities=read,glob
```

`permission` is `read-only`, `workspace-write`, or `danger-full-access`. `capabilities` is optional. With no list, every tool that permission still allows is offered. The model card stores both on `settings`. A permission also leases a sandbox in that mode. `reconcile.py` records that mode as a `sandbox/mode` event for the session.

`tool_with_workspace` leases a tool, a sandbox, and the ledger channel when the tool process itself starts. A read tool stays `read-only`. A write or command tool starts at `workspace-write` unless this launch names a mode, and the result stays inside the tool's ceiling and inside the session mode already recorded. [`kernel/environment`](../environment/README.md) enforces the mode on the room: a read-only room rejects file writes, and a confined mode wraps external commands. `tool_only` leases a tool and the ledger channel, with no sandbox.

Creation order is: take the operating-system pid, open an empty record, write leases from the claims, build the room, then mark the record ready.

`compile_declaration` in `kernel/resource` hashes kind and identity into the entity key. Call parameters stay in `call_params` and do not become another entity. A kind stays exclusive until this launch names it in `shared`. Closing the record returns every lease on it. The pool unloads an entity when no record still occupies it.
