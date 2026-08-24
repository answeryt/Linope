# -*- coding: utf-8 -*-
"""Process entry: inject the ui plugins and serve frontend dist."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent


def load(relative: str) -> Any:
    path = HERE / relative
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)
    startup = load("startup/ui_startup_plugin.py")
    server = load("server/ui_server_plugin.py")
    shell = load("api/ui_shell_plugin.py")
    static = load("static/ui_static_plugin.py")
    opening = load("open/ui_open_plugin.py")
    cli = load("cli/ui_cli_plugin.py")
    return int(
        cli.run_cli(
            parse_startup=startup.parse_startup,
            create_server=server.create_server,
            mount_shell=shell.mount_shell,
            mount_static=static.mount_static,
            announce=opening.announce,
            resolve_dist_index=static.resolve_dist_index,
            argv=sys.argv[1:] if argv is None else argv,
        )
    )


if __name__ == "__main__":
    raise SystemExit(run())
