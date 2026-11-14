# linope/ — the agent loop

English | [中文](README.cn.md)

 One user message is one turn. Inside the turn the loop asks the model, and if the model asks for a tool it runs that tool and asks again. A reply with no tool call ends the turn.

The loop does not call a provider, read a file, or run a shell. It writes the command lines the kernel already accepts. The kernel starts the peer, runs the line, and writes the text back.

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
process starts.

Tool calls run one at a time, in the order the model gave them. The command door accepts one line and returns one result. A command error comes back as the tool result, and the loop asks the model again.

The loop keeps its own messages and sends them in each `model run`; the model
does not own a memory or a pid.

| File | Role |
|---|---|
| [`__main__.py`](__main__.py) | One capability process. It speaks the stdin door and writes command lines |
| [`loop.py`](loop.py) | The turn. It decides whether the next line asks the model or runs a tool |
| [`../linope.json`](../linope.json) | The start declaration. The command is `python -m capability.agent_loop.linope` |

Processes, resources, and commands are [`kernel/`](../../../kernel/README.md).
