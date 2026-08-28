# -*- coding: utf-8 -*-
"""Parse the ui flag family. Does not bind a port or open a browser."""

from __future__ import annotations

import argparse
from typing import Any


PLUGIN_NAME = "ui_startup"
PLUGIN_VERSION = "1.0"

ALL_INTERFACES_HOST = "0.0.0.0"
ALL_INTERFACES_ERROR = (
    "error: --host 0.0.0.0 is intentionally not supported yet for safety: "
    "it would expose remote code execution to the network; use 127.0.0.1 instead"
)


def _port(value: str) -> int:
    if not value.isdigit():
        raise argparse.ArgumentTypeError(
            f"error: --port must be a number, got {value!r}"
        )
    number = int(value)
    if number > 65535:
        raise argparse.ArgumentTypeError(
            f"error: --port must be at most 65535, got {number}"
        )
    return number


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ui",
        description="Serve the Linope browser UI.",
    )
    parser.add_argument("--host", help="bind host")
    parser.add_argument(
        "--port",
        type=_port,
        help="listen port; pass 0 to let the OS pick a free one",
    )
    parser.add_argument(
        "--trusted-host",
        action="append",
        default=[],
        dest="trusted_hosts",
        metavar="authority",
        help="extra authority the browser-trust fence accepts (repeatable)",
    )
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="print the URL but do not open the default browser",
    )
    return parser


def parse_startup(argv: list[str] | None = None) -> dict[str, Any]:
    """Return the flags this invocation named. Help and usage errors exit."""
    args = build_parser().parse_args(argv)
    if args.host == ALL_INTERFACES_HOST:
        raise SystemExit(ALL_INTERFACES_ERROR)
    return {
        "host": args.host,
        "port": args.port,
        "trusted_hosts": list(args.trusted_hosts or ()),
        "no_open": bool(args.no_open),
    }
