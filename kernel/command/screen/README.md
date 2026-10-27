# screen

English | [中文](README.cn.md)

Two scripts. They do not call each other.

`resource.py` is the `linope resource` command. It starts a local HTTP server so a developer can open resource pages in a browser on this machine. `live_stream.py` prints one piece of a model reply to the terminal while the reply is still arriving.

Page links, the `409` for a stale link, and the HTTP handler live in [`kernel/hypermedia`](../../hypermedia/README.md). This directory only starts that server, or prints a text fragment.

## `resource.py`

[`dispatch.py`](../dispatch.py) registers `run` as the `resource` command. The only subcommand is `serve`:

```text
linope resource serve [--host 127.0.0.1] [--port 0]
```

`run` reads the first word. Missing arguments, or any word other than `serve`, print the usage line and exit 2.

`_serve` parses `--host` and `--port`, then calls `serve_resources` in `kernel/hypermedia/http_server.py`. The store path passed in is empty. An empty path means: use `LINOPE_RESOURCE_STORE` if it is set, otherwise the `resource_store` value in the project config, otherwise `file:.linope/resources.json`.

The call blocks in `serve_forever` until the process is stopped. On startup the server prints `Resource service listening on <host>:<port>` and writes `http-server.json` next to the store, with host, port, pid, and the store locator. When the process exits, that file is removed.

| Flag | Default | Meaning |
|---|---|---|
| `--host` | `127.0.0.1` | Bind address. `serve_resources` accepts only `127.0.0.1`, `localhost`, and `::1`. |
| `--port` | `0` | TCP port. `0` asks the operating system for a free port. A value outside `0`–`65535` is a usage error and exits 2. |

These cases print the exception on stderr and exit 1:

- `--host` is not one of the three loopback names (`ValueError`)
- the resolved store is a `memory:` store (`ValueError`)
- `http-server.json` already records a running server for that store (`RuntimeError`)
- the socket cannot be opened (`OSError`)

## `live_stream.py`

`publish_text(text)` prints one JSON line and flushes it:

```json
{"type": "text-delta", "text": "..."}
```

Two callers use it so a fragment shows up before the whole reply is finished:

- `capability/model/model_runtime/model_main.py` `_forward_display`, when a stream part has type `text` or `text-delta` and a non-empty `text`
- `kernel/command/process/listen.py` `_show_notice`, when a notice dict has a non-empty `text`

A finished reply is still printed by the caller. `publish_text` only emits the fragment. It does not open a socket and does not write a file.
