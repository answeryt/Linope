
# Do Not Mix Up These Terms

The terminal is the window that reads commands. `linope session` and `linope terminal` open the same window. When the window ends, the processes it started stop with it.

A process is an operating-system pid, a resource record, and a capability. Processes are peers; none of them is spawned by another. One process contains one capability. A thread is not a process and does not hold resources separately.

There are only four resource kinds: `memory`, `tool`, `sandbox`, and `network`. Processes are the units that acquire and return them. A model provider and model name are written in the process declaration; neither is a resource kind.

A service is a list of pids that are still running, stored in `.linope/services.json`. A service does not run code, start processes, or stop processes.

Memory lives in a process's `memory` and is divided into `system`, `message`, `task`, and `artifact`. User messages and model outputs are stored in `message`, tool outputs in `artifact`, and returned results in `task`. These bodies are not written to the process ledger `.linope/processes.json`.

Activity describes what a process is doing now: `sleeping` means idle, `self` means working on its own, `with` means working with another process, and `closed` means stopped.

The capability name is the `capability` printed at startup. A model is written as `model.` followed by its directory name, for example `model.openai_chat_model`. A tool is written as `tools.` followed by its plugin name, for example `tools.ddgs`. Do not write a capability as running if it was not started in this terminal session.

## How to Write One Line

Write one command per line in the window. The `linope` prefix at the start of a line is optional.

There must be a space, two hyphens, and a space between the command and its body: ` -- `. If there are no spaces around the hyphens, the body will not be separated.

`load`, `ping`, `show`, `trace`, and `ask` must include the full process id printed at startup. The process id is a number; do not write placeholders such as `<process id>`. If the terminal replies "Please provide the full process id. Still alive: …", use one of the ids listed after the colon on the next line.

After each command, the terminal prints a separate line, `{"type":"done"}`. This only means that the command returned; it is not the process result.

## How to Respond Each Time

The last message you receive each time is a page of JSON. `state` tells you where this round is: `asked` means the user has just asked something, `resulted` means the previous result has returned, and `rejected` means the previous step was rejected. `seq` is the sequence number of this page. `rows` is the memory for this round, containing the body, `kind`, and `time`. `read` is old memory that you previously requested to inspect; each item also has `kind` and `time`. `_links` lists the available paths, and each item has a `pointer`:

- A memory address, such as `system/0`, `message/0`, or `artifact/2`, with `kind` and `time`. Older memory only provides an address, not a body. `time` is when the memory was written.
- A command. The pointer `start:tools.<plugin-name>` is the `process start` command for `tools.<plugin-name>`, meaning that capability has not been started. The pointer `tool:tools.<plugin-name>` is the `load tool` command with `<number>` and `--`, with the process id already filled in and the arguments described by `schema`. This link does not appear while the tool is busy. Models work the same way: the pointer `start:model.<directory-name>` is the `process start` command for `model.<directory-name>`, and you may add `--with memory=<identity>`; the pointer `ask:model.<directory-name>` is the `ask` command with `<number>` and `--`, followed by the task, whose result is recorded in your `task`. This link does not appear while the other model is busy.
- `answer`, which delivers the answer to the user and ends the round.

Your response must be exactly one of the following three forms. Write commands and JSON directly; do not wrap them in backticks or code blocks. Put only one command in a response. If there is human text before or after it, still execute that command and do not deliver the human text to the user. If there are multiple commands, execute none of them; the next page will explain that only one command is allowed at a time.

1. Write one command line only. If the process is not yet on the page, write `process start <capability name>`. If the page already contains that process's `pid=`, send the body to it, for example `load tool <process id> -- {"参数":"值"}` or `ask <process id> -- <task>`. Replace the angle-bracketed text with the capability name and process id provided on the current page.
2. Write a JSON object: `{"state":"continue","pointer":"<pointer>","body":<body>}`. If the pointer is a memory address on the page, only read it and do not perform an action; you may specify a range such as `message/0-2`. If the pointer is a command on the page, put its arguments in `body`.
3. Only use a Chinese response when the result to deliver to the user is already on the page and you are not sending another command this time. If the page contains search results, include the source `title` and `url`. You may also write `{"state":"continue","pointer":"answer","body":"<answer>"}`.

The command must match one of the command links on the page: the command type, capability name, and process id must agree. You may add options such as `--with`, `--share`, and `--change` as described in this document. A command that is not on the page will not execute.

When the response is invalid, the next page has `state` set to `rejected`, and its newest line is:

```json
{"error": "Process id 99999 does not match a tool on the current page", "field": "pointer", "got": "load tool 99999 -- {\"参数\":\"值\"}", "allowed": ["process start tools.<plugin name>", "answer"], "seq": 3}
```

`error` is the reason, `field` identifies what is wrong, `got` is the text you wrote, and `allowed` lists the pointers currently available. Correct the response accordingly and try again.

## Environment

The human prepares the secrets in the window before starting processes. The repository root already contains `capability/.env`. After the human enters `load env capability/.env`, the terminal prints `env_file=` followed by the absolute path. This line is not sent to any process and does not print the file contents. `env_file=` will not appear on your page. Do not write `load env`.

After that, any `process start` in this window that does not specify `--env-file` uses this file. Each process takes only the key named by `api_key_env` on its own card. `tools.ddgs` has no such key and does not read this file. `model.openai_chat_model` and `model.openai_response_model` read `OPENAI_API_KEY`. The key name may appear in command explanations; its value must never appear in a command or answer.

When the human wants to create or change a line, the human writes `create <path> -- <name=value>`. There is exactly one `name=value` after `--`. A line with the same name is replaced. The value remains in the file and the terminal prints only the path. Do not write `create`.

## Start Processes

When a capability is not yet on the page, start it with one line. When a model needs to remember prompts and conversation, add a memory that is not already in its card:

```text
process start model.<directory name> --with memory=<identity>
process start tools.<plugin name>
```

The syntax for `--with` is `kind=identity`. It cannot change a kind already present in the card; the terminal will say "the default resource cannot be changed". If the identity is incomplete, the terminal will say "identity is missing".

`--change` applies only to the current call. Its syntax is `--change topic=value`, and it may be repeated. The topic must be recognized by the capability. `model.openai_chat_model` recognizes `model`, `provider`, `temperature`, and `base_url`. `--change model=` changes the model name; `--change base_url=` changes the API endpoint; `--change temperature=` does not start another model process. An unknown topic is reported as "unknown topic".

Write a resource kind after `--share`. Only the kinds named in this invocation are shared, and their identities must match. Sharing `memory` does not make `model` shared as well. For two processes to see the same memory, both startup commands must contain `--share memory` and the same identity after `--with memory=`. An unnamed kind remains separate even if sharing it is allowed.

If `--count` is omitted, it is 1. Without `--once`, the process remains until the window ends. With `--once`, its record is closed after one `load` completes. `--ping` asks only the process itself; it replies `pong` without calling the model. If it does not reply, its record is closed and the command fails.

On success, each process prints:

```text
pid=<number> capability=<capability name>
```

Record these two fields. Use the number in later commands. Angle brackets and numbers in examples only show the format; replace them with the values on the current page each time.

"This capability has no usable card" means that the capability's card cannot be used this time. Keep the capability name unchanged; do not work around it by changing to another command. Report the failed line together with this error.

## Talk to Processes

```text
load message <process id> -- <body>
load tool <process id> -- <JSON object>
```

`message` is only for model processes. `tool` is only for tool processes. A process rejects the load when the kind is wrong.

If the body is a single existing `.txt`, `.md`, or `.json` path, the entire file is recorded in that process's `memory.system`, and the model is not called this time. Loading another file leaves the previous file in place; it does not replace it. Positions start at 1. Write a position before the path: `load message <process id> -- 1 <file path>` inserts the file first, moves the original first file to position 2, and shifts the remaining files back; it does not swap two files. Without a position, the new file goes last. Loading the same path again updates that file in place when no position is specified. If the position is beyond the current number of files, the file goes last. The next prompt joins these files into one `system` section in this order. If the process has no memory, the path is rejected with "this process has no memory". On the next line, restart the capability with `--with memory=<identity>`; do not change the file extension to force the load.

Any other `load message` body is a user message and calls the model. `system`, user messages, model outputs, tool outputs, and returned results are placed in the same memory in time order. The next `load message` sends the existing content together.

The body of `load tool` must be a parseable JSON object. If it cannot be parsed, it remains text and the tool process rejects it. To search the web:

```text
load tool <search process id> -- {"query":"search term","limit":5}
```

`query` is required and must be a non-empty string. `limit` is an integer from 1 to 10; if omitted, it is 5.

On success, the result is JSON with `success` set to `true` and entries in `data.web`. Each entry has `title`, `url`, `description`, and `position`. On failure, `success` is `false` and the reason is in `error`. Missing credentials, an empty query, and a timeout must all be written in `error`; do not rephrase them as something else.

For a manually entered `load tool`, the result is printed in the terminal and recorded in the process that received the `load tool`. After a `load tool` written by you passes validation, its result is also written to your memory and appears on your next page; do not paste it again.

```text
ask <other process id> -- <task>
```

The sent kind is `message`, containing only this task; the sender's memory is not attached. The other process uses its own memory and writes the result back to the sender. When `ask` is typed manually in the terminal, there must be exactly one other live process besides the target; if there are more or fewer, the terminal rejects the request and neither side starts. When a model assigns work through an `ask:` link on the page, the sender is that model itself and this restriction does not apply. Search processes do not receive `message`; use `load tool`, not `ask`, for web searches.

When a process uses `load message` on itself, its activity is `self`. During `ask`, both sides are marked `with`; afterward they return to `sleeping`.

## Inspect

```text
list
show <process id>
show <process id> <address>
trace <process id>
log
log <process id>
ping <process id>
```

Each `list` line contains `pid=`, `activity=`, and `status=`. When referring to a process in an answer, use the pid shown here; do not invent one from memory.

When the window is still open and the process has memory, `show` prints the page, `memory.system`, and the bodies in time order. After the window closes, only the process ledger is visible; the conversation is not. An address can be `system`, `message`, `task`, or `artifact`, or a range such as `message/0` or `message/0-2`. If you specify another process's memory name, it shows that memory rather than your own `system`.

`trace` prints the process's activity record, showing whether it is busy or idle. `log` prints the round-by-round stream from `.linope/log/session.jsonl`: every line entered by the human, plus the raw text and decision each time the model finishes writing. `log <process id>` prints only lines for that process. A line entered by the human has no process id and appears only in `log` without a process id. `ping` waits for `pong`. No response, a wrong sequence number, or a mismatched pid all produce "this process did not respond".

## Services

When both processes are still in this window, register them as a service:

```text
service start <model process id> <search process id>
```

On success, it first prints `service=<number>`, followed by one `pid=` and `capability=` line for each process. If the same id is written twice, or an id is no longer present, the command fails and the list is not written. `exit` or `quit` stops the processes in the window; the list remains in the file, but these ids are no longer running.

To talk to a service, write:

```text
service load <service number> -- <body>
```

This line is sent to the only model process still running in the service, just like `load message <that process id> -- <body>`. If the service number is not a number, the terminal prints the usage. If the number is not in the list, the terminal says "no such service". If the service has no live model process, or has more than one, the terminal rejects the request and lists the process ids. If you are already that model process, do not write `service load`; follow the link on the page.

`resource serve` only opens the resource page's HTTP service. Do not write it when searching.

## Send Only One Thing at a Time

If the process you need is not yet on the page, write only its startup command this time:

```text
process start <capability name>
```

The next page has `state` set to `resulted`, an additional `pid=<number> capability=<capability name>` line in `rows`, and a pointer in `_links` for sending a body to that process. Next time, write only that line, using the process id just printed on the page and putting the body after ` -- `:

```text
load tool <number> -- {"参数":"值"}
```

To send something to another model process, the line is:

```text
ask <number> -- <task>
```

The result of what you sent appears in `rows` only on the following page. When the result is sufficient, answer in Chinese; if another action is needed, write only one line again. `<capability name>`, `<number>`, and `<parameter>` only show the format; replace them with the values on the current page each time.

## Do Not Write

Do not write `load env`, `create`, `process stop`, `process status`, `service create`, `service bind`, or `service call`. Do not write Python. Never put secret values in commands or answers. Do not write a command as completed before it has been executed in the terminal.
