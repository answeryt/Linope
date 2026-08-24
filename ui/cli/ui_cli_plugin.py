# -*- coding: utf-8 -*-
"""Compose startup, server, static serving, and browser open.

parse_startup / create_server / mount_shell / mount_static / announce /
resolve_dist_index are injected so this file never imports sibling plugins.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


PLUGIN_NAME = "ui_cli"
PLUGIN_VERSION = "1.0"

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 4080


def run_cli(
    *,
    parse_startup: Callable[..., dict[str, Any]],
    create_server: Callable[..., Any],
    mount_shell: Callable[..., None],
    mount_static: Callable[..., None],
    announce: Callable[..., str],
    resolve_dist_index: Callable[..., str],
    argv: list[str] | None = None,
    wait: bool = True,
) -> int:
    """Bind the UI, print the URL, and open the browser unless flags say otherwise."""
    if parse_startup is None or create_server is None:
        raise TypeError("parse_startup and create_server are required")
    if mount_shell is None or mount_static is None or announce is None:
        raise TypeError("mount_shell, mount_static, and announce are required")
    if resolve_dist_index is None:
        raise TypeError("resolve_dist_index is required")

    startup = parse_startup(argv)
    host = startup.get("host") or DEFAULT_HOST
    port = DEFAULT_PORT if startup.get("port") is None else int(startup["port"])
    dist_index = resolve_dist_index()
    server = create_server(host=host, port=port)
    mount_shell(register=server.register)
    mount_static(
        register_fallback=server.register_fallback,
        apply_index_taps=server.apply_index_taps,
        dist_index=dist_index,
    )
    listened = server.listen()
    announce(
        host=server.host,
        port=listened,
        trusted_hosts=list(startup.get("trusted_hosts") or ()),
        no_open=bool(startup.get("no_open")),
    )
    if wait:
        try:
            server.wait()
        except KeyboardInterrupt:
            server.close()
            return 0
    return 0
