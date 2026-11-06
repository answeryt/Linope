# pi/ — a Pi agent loop on the kernel

English | [中文](README.cn.md)

[Pi](https://github.com/earendil-works/pi) is used here to verify the flexibility and generality of the Linope kernel, and to verify that the kernel engineering paradigm is feasible.

Pi is an existing agent loop. It keeps the tool loop, the extensions, and the transcript. Asking the model, starting a peer process, and reading the result are kernel command lines written by [`main.mjs`](main.mjs). The kernel starts this process, binds its resource record, and runs the command it is given.

The same processes, resources, and commands still turn with Pi in place. An outside loop can be attached, which shows that this kernel engineering paradigm can hold different implementations.

| File | Role |
|---|---|
| [`main.mjs`](main.mjs) | One capability process. A model question becomes `process start` and `load message` |
| [`loop.mjs`](loop.mjs) | Opens one Pi session. Tool execution, extensions, and the transcript are Pi's. The caller supplies the model request |
| [`../linope.json`](../linope.json) | The start declaration. The command is `node capability/agent_loop/pi/main.mjs` |

Processes, resources, and commands are [`kernel/`](../../../kernel/README.md).
