# -*- coding: utf-8 -*-
"""Print the ready URL and open the default browser unless suppressed."""

from __future__ import annotations

import os
import socket
import webbrowser
from collections.abc import Callable, Mapping, Sequence
from typing import Any


PLUGIN_NAME = "ui_open"
PLUGIN_VERSION = "1.0"

LOOPBACK_HOST = "127.0.0.1"
ALL_INTERFACES_HOST = "0.0.0.0"


def local_url(port: int, *, host: str = LOOPBACK_HOST) -> str:
    return f"http://{host}:{int(port)}"


def lan_ipv4_addresses() -> list[str]:
    found: list[str] = []
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            address = sock.getsockname()[0]
            if address and not address.startswith("127."):
                found.append(address)
    except OSError:
        pass
    return found


def resolve_lan_trust(
    bind_host: str,
    extra: Sequence[str] | None = None,
) -> dict[str, list[str]]:
    lan_addresses = lan_ipv4_addresses() if bind_host == ALL_INTERFACES_HOST else []
    extras = [str(item) for item in extra or ()]
    return {
        "lan_addresses": lan_addresses,
        "trusted_hosts": [*lan_addresses, *extras],
    }


def format_ready_line(port: int, lan_addresses: Sequence[str] = ()) -> str:
    local = local_url(port)
    if not lan_addresses:
        return f"ui: {local}"
    return f"ui: {local} (LAN: http://{lan_addresses[0]}:{int(port)})"


def should_open_browser(
    env: Mapping[str, str] | None = None,
    *,
    no_open: bool = False,
) -> bool:
    if no_open:
        return False
    facts = env if env is not None else os.environ
    if facts.get("SSH_CONNECTION") or facts.get("SSH_TTY"):
        return False
    return True


def open_browser(
    url: str,
    *,
    open_url: Callable[[str], Any] | None = None,
) -> bool:
    opener = open_url if open_url is not None else webbrowser.open
    return bool(opener(url))


def announce(
    *,
    host: str,
    port: int,
    trusted_hosts: Sequence[str] = (),
    no_open: bool = False,
    print_fn: Callable[[str], Any] = print,
    open_url: Callable[[str], Any] | None = None,
    env: Mapping[str, str] | None = None,
) -> str:
    runtime = resolve_lan_trust(host, trusted_hosts)
    print_fn(format_ready_line(port, runtime["lan_addresses"]))
    url = local_url(port)
    if should_open_browser(env, no_open=no_open):
        open_browser(url, open_url=open_url)
    return url
