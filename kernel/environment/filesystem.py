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
    """One named place supplied by the sandbox policy."""

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
    scope: str = "workspace"
    policy: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "access_mode", check_access_mode(self.access_mode))
        if not any(root.name == "workspace" for root in self.roots):
            raise ValueError("Filesystem has no workspace")

    def root_path(self, name: str) -> str:
        for root in self.roots:
            if root.name == name:
                return root.path
        raise KeyError(name)

    def allows(self, path: Path, *, write: bool = False) -> bool:
        """Answer whether a path is inside the sandbox-provided view."""
        try:
            self.locate(path, write=write)
        except (PermissionError, ValueError, OSError):
            return False
        return True

    def locate(self, candidate: Path, *, write: bool) -> Path:
        """Normalize a path, then keep it inside an allowed place."""
        own_temp = next((root.path for root in self.roots if root.name == "temp"), "")
        return admit_path(
            candidate,
            tuple((root.path, root.writable) for root in self.roots),
            write=write,
            own_temp=own_temp,
            mode=self.access_mode,
            scope=self.scope,
            blocked_names=tuple(self.policy.get("blocked_names") or ())
            if self.policy
            else (),
            blocked_parts=tuple(self.policy.get("blocked_parts") or ())
            if self.policy
            else (),
            blocked_suffixes=tuple(self.policy.get("blocked_suffixes") or ())
            if self.policy
            else (),
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
        policy = dict(self.policy or {})
        policy["mode"] = mode
        policy["writable_roots"] = [
            root.path for root in roots if root.writable
        ]
        return FilesystemView(
            roots=roots,
            access_mode=mode,
            scope=self.scope,
            policy=policy,
        )

    def payload(self) -> dict[str, Any]:
        return {
            "access_mode": self.access_mode,
            "scope": self.scope,
            "policy": dict(self.policy or {}),
            "roots": [root.payload() for root in self.roots],
        }

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "FilesystemView":
        return cls(
            roots=tuple(
                FilesystemRoot.from_payload(item) for item in payload.get("roots", ())
            ),
            access_mode=str(payload.get("access_mode", "workspace-write")),
            scope=str(payload.get("scope", "workspace")),
            policy=dict(payload.get("policy") or {}),
        )

    @classmethod
    def for_local(
        cls,
        workspace: Path,
        *,
        package_paths: tuple[Path, ...] = (),
        access_mode: str = "workspace-write",
        pid: int = 0,
        policy: dict[str, Any] | None = None,
    ) -> "FilesystemView":
        mode = check_access_mode(access_mode)
        root = workspace.expanduser().resolve()
        workspace_path = str(root)
        has_policy = policy is not None
        resolved_policy = dict(policy or {})
        scope = str(resolved_policy.get("scope") or "workspace")
        if not has_policy:
            resolved_policy = {
                "version": 1,
                "scope": scope,
                "mode": mode,
                "cwd": workspace_path,
                "roots": [workspace_path],
                "writable_roots": (
                    [workspace_path] if mode == "workspace-write" else []
                ),
            }
        policy_roots = [
            str(item)
            for item in resolved_policy.get("roots") or ()
            if str(item).strip()
        ]
        writable = {
            os.path.normcase(str(Path(item).expanduser().resolve()))
            for item in resolved_policy.get("writable_roots") or ()
        }
        roots = [
            FilesystemRoot(
                name="workspace",
                path=workspace_path,
                writable=(
                    mode == "danger-full-access"
                    or not confines(mode)
                    or _is_writable(workspace_path, writable, mode)
                ),
            ),
        ]
        for index, path in enumerate(policy_roots):
            resolved = str(Path(path).expanduser().resolve())
            if os.path.normcase(resolved) == os.path.normcase(workspace_path):
                continue
            roots.append(
                FilesystemRoot(
                    name=f"host-{index}",
                    path=resolved,
                    writable=(
                        mode == "danger-full-access"
                        or not confines(mode)
                        or _is_writable(resolved, writable, mode)
                    ),
                )
            )
        if has_policy:
            temp_base = Path(
                str(resolved_policy.get("temp_root") or private_temp(workspace_path, pid))
            )
            own_temp = str(temp_base / ".linope" / str(pid or "session"))
        else:
            own_temp = private_temp(workspace_path, pid)
        roots.append(
            FilesystemRoot(
                name="temp",
                path=own_temp,
                writable=(
                    mode == "danger-full-access"
                    or not confines(mode)
                    or _is_writable(own_temp, writable, mode)
                ),
            )
        )
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
        return cls(
            roots=tuple(roots),
            access_mode=mode,
            scope=scope,
            policy=resolved_policy,
        )

def _root_writable(mode: str, name: str, path: str, workspace: str) -> bool:
    """Whether one view root is writable under the sandbox's own rules."""
    if name == "package" or not confines(mode):
        return name != "package"
    granted = writable_roots({"mode": mode, "workspace_root": workspace})
    return any(inside(item, Path(path)) for item in granted)


def _is_writable(path: str, granted: set[str], mode: str) -> bool:
    if not confines(mode):
        return True
    if not granted:
        return False
    return any(inside(item, Path(path)) or inside(path, Path(item)) for item in granted)
