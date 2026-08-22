# -*- coding: utf-8 -*-
"""Reload the agent worker when Python files change.

watchfiles is imported inside run so the plugin loads without it.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any


PLUGIN_NAME = "kernel_watchfiles"
PLUGIN_VERSION = "1.0"


def watch_and_reload(
    *,
    target: Callable[..., Any],
    reload_dirs: Sequence[str | Path],
    extra_extensions: Sequence[str] = (),
    logger: logging.Logger | None = None,
) -> None:
    """Block, call target, restart it when watched files change."""
    try:
        import watchfiles
    except ImportError as exc:
        raise RuntimeError("watchfiles is required for --reload") from exc

    log = logger or logging.getLogger(PLUGIN_NAME)
    dirs = [str(path) for path in reload_dirs]
    log.info("watching for changes in %s", dirs)

    from multiprocessing import Process

    process = Process(target=target, name="agent-reload-worker")
    process.start()
    try:
        for changes in watchfiles.watch(
            *dirs,
            watch_filter=watchfiles.PythonFilter(extra_extensions=tuple(extra_extensions)),
        ):
            names = {Path(item[1]).name for item in changes}
            log.info("reload after change in %s", ", ".join(sorted(names)))
            if process.is_alive():
                process.terminate()
                process.join(timeout=10)
                if process.is_alive():
                    process.kill()
            process = Process(target=target, name="agent-reload-worker")
            process.start()
    except KeyboardInterrupt:
        pass
    finally:
        if process.is_alive():
            process.terminate()
            process.join(timeout=10)
