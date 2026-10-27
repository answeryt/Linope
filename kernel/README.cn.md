# kernel/ — 进程、资源与命令核心

[English](README.md) | 中文

内核启动能力进程，绑定它们的资源记录，并接受与这些进程对话的 `linope` 命令。模型卡片、工具插件和提示词文本在 [`capability/`](../capability/README.cn.md)。

| 目录 | 职责 |
|---|---|
| [`process/`](process/README.cn.md) | 一个操作系统 `pid`，一份资源记录 |
| [`command/`](command/README.cn.md) | `linope` 命令入口 |
| [`resource/`](resource/README.cn.md) | 资源种类、租约与句柄 |
| [`scheduler/`](scheduler/README.cn.md) | 模型回合、记忆准入与请求路由 |
| [`thread/`](thread/README.cn.md) | 一个进程内部的异步与工作线程执行 |
| [`load_balancing/`](load_balancing/README.cn.md) | 哪一个对等进程或工作线程接收请求 |
| [`communication/`](communication/README.cn.md) | 模型页、已检查的步骤，以及调用方提供的通道 |
| [`environment/`](environment/README.cn.md) | 一个进程可以触及的房间 |
| [`hypermedia/`](hypermedia/README.cn.md) | 只读资源页与回环 HTTP 服务 |
| [`services/`](services/README.cn.md) | 一份已保存的进程号列表 |
| [`trace/`](trace/README.cn.md) | 活动轨迹与回合日志 |
| [`calculate/`](calculate/README.cn.md) | token 压力，以及同一网络通道上的其他进程 |
