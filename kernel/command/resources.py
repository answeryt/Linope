"""Resource HTTP service command."""

from __future__ import annotations

import sys

from kernel.command.parser import resource_store_path
from kernel.command.protocol import CommandSpec
from kernel.process.hypermedia.http_server import serve_resources


def run(argv: list[str]) -> int:
    rest, store_path = resource_store_path(list(argv))
    if not rest or rest[0] != "serve":
        raise SystemExit(
            "resources 的写法是：resources serve [--host 127.0.0.1] [--port 0]"
        )
    rest = rest[1:]
    host = "127.0.0.1"
    port = 0
    index = 0
    while index < len(rest):
        token = rest[index]
        if token == "--host":
            if index + 1 >= len(rest):
                raise SystemExit("--host 后面要写地址")
            host = rest[index + 1]
            index += 2
            continue
        if token.startswith("--host="):
            host = token.split("=", 1)[1]
            index += 1
            continue
        if token == "--port":
            if index + 1 >= len(rest):
                raise SystemExit("--port 后面要写端口")
            raw_port = rest[index + 1]
            index += 2
        elif token.startswith("--port="):
            raw_port = token.split("=", 1)[1]
            index += 1
        else:
            raise SystemExit(
                "resources 的写法是：resources serve [--host 127.0.0.1] [--port 0]"
            )
        try:
            port = int(raw_port)
        except ValueError:
            raise SystemExit("--port 必须是整数") from None
        if not 0 <= port <= 65535:
            raise SystemExit("--port 必须在 0 到 65535 之间")
    try:
        serve_resources(store_path, host=host, port=port)
    except (OSError, RuntimeError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0


SPEC = CommandSpec(name="resources", run=run)
