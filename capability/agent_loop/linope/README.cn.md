# linope/ — 代理循环

[English](README.md) | 中文

一条用户消息是一轮。这一轮里，循环问模型；模型要工具，就执行那个工具再问一次。回复里没有工具调用，并且没有还在跑的工具，这一轮结束。

循环不调用提供商，不读文件，也不跑 shell。它也不导入内核的调度器。复用方式是命令行：写出一行，读回执。内核启动对等进程，执行这一行，再把文字送回来。多个工具由内核一起跑，循环不自己依次执行。

| 步骤 | 命令行 |
|---|---|
| 安装模型卡片 | `model use <模型卡片>` |
| 问模型 | `model run -- <消息和工具>` |
| 工具还没起来 | `process start <工具>` |
| 执行工具 | `load tool <进程号> -- <JSON>` |

工具的 `process start` 和 `load tool` 用的是 `CommandOffer` 的指针。模型卡片由 `model use` 安装，不是进程。模型看到的是聊天接口接受的函数名。能力名里的点换成下划线，所以 `tools.read` 以 `tools_read` 传出去。循环仍按能力名启动工具进程。参数来自能力表里已经写好的 schema。配置里点了名、表里却没有 schema 的工具，会在这个进程启动时失败。

多个工具一起跑。内核每完成一份，就写回这一份信号。循环按这份信号写下一行 `model run`，不等其余的份。命令出错时，错误文本当作这份结果。

循环进程自己持有 `messages`，每次 `model run` 把当前消息寄存器交给模型。模型没有 pid，也没有自己的 memory。

| 文件 | 职责 |
|---|---|
| [`__main__.py`](__main__.py) | 一个能力进程。它守着 stdin，并写出命令行 |
| [`loop.py`](loop.py) | 这一轮。它决定下一行是问模型还是执行工具 |
| [`../linope.json`](../linope.json) | 启动声明。命令是 `python -m capability.agent_loop.linope` |

进程、资源和命令在 [`kernel/`](../../../kernel/README.cn.md)。
