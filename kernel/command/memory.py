"""Choose where logical memory is stored. The kernel does not pick a database."""

from __future__ import annotations

from pathlib import Path

from kernel.command.convention import UsageError
from kernel.resource.memory.backends import configured_backend, write_backend_config


USAGE = "usage: linope memory backend [memory | local --path <folder>]"


def run(argv: list[str]) -> int:
    if not argv or argv[0] != "backend":
        raise UsageError(USAGE)
    return _backend(argv[1:])


def _backend(argv: list[str]) -> int:
    if not argv:
        name, path = configured_backend()
        return {"backend": name, "path": path}
    name = argv[0]
    if name not in {"memory", "local"}:
        raise UsageError(USAGE)
    path = ""
    if name == "local":
        if argv[1:2] != ["--path"] or len(argv) != 3 or not argv[2].strip():
            raise UsageError(USAGE)
        path = str(Path(argv[2]))
        Path(path).mkdir(parents=True, exist_ok=True)
    write_backend_config(name, path)
    return {"backend": name, "path": path}
