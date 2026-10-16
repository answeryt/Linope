"""Whether this room may start an external program.

Worker counts and which process receives a request stay in kernel.thread
and kernel.load_balancing. The numbers here are only a snapshot to show.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kernel.environment.filesystem import FilesystemView
from kernel.environment.identity import IdentityDoor


Isolator = Callable[[tuple[str, ...], str], tuple[str, ...]]


@dataclass(frozen=True)
class CommandPermit:
    """A checked command. The thread pool still waits on it."""

    argv: tuple[str, ...]
    cwd: str
    env: dict[str, str]
    timeout_seconds: float | None


@dataclass(frozen=True)
class ComputeDoor:
    """Permission to launch a program. It does not grow a thread pool."""

    max_concurrent_tasks: int
    max_sync_workers: int
    filesystem: FilesystemView
    identity: IdentityDoor
    max_command_seconds: float | None = None
    isolator: Isolator | None = None

    def prepare(
        self,
        argv: tuple[str, ...] | list[str],
        *,
        cwd: str,
        timeout_seconds: float | None,
        isolate: bool = False,
    ) -> CommandPermit:
        """Answer whether this program may start, where, and for how long."""
        if not argv:
            raise ValueError("命令不能是空的")
        directory = self.filesystem.locate(Path(cwd), write=True)
        if not directory.is_dir():
            raise ValueError(f"命令目录不存在: {directory}")
        if timeout_seconds is not None and timeout_seconds <= 0:
            raise ValueError("命令时间必须大于 0")
        if (
            timeout_seconds is not None
            and self.max_command_seconds is not None
            and timeout_seconds > self.max_command_seconds
        ):
            raise ValueError("命令超过这间屋子允许的最长时间")
        from kernel.resource.workspace.mount.mode import DANGER_FULL_ACCESS, confines

        command = tuple(str(part) for part in argv)
        mode = self.filesystem.access_mode
        if mode != DANGER_FULL_ACCESS and confines(mode):
            if self.isolator is None:
                raise RuntimeError("没有隔离器，不能直接跑")
            command = tuple(self.isolator(command, str(directory)))
        del isolate
        return CommandPermit(
            argv=command,
            cwd=str(directory),
            env=self.identity.scrub_env(),
            timeout_seconds=timeout_seconds,
        )

    def payload(self) -> dict[str, Any]:
        return {
            "max_concurrent_tasks": self.max_concurrent_tasks,
            "max_sync_workers": self.max_sync_workers,
            "max_command_seconds": self.max_command_seconds,
        }

    @classmethod
    def from_parts(
        cls,
        payload: dict[str, Any],
        *,
        filesystem: FilesystemView,
        identity: IdentityDoor,
    ) -> "ComputeDoor":
        raw = dict(payload or {})
        from kernel.environment.confine import host_isolator

        cap = raw.get("max_command_seconds")
        return cls(
            max_concurrent_tasks=int(raw.get("max_concurrent_tasks", 1)),
            max_sync_workers=int(raw.get("max_sync_workers", 1)),
            max_command_seconds=None if cap is None else float(cap),
            filesystem=filesystem,
            identity=identity,
            isolator=host_isolator(filesystem.access_mode),
        )
