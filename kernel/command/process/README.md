# process

English | [中文](README.cn.md)

Process commands open a capability and talk to processes that are already in this window. The resource record is [`kernel/process`](../../process/README.md). The plugin loop is [`kernel/process/process_runtime`](../../process/process_runtime/README.md).

## Contract

`process.py` accepts:

```text
linope process start <capability> [--change topic=value] [--count count] [--share resource kind] [--with kind=identity] [--once] [--ping]
linope process list
linope process show <pid> [address]
linope process trace <pid>
```

Inside a living window the same words run against that window. Outside it, `list`, `show`, and `trace` read the saved ledger, activity trail, and journal.

### Start

`start.py` asks the capability for its profile, opens one resource record per pid, prints each `pid=`, and stays in the launching process. It does not detach and it does not enter the `process_runtime` request loop by itself.

| Flag | Meaning |
|---|---|
| `--change topic=value` | Forwarded to `capability_profile`. `space` is also copied onto the memory claim. On a model start, `permission` is `read-only`, `workspace-write`, or `danger-full-access`, and `capabilities` is the tool list that may be offered. The rule is [`kernel/process`](../../process/README.md). |
| `--count` | How many copies to open. Omitted means one. |
| `--share <kind>` | Kinds this launch shares. A kind that is only allowed to be shared stays exclusive until it is named. Naming one kind does not share the others. |
| `--with kind=identity` | Claims an extra kind the profile did not already claim. A kind the profile already has stays as the profile wrote it. |
| `--once` | Closes the record and returns after one `load` has been handed over. |
| `--ping` | After open, asks each living process and waits for `pong`. No answer closes the record and the command fails. |
| `--cwd` | Working directory for the room. |
| `--env-file` | Env file for this start. The window's remembered file is used when this is omitted. |
| `--max-runtime-seconds` | Host execution limit for this launch. |
| `--max-concurrent-tasks`, `--min-concurrent-tasks`, `--max-sync-workers` | Thread policy for this launch. Defaults are 1. |

A capability with no usable profile stops before the process is created. `--share` of a kind the contract refuses, including a name that is not a resource, fails the start.

Without `--once` the command stays until the process exits or the window stops.

### Lines in the window

`listen.py` reads lines after start. None of these lines are written into the resource ledger.

| Line | Result |
|---|---|
| `load <kind> <pid> -- <body>` | Sent to the adapter that process already opened. `message` walks a model that has memory through [`kernel/scheduler`](../../scheduler/README.md). `tool` is a tool load. |
| `load message <pid> <address> -- <question>` | The text at that address is placed on the model's first page, then the question is stored and the turn runs. An address is `message/0`, `message/0-3`, or `chat/message/0`. A bad address is refused before the question is stored. `show <pid>` lists every visible row. |
| `load <kind> <pid> -- <n> <file>` | A `.txt`, `.md`, or `.json` file is copied into `system` and is not sent to the model. The copy index starts at 1. The same path updates that copy. Without an index, a new file goes last and an existing path stays where it was. A process with no memory refuses the file. |
| `ask <pid> -- <task>` | Hands one task to that process. The sender's memory is not attached. A peer with memory runs its own page turn, so the task and the answer are stored in the peer's memory. A peer with no memory receives the task text. The result is written back into the sender's memory. Both sides are recorded as `with`, then return to `sleeping`. Exactly one other living process must exist to act as the sender. |
| `ping <pid>` | Asks that process. `pong` must carry the same sequence and pid. Silence, a wrong sequence, or a different pid is no answer. |
| `list` | Prints `pid`, activity, and record status for processes in the window. |
| `show <pid> [address]` | Prints the process page. When the process has memory, the page includes the memory contents for that address. |
| `trace <pid>` | Prints that process's activity rows. |

`load message` to a process with memory always runs a page turn. The window does not need to be able to launch another process for that. `process start` is offered on the page only when it can. `load message` to the process itself records activity `self` while the call runs, then `sleeping` when it returns. What a person said, model output, tool output, and a handed-back task result are written into that process's memory when it has one. Those bodies are not written to the process ledger. A tool load sends its body unchanged.

After the window closes, `show` reads the saved ledger. The dialogue body was kept in the memory entity, not in the ledger file.

## Known Limitations and Deferred Work

- **`ping` in the window requires a pid** — `ping` with no pid is a usage error. Startup `--ping` asks every process this start opened.
- **A task handoff needs exactly one sender** — `ask` succeeds only when exactly one other living process can act as the sender.
