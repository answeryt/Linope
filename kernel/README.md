# kernel/ — process, resource, and command core

English | [中文](README.cn.md)

The kernel starts capability processes, binds their resource records, and accepts the `linope` commands that talk to those processes. Model cards, tool plugins, and prompt text live in [`capability/`](../capability/README.md).

| Directory | Role |
|---|---|
| [`process/`](process/README.md) | One operating-system pid, one resource record |
| [`command/`](command/README.md) | The `linope` command entry |
| [`resource/`](resource/README.md) | Resource kinds, leases, and handles |
| [`scheduler/`](scheduler/README.md) | Model turns, memory admission, and request routing |
| [`thread/`](thread/README.md) | Async and worker execution inside one process |
| [`load_balancing/`](load_balancing/README.md) | Which peer process or worker receives a request |
| [`communication/`](communication/README.md) | Model pages, checked steps, and caller-supplied channels |
| [`environment/`](environment/README.md) | The room one process may touch |
| [`hypermedia/`](hypermedia/README.md) | Read-only resource pages and the loopback HTTP service |
| [`services/`](services/README.md) | A saved list of process ids |
| [`trace/`](trace/README.md) | Activity trail and the turn journal |
| [`calculate/`](calculate/README.md) | Token pressure and peers on one network channel |
