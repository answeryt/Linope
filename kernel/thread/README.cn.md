# thread

[English](README.md) | 中文

进程和线程都是 task。进程是线程组组长，id 使用它的 pid；同组线程是后续的 task。每条 task 都有自己的程序计数器、寄存器和状态，并指向线程组共享的那份资源账本。模型调度只在 task 之间切换，不必先问这是换进程还是换线程。

同一个进程可以有多条 task。它们共用那份记忆、文件和网络。账本不记下程序计数器。进程停掉时，同组 task 一起丢掉。

## 脚本

| 脚本 | 作用 |
|---|---|
| `task.py` | `Task` 是进程组长或同组线程。`ThreadTable` 是一个进程名下的 task 组。第一条组长 task 和进程一起出生。 |
| `contracts.py` | 对外说出 `Task` 和 `ThreadTable` 这两个名字。 |
| `__init__.py` | 第一次用到某个名字时才导出。 |

程序计数器目前用这些名字：`idle`、`ask_model`、`using_model`、`wait_tool`、`wait_helpers`、`answer`、`done`。寄存器只放下一步要用的小抄，例如用户原话、要跑的命令、工具名字。长对话仍留在进程的记忆里。组长 task 的 `tgid` 等于 pid，同组 task 的 `tgid` 相同。
