"""Resource HTTP service command."""

from __future__ import annotations

from kernel.command.convention import UsageError, guard, parse
from kernel.command.events import KernelEvent, current_event_sink

USAGE = "usage: linope resource serve"


@guard(USAGE)
def run(argv: list[str]) -> int:
    if not argv:
        raise UsageError(USAGE)
    action, rest = argv[0], argv[1:]
    if action == "serve":
        return _serve(rest)
    raise UsageError(USAGE)


_SERVE = "usage: linope resource serve [--host 127.0.0.1] [--port 0]"


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
        raise UsageError("--port must be between 0 and 65535")
    from kernel.hypermedia.http_server import serve_resources

    def announce(actual_host: str, actual_port: int) -> None:
        current_event_sink().emit(
            KernelEvent(
                "resource.started",
                {"host": actual_host, "port": actual_port},
            )
        )

    serve_resources("", host=host, port=port, on_started=announce)
    return {"host": host, "port": port}

