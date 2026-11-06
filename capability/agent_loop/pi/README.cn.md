# pi/ — 接入 Pi 的代理循环

[English](README.md) | 中文

使用 [Pi](https://github.com/earendil-works/pi) 是为了验证 Linope 内核的灵活性与通用性，验证内核工程范式的可行性。

Pi 是一份已经存在的代理循环。它自己持有工具循环、扩展和会话记录。问模型、启动对等进程、取回结果，都由 [`main.mjs`](main.mjs) 写成内核已经接受的命令行。内核启动这个进程，绑定它的资源记录，并执行交给它的命令。

同一套进程、资源和命令换上 Pi 之后仍然能转。外部循环可以接进来，说明这套内核工程范式可以容纳不同的实现。

| 文件 | 职责 |
|---|---|
| [`main.mjs`](main.mjs) | 一个能力进程。Pi 要问模型时，写成 `process start` 和 `load message` |
| [`loop.mjs`](loop.mjs) | 打开一次 Pi 会话。工具执行、扩展和会话记录是 Pi 的。模型请求由调用方提供 |
| [`../linope.json`](../linope.json) | 启动声明。命令是 `node capability/agent_loop/pi/main.mjs` |

进程、资源和命令在 [`kernel/`](../../../kernel/README.cn.md)。
