# linope/ — the agent loop

English | [中文](README.cn.md)

One user message is one turn. Inside the turn the loop asks the model, and if the model asks for a tool it runs that tool and asks again. A reply with no tool call, and no tool still running, ends the turn.

The loop does not call a provider, read a file, or run a shell. It does not import the kernel scheduler. It writes a command line and reads the reply. The kernel starts the peer, runs the line, and writes the text back. Several tools run together; the loop does not run them one by one.

| Step | Command line |
|---|---|
| Install a model card | `model use <model card>` |
| Ask the model | `model run -- <messages and tools>` |
| A tool is not up | `process start <tool>` |
| Run a tool | `load tool <pid> -- <JSON>` |

Tool `process start` and `load tool` are the pointers from `CommandOffer`.
Model cards are installed with `model use`; the model has no pid. The model
sees a function name the chat API accepts. A dot in the capability name
becomes an underscore, so `tools.read` is sent as `tools_read`. The loop still
starts tools by capability name. The parameters are the schemas already stored
in the capability table. A configured tool with no schema fails when this
process starts. `tools.mcp_tool_manager` names MCPHub. After `ready`, the
process asks MCPHub for the tools it is serving and installs them before
`prepare`. The loop then starts that capability like any other tool, and the
call body is the remote tool name plus the arguments. When MCPHub is down,
the turn fails and the process stays ready.

Several tools run together. The kernel numbers each tool thread and keeps the call id in its registers. Each finished tool comes back as one signal, and the loop writes the next `model run` without waiting for the rest. Finished results that are still queued come back before that model run starts. A command error is that tool's result.

The turn in progress holds its own messages. When the turn ends, the tool calls and tool results go to the kernel and are written into this process's memory, ahead of the final answer. The next turn starts with one `show` and reads the rows that have already finished. A user row with no model or tool row after it is not history yet. The model has no pid and no memory of its own.

One process can hold several turns. Each turn has its own messages, phase, and program counter. The process shares the tool processes and whether the model card is installed. The `ready` line carries `threads: true`.

| File | Role |
|---|---|
| [`__main__.py`](__main__.py) | One capability process. It keeps the stdin door and returns each command result to the turn named by `thread` |
| [`loop.py`](loop.py) | The turn. It decides whether the next line asks the model or runs a tool |
| [`../linope.json`](../linope.json) | The start declaration. The command is `python -m capability.agent_loop.linope` |

Processes, resources, and commands are [`kernel/`](../../../kernel/README.md).
