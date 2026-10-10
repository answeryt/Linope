"""The one room bound inside a capability process."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from kernel.environment.room import KernelEnvironment


_ROOM: KernelEnvironment | None = None


def bind_room(room: KernelEnvironment | None) -> None:
    """Share one room with every thread in this process."""
    global _ROOM
    _ROOM = room


def current_room() -> KernelEnvironment | None:
    return _ROOM


@contextmanager
def using_room(room: KernelEnvironment | None) -> Iterator[KernelEnvironment | None]:
    previous = current_room()
    bind_room(room)
    try:
        yield room
    finally:
        bind_room(previous)
