"""Start one capability process without keeping a parent handle on it."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


_ROOT = Path(__file__).resolve().parents[3]


def launch_detached(store_locator: str, process_id: str) -> int:
    """Start the capability and return its pid. The caller does not signal it."""
    command = [
        sys.executable,
        "-m",
        "kernel.process.process_runtime.serve",
        "--store",
        str(store_locator),
        "--process-id",
        process_id,
    ]
    kwargs: dict = {
        "cwd": str(_ROOT),
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "close_fds": True,
    }
    if sys.platform == "win32":
        detached = 0x00000008
        new_group = 0x00000200
        breakaway = 0x01000000
        try:
            process = subprocess.Popen(
                command,
                creationflags=detached | new_group | breakaway,
                **kwargs,
            )
        except OSError:
            process = subprocess.Popen(
                command,
                creationflags=detached | new_group,
                **kwargs,
            )
    else:
        process = subprocess.Popen(command, start_new_session=True, **kwargs)
    return int(process.pid)
