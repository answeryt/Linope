"""Resource HTTP service command."""

from __future__ import annotations

import sys

from kernel.command.convention import UsageError, guard, parse
from kernel.command.file import run as file_run
from kernel.hypermedia.http_server import serve_resources
from kernel.resource.store.network import plan_serve, save_network

USAGE = "用法: linope resource serve|file ..."


@guard(USAGE)
def run(argv: list[str]) -> int:
    if not argv:
        raise UsageError(USAGE)
    action, rest = argv[0], argv[1:]
    if action == "serve":
        return _serve(rest)
    if action == "file":
        return file_run(rest)
    raise UsageError(USAGE)


_SERVE = (
    "用法: linope resource serve [--mode local|private] [--host 127.0.0.1] [--port 0] "
    "[--public-base-url http://10.0.0.10:49152] [--allow <地址>]"
)


def _serve(argv: list[str]) -> int:
    invocation = parse(
        argv,
        flags={"host": "str", "port": "int", "mode": "str", "public-base-url": "str", "allow": "repeat"},
        usage=_SERVE,
    )
    if invocation.position:
        raise UsageError(_SERVE)
    host = str(invocation.options.get("host") or "127.0.0.1")
    port = 0 if invocation.options.get("port") is None else int(invocation.options["port"])
    mode = str(invocation.options.get("mode") or "local")
    public = str(invocation.options.get("public-base-url") or "")
    allow = tuple(str(item) for item in invocation.options.get("allow") or ())
    if port < 0 or port > 65535:
        raise UsageError("--port 要在 0 到 65535 之间")
    try:
        plan_serve(
            invocation.store,
            mode=mode,
            host=host,
            port=port,
            public_base_url=public,
            allow=allow,
        )
        if invocation.options.get("mode") or public:
            save_network(mode, public)
        serve_resources(
            invocation.store,
            host=host,
            port=port,
            mode=mode,
            public_base_url=public,
            allow=allow,
        )
    except (OSError, RuntimeError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0

