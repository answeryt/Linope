"""Select interchangeable tools through named sockets."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..exception import NoMatches
from .file_loader import FileModuleLoader


class SocketLoader:
    """Resolve ``(socket, name)`` and enforce the socket callable contract."""

    def __init__(
        self,
        sockets: Mapping[str, Mapping[str, str]],
        files: FileModuleLoader,
    ) -> None:
        self._sockets = sockets
        self._files = files

    def get(self, socket: str, name: str) -> Any:
        plugs = self._sockets.get(socket)
        if not isinstance(plugs, Mapping) or name not in plugs:
            raise NoMatches(f"no plug {name!r} on socket {socket!r}")
        return self._files.load(
            f"socket:{socket}",
            name,
            plugs[name],
            required="dispatch",
        )
