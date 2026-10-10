"""Read and write only after the path sits inside an allowed place."""

from __future__ import annotations

import os
from pathlib import Path

from kernel.environment.filesystem import FilesystemView


class FileDoor:
    """Checked open, read, and write for one filesystem view."""

    def __init__(self, filesystem: FilesystemView) -> None:
        self.filesystem = filesystem

    def resolve(self, path: str, *, write: bool, base: str | None = None) -> Path:
        if not path or "\x00" in path:
            raise ValueError("路径无效")
        raw = Path(path)
        if not raw.is_absolute():
            raw = self._anchor(base) / raw
        return self.filesystem.locate(raw, write=write)

    def read_text(self, path: str, *, base: str | None = None) -> str:
        return self.resolve(path, write=False, base=base).read_text(encoding="utf-8")

    def write_text(self, path: str, content: str, *, base: str | None = None) -> Path:
        target = self.resolve(path, write=True, base=base)
        parent = self.filesystem.locate(target.parent, write=True)
        parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return target

    def _anchor(self, base: str | None) -> Path:
        if base:
            return self.filesystem.locate(Path(base), write=False)
        return Path(self.filesystem.root_path("workspace"))


def door_for(room: object | None, workspace: str | None) -> FileDoor:
    """Use the process room, or a workspace-sized door when no room is bound."""
    if room is not None:
        return room.file_io  # type: ignore[attr-defined]
    root = Path(workspace or os.getenv("TERMINAL_CWD") or os.getcwd())
    root = root.expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"工作区不是目录: {root}")
    return FileDoor(FilesystemView.for_local(root))
