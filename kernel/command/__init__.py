"""Command-line entry for the kernel.

Submodules are imported explicitly. ``main`` and ``parse_start`` are the
public names tests and ``python -m kernel.command`` use.
"""

from __future__ import annotations

__all__ = ["main", "parse_start"]


def __getattr__(name: str):
    if name == "main":
        from kernel.command.dispatch import main

        return main
    if name == "parse_start":
        from kernel.command.process.start import parse_start

        return parse_start
    raise AttributeError(name)
