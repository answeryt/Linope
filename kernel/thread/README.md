# thread

English | [中文](README.cn.md)

Processes and threads are tasks. A process is the thread-group leader and
uses its pid as the task id; later sibling threads are other tasks in the
same group. Each task has its own program counter, registers, and state, and
points at the group's shared resource ledger. The model scheduler switches
tasks and does not first ask whether that is a change of process or thread.

One process may have several tasks. They share that process's memory, files,
and network. The ledger does not store the program counter. When the process
stops, its task group goes with it.

## Scripts

| Script | Role |
|---|---|
| `task.py` | `Task` is a process leader or sibling thread. `ThreadTable` is the task group of one process. The leader task is created with the process. |
| `contracts.py` | Names `Task` and `ThreadTable` for other modules. |
| `__init__.py` | Exports a name the first time it is used. |

The program counter uses these names for now: `idle`, `ask_model`, `using_model`, `wait_tool`, `wait_helpers`, `answer`, `done`. The registers hold only the short notes the next step needs, such as the user's sentence, the command to run, and the tool name. The long conversation stays in process memory. The leader's `tgid` is its pid, and sibling tasks share that `tgid`.
