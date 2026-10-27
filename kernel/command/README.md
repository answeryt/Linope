# command/ — `linope` command entry

English | [中文](README.cn.md)

`dispatch.py` reads the first word and hands the rest to that script. An unknown word, or a bad usage line, exits 2.

There are two layers. The first word names an object: create a file, start a process, look at a process, or record pids that are already running as one service. A short line typed after the window is open talks to a process that is already open, for example `load message`. A short line does not start a process.

This layer does not read a model card, run a tool, or pick a command out of model output. The card is in the capability plugin. The tool runs in the tool process. Parsing a model reply is [`kernel/communication`](../communication/README.md).

| Directory | Commands |
|---|---|
| [`file/`](file/README.md) | `create`, `load env` |
| [`process/`](process/README.md) | `process start`, and the window lines `load`, `ask`, `ping`, `list`, `show`, `trace` |
| [`screen/`](screen/README.md) | `resource serve`, and printing one fragment of a model reply to the terminal |

`service` is [`kernel/services`](../services/README.md). The turn journal that `log` prints is [`kernel/trace`](../trace/README.md).

## Object commands

These are the object commands. They can be typed outside a window. The full flag tables are in the directory READMEs above.

`create <path> [-- name=value]`

Creates a file on this machine. One `name=value` after `--` is written into that file, to prepare an environment variable. This does not start a process.

`load env <path>`

Remembers this env file. The next `process start` in the same window uses it when `--env-file` is omitted. The value stays in the file. The command prints the path.

`process start <capability>`

Starts a process by capability name. `process start model.openai_chat_model` starts a model process. `process start tools.read` starts the read-file tool process. The capability's `capability_profile` says which resources this start claims. One operating-system pid has one resource record. The command prints `pid=` and stays in the current window, waiting for a body. It does not call the model by itself.

`--count 2` starts two copies. The copies are peers. `--share memory` is what makes this start share memory. Without it, each copy has its own. `--with memory=chat` claims one extra kind the profile did not already claim. `--once` closes after one `load` has been handed over. `--ping` asks after open, and fails when nobody answers.

`process list`

Lists the processes in the window: pid, busy or idle, record status. It does not start a process.

`process show <pid> [address]`

Shows one process page. When that process has memory, the page includes the contents at that address.

`process trace <pid>`

Shows that process's activity, from idle to busy.

After the window closes, `list`, `show`, and `trace` read the ledger and logs on disk. Dialogue text is in memory, not in the ledger file.

`service start <pid> [<pid> ...]`

Records pids that are already running as one service, in `.linope/services.json`. One missing, dead, or repeated pid writes nothing. Starting a process is still `process start`.

`service load <service id> -- <body>`

Used inside a window. It finds the single model process in that service that is still open, rewrites the line as `load message <that pid> -- <body>`, and hands it to that process. No model, or two models, is a refusal. The service does not choose the next tool.

`resource serve [--host 127.0.0.1] [--port 0]`

Starts an HTTP service on this machine so a developer can open resource pages in a browser. A model search or file edit does not use this command.

`log [pid]`

Prints the turn journal in time order: each line a person typed, and the text each time the model finishes a write. `log <pid>` keeps only that process. A typed line has no pid, so it appears only in `log` without a pid.

`terminal` and `session`

Open the same window. The short lines below are typed in that window.

## Lines inside the window

After `process start` leaves the window open, [`process/listen.py`](process/listen.py) reads these lines. They are not written into the resource ledger. Arguments and failures are in [`process/`](process/README.md).

`load message <pid> -- <body>`

Sends that sentence to the model process. The process must already be open, and it must be a model. When it has memory, the sentence is stored there and the question runs as a page turn until the model answers. Older rows stay addresses on that page. The window does not have to be able to launch a process for this turn; `process start` is offered only when it can.

`load message <pid> <address> -- <question>`

Places the text at that address on the first page the model sees, then stores the question and runs the turn. An address is `message/0`, `message/0-3`, or `chat/message/0`. Several addresses are separated by spaces. A bad address is refused before the question is stored. `show <pid>` still lists every row this process can see.

`load tool <pid> -- <JSON>`

Sends that call to the tool process. The process must already be open, and it must be a tool.

`load message <pid> -- <n> <file>`

Copies a `.txt`, `.md`, or `.json` file into the `system` section of that process's memory. This step does not call the model. A process with no memory refuses it.

When the second word of `load` is not `env`, `dispatch.py` does not treat the line as `load env`. It hands the line to the open window. `load env` remembers an env file. `load message` talks to a process.

`ask <pid> -- <task>`

Hands the task to another process that is already open. The receiver does not see the sender's memory. A receiver with memory runs its own page turn, so the task and the answer are stored there. A receiver with no memory gets the task text. The result is written back to the sender. Besides the receiver, the window must contain exactly one other living process to act as the sender.

`ping <pid>`

Asks whether that process is still there. The answer must be `pong` with the same sequence and the same pid.

`list`, `show <pid>`, `trace <pid>`

The same lookups as `process list`, `process show`, and `process trace`, typed inside the window, against the processes in that window.
