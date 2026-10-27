# process_runtime

English | [中文](README.cn.md)

This is where the capability plugin actually runs inside the process. The activation names the files to load. This directory loads them, attaches the working directory, the environment variables, and the resource handles, and keeps taking requests until it is closed. The commands a person types are [`kernel/command`](../../command/README.md). `process start` stays in the process that launched it. Later `load message` and `load tool` lines go to the adapter this directory already opened.

## Each script

`adapter.py`

The shape a plugin must have, named `CapabilityAdapter`. `initialize` runs after the handles arrive. One request uses `handle`, or `handle_async` when it should not sit on a thread while it waits. `shutdown` runs before stop. `is_async` says whether it can run asynchronously. `sync_thread_safe` says whether [`kernel/thread`](../../thread/README.md) may give it more than one synchronous helper.

`runtime.py`

`open_adapter` first switches to the working directory chosen for this start and checks that the named environment variables exist. In code that step is `apply()` on the `KernelEnvironment` in [`kernel/environment`](../../environment/README.md). It then loads the modules named by the activation. When a module has `create_adapter`, that builds the adapter and `initialize` is called. When none does, the working directory is already in place and the result is no adapter. A failure during open closes the adapter that was created, then raises.

`close_adapter` calls `shutdown`. Closing again is safe.

`serve_capability` opens and closes in the same call, then calls `on_exit` with the pid. That is one run that leaves when it finishes.

`serve_stdio` is this process's own loop. It reads one startup JSON line, which must contain `activation`. Each later request line goes to the adapter, and the reply is written to standard output, until the pipe closes. It does not decide whether the caller wanted only one job.

`__main__.py`

Calls `serve_stdio` when this directory is started as a program. The side that launched it decides when the program should leave.

`__init__.py`

Still exports `CapabilityProcess`, `ProcessActivation`, and `ProcessStatus`. Those names are defined in `process_manager` and `process_creat`. This module imports them late, so the two packages do not import each other at load time.
