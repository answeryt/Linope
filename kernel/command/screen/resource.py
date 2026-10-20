"""Resource HTTP service command."""

from __future__ import annotations

import sys

from kernel.command.convention import UsageError, guard, parse

USAGE = "用法: linope resource serve"


@guard(USAGE)
def run(argv: list[str]) -> int:
    if not argv:
        raise UsageError(USAGE)
    action, rest = argv[0], argv[1:]
    if action == "serve":
        return _serve(rest)
    raise UsageError(USAGE)


_SERVE = "用法: linope resource serve [--host 127.0.0.1] [--port 0]"


def _serve(argv: list[str]) -> int:
    invocation = parse(
        argv,
        flags={"host": "str", "port": "int"},
        usage=_SERVE,
    )
    if invocation.position:
        raise UsageError(_SERVE)
    host = str(invocation.options.get("host") or "127.0.0.1")
    port = 0 if invocation.options.get("port") is None else int(invocation.options["port"])
    if port < 0 or port > 65535:
        raise UsageError("--port 要在 0 到 65535 之间")
    from kernel.hypermedia.http_server import serve_resources

    try:
        serve_resources(
            "",
            host=host,
            port=port,
        )
    except (OSError, RuntimeError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0

