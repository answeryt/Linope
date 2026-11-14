# screen

English | [中文](README.cn.md)

`resource.py` is the `linope resource` command. It starts a local HTTP server so a developer can open resource pages in a browser on this machine.

Page links, the `409` for a stale link, and the HTTP handler live in [`kernel/hypermedia`](../../hypermedia/README.md). This directory only starts that server. The command returns structured facts; the host decides how to show them.

## `resource.py`

[`dispatch.py`](../dispatch.py) registers `run` as the `resource` command. The only subcommand is `serve`:

```text
linope resource serve [--host 127.0.0.1] [--port 0]
```

`run` reads the first word. Missing arguments, or any word other than `serve`, raise `UsageError`. The terminal host turns that into exit code 2.

`_serve` parses `--host` and `--port`, then calls `serve_resources` in `kernel/hypermedia/http_server.py`. The store path passed in is empty. An empty path means: use `LINOPE_RESOURCE_STORE` if it is set, otherwise the `resource_store` value in the project config, otherwise `file:.linope/resources.json`.

The call blocks in `serve_forever` until the process is stopped. On startup the server emits a structured `resource.started` fact (`host`, `port`) and writes `http-server.json` next to the store, with host, port, pid, and the store locator. When the process exits, that file is removed.

| Flag | Default | Meaning |
|---|---|---|
| `--host` | `127.0.0.1` | Bind address. `serve_resources` accepts only `127.0.0.1`, `localhost`, and `::1`. |
| `--port` | `0` | TCP port. `0` asks the operating system for a free port. A value outside `0`–`65535` is a usage error. The terminal host exits 2. |

These cases raise. The terminal host prints the message and exits 2:

- `--host` is not one of the three loopback names (`ValueError`)
- the resolved store is a `memory:` store (`ValueError`)
- `http-server.json` already records a running server for that store (`RuntimeError`)
- the socket cannot be opened (`OSError`)

## Display bytes

The kernel does not copy process standard error into a window. Command results remain structured values returned to the host.
