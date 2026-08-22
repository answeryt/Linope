# -*- coding: utf-8 -*-
"""CLI entry for the agent microservice.

create_app / spawn_workers / watch_reload are injected so this file does
not import app, multiprocess, or watchfiles siblings.
"""

from __future__ import annotations

import argparse
import asyncio
import inspect
import logging
from collections.abc import Callable
from typing import Any


PLUGIN_NAME = "kernel_cli"
PLUGIN_VERSION = "1.0"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the agent microservice worker.")
    parser.add_argument(
        "-w",
        "--workers",
        type=int,
        default=1,
        help="Number of worker processes (default 1).",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Restart the worker when Python files change.",
    )
    parser.add_argument(
        "--reload-dir",
        action="append",
        default=[],
        help="Directory to watch with --reload. Repeatable.",
    )
    return parser


def _run_app(app: Any) -> None:
    run = getattr(app, "run")
    result = run()
    if inspect.isawaitable(result):
        asyncio.run(result)


def run_cli(
    *,
    create_app: Callable[..., Any],
    spawn_workers: Callable[..., Any] | None = None,
    watch_reload: Callable[..., Any] | None = None,
    argv: list[str] | None = None,
) -> int:
    """Start one worker, many workers, or a reloading worker."""
    if create_app is None:
        raise TypeError("create_app is required")
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO)

    if args.reload and args.workers > 1:
        raise SystemExit("cannot combine --reload with --workers > 1")

    def _target(**_kwargs: Any) -> None:
        _run_app(create_app())

    if args.reload:
        if watch_reload is None:
            raise SystemExit("watch_reload must be injected to use --reload")
        watch_reload(
            target=_target,
            reload_dirs=args.reload_dir or ["."],
        )
        return 0
    if args.workers > 1:
        if spawn_workers is None:
            raise SystemExit("spawn_workers must be injected to use --workers")
        spawn_workers(target=_target, workers=args.workers)
        return 0
    _target()
    return 0
