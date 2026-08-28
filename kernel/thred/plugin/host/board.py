"""Public lookup board for socket tools and raw leaf modules."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ..exception import NoMatches
from .file_loader import FileModuleLoader
from .module_loader import ModuleLoader
from .socket_loader import SocketLoader


class Board:
    """Expose lookups while keeping Socket and Module policies separate."""

    def __init__(
        self,
        sockets: Mapping[str, Mapping[str, str]],
        modules: Mapping[str, str],
        *,
        repo: Path,
    ) -> None:
        self._files = FileModuleLoader(repo)
        self._socket_loader = SocketLoader(sockets, self._files)
        self._module_loader = ModuleLoader(modules, self._files)

    def get(self, socket: str, name: str) -> Any:
        return self._socket_loader.get(socket, name)

    def module(self, name: str) -> Any:
        """Return a raw leaf module without imposing a composition contract."""
        return self._module_loader.get(name)

    def close(self) -> None:
        """Release modules loaded through this board."""
        self._files.close()


def create_board(
    sockets: Mapping[str, Mapping[str, str]],
    *,
    repo: Path,
    modules: Mapping[str, str] | None = None,
) -> Board:
    return Board(sockets, modules or {}, repo=repo)
