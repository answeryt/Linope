# environment

English | [中文](README.cn.md)

The working directory, the paths a capability process may read or write, the secret names it may look up, how long it may run, and whether an external command is wrapped: all of that is recorded here. The room is assembled from the resource record when the process starts. It is not widened after that.

Chat text and memory rows are not here. Model pages are [`kernel/communication`](../communication/README.md). Memory is [`kernel/resource`](../resource/README.md). This directory does not copy either of those.

The three file modes come from [`capability/sandbox`](../../capability/sandbox/README.md): `read-only`, `workspace-write`, and `danger-full-access`. This directory does not keep a second list. Which mode a tool process receives is chosen in [`kernel/process`](../process/README.md) and stored on the sandbox lease before the room is built.

## Each script

`room.py`

Puts the pieces below into one `KernelEnvironment`. `apply()` sets the working directory and the environment variables that were named explicitly.

`current.py`

Which room this process is using now. `bind_room` installs one. `current_room` reads it. `using_room` swaps in another for a block of code, then puts the previous one back.

`policy.py`

The time numbers for this start: how long to wait for startup, how long to wait while stopping, how long the process may run, the memory cap, and the heartbeat interval. A negative number is refused. These are host limits. They are not a resource kind in the pool.

`lifecycle.py`

Checks the numbers from `policy.py`. When the clock runs out, it asks the process to stop. When memory is over the cap, it reports that. It does not kill the process. A heartbeat that was required and did not arrive is also reported here.

`shell.py`

Working directory, argv, environment variables, and where stdin, stdout, and stderr are attached. The file remembered by `load env` is `env_file`. Only the names to read are stored. Secret values stay in the file and are not put in the package handed to the process at start. `apply()` checks that those names exist in the file, removes them from the process environment, and reads them later when they are used.

`filesystem.py`

The places this process can see: the workspace, its own files, and a temp directory. Each place has a path and whether it may be written. One place must be named `workspace`. `locate` keeps a path inside an allowed place, or refuses it.

`file_io.py`

The read and write entry. It asks `filesystem.py` whether the path may be touched, then reads or writes. A relative path is resolved from the workspace. A missing parent directory is created on write.

`identity.py`

Who this process is: pid, capability name, and the current file mode. Secrets are stored as names and a file path. `resolve_secret` reads one value from the file at the moment it is used. Names containing `KEY`, `PASSWORD`, `SECRET`, or `TOKEN` are removed before an external program starts.

`compute.py`

Whether an external program may start, in which directory, and for how long. The working directory must sit in an allowed place. When the mode requires a sandbox wrapper and none is attached, the command is refused. The thread pool is [`kernel/thread`](../thread/README.md). This script does not start threads.

`mount.py`

Path rules. The workspace root comes from `--change workspace=`, `workspace_root`, or `cwd`. Otherwise the fallback path is used. Each process has its own temp directory at `.linope-tmp/<pid>` under the project root. The home directory, `.git`, `.ssh`, `.aws`, `.env`, private keys, and certificate files stay out of the view.

`sandbox_vocab.py`

Reads the mode list and the writable-root rules from `capability/sandbox/sandbox/src`. `check_mode` refuses a mode that list does not contain. `confines` says whether a command must be wrapped. `writes` says whether the mode allows writes.

`session_mode.py`

The sandbox mode of the current session. `effective_mode` reads the last `sandbox/mode` record. `remember_mode` appends one record to the turn journal. The journal is [`kernel/trace`](../trace/README.md).

`confine.py`

Hands the workspace root and the file mode to the platform wrapper. `read-only` and `workspace-write` rewrite the command line. `danger-full-access` keeps the original command line. Linux uses bwrap then Landlock, macOS uses Seatbelt, and Windows uses the ACL runner. The wrappers live in [`capability/sandbox`](../../capability/sandbox/README.md).

`__init__.py`

Exports `KernelEnvironment`, `ProcessEnvironment`, `HostExecutionPolicy`, `bind_room`, `current_room`, and `using_room`.

## Known Limitations and Deferred Work

- **The room is fixed at start** — after `apply()`, a later resource claim does not widen the paths or the mode already in use.
