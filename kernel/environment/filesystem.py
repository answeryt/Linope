"""Named places a process can see: workspace, its own files, and temp."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kernel.environment.identity import check_access_mode
from kernel.environment.mount import admit_path, inside, private_temp
from kernel.environment.sandbox_vocab import confines, writable_roots


@dataclass(frozen=True)
class FilesystemRoot:
    """One named place. Home and secret files are not roots."""

    name: str
    path: str
    writable: bool

    def payload(self) -> dict[str, Any]:
        return {"name": self.name, "path": self.path, "writable": self.writable}

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "FilesystemRoot":
        return cls(
            name=str(payload["name"]),
            path=str(payload["path"]),
            writable=bool(payload["writable"]),
        )


@dataclass(frozen=True)
class FilesystemView:
    """The places this process is allowed to touch."""

    roots: tuple[FilesystemRoot, ...]
    access_mode: str = "workspace-write"

    def __post_init__(self) -> None:
        object.__setattr__(self, "access_mode", check_access_mode(self.access_mode))
        if not any(root.name == "workspace" for root in self.roots):
            raise ValueError("Filesystem has no workspace")

    def root_path(self, name: str) -> str:
        for root in self.roots:
            if root.name == name:
                return root.path
        raise KeyError(name)

    def locate(self, candidate: Path, *, write: bool) -> Path:
        """Normalize a path, then keep it inside an allowed place."""
        own_temp = next((root.path for root in self.roots if root.name == "temp"), "")
        return admit_path(
            candidate,
            tuple((root.path, root.writable) for root in self.roots),
            write=write,
            own_temp=own_temp,
            mode=self.access_mode,
        )

    def with_access_mode(self, access_mode: str) -> "FilesystemView":
        mode = check_access_mode(access_mode)
        workspace = self.root_path("workspace")
        roots = tuple(
            FilesystemRoot(
                name=root.name,
                path=root.path,
                writable=_root_writable(mode, root.name, root.path, workspace),
            )
            for root in self.roots
        )
        return FilesystemView(roots=roots, access_mode=mode)

    def payload(self) -> dict[str, Any]:
        return {
            "access_mode": self.access_mode,
            "roots": [root.payload() for root in self.roots],
        }

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "FilesystemView":
        return cls(
            roots=tuple(
                FilesystemRoot.from_payload(item) for item in payload.get("roots", ())
            ),
            access_mode=str(payload.get("access_mode", "workspace-write")),
        )

    @classmethod
    def for_local(
        cls,
        workspace: Path,
        *,
        package_paths: tuple[Path, ...] = (),
        access_mode: str = "workspace-write",
        pid: int = 0,
    ) -> "FilesystemView":
        mode = check_access_mode(access_mode)
        root = workspace.expanduser().resolve()
        workspace_path = str(root)
        roots = [
            FilesystemRoot(
                name="workspace",
                path=workspace_path,
                writable=_root_writable(mode, "workspace", workspace_path, workspace_path),
            ),
            FilesystemRoot(
                name="temp",
                path=private_temp(workspace_path, pid),
                writable=_root_writable(
                    mode,
                    "temp",
                    private_temp(workspace_path, pid),
                    workspace_path,
                ),
            ),
        ]
        seen: set[str] = set()
        for package in package_paths:
            directory = package if package.is_dir() else package.parent
            if not directory.is_dir():
                continue
            resolved = directory.resolve()
            if os.path.normcase(str(resolved)) == os.path.normcase(str(root)):
                continue
            key = os.path.normcase(str(resolved))
            if key in seen:
                continue
            seen.add(key)
            roots.append(
                FilesystemRoot(name="package", path=str(resolved), writable=False)
            )
        return cls(roots=tuple(roots), access_mode=mode)


def _root_writable(mode: str, name: str, path: str, workspace: str) -> bool:
    """Whether one view root is writable under the sandbox's own rules."""
    if name == "package" or not confines(mode):
        return name != "package"
    granted = writable_roots({"mode": mode, "workspace_root": workspace})
    return any(inside(item, Path(path)) for item in granted)
