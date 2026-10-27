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


Isolator = Callable[[tuple[str, ...], str, str], dict[str, Any]]


@dataclass(frozen=True)
class CommandPermit:
    """A checked command. The thread pool still waits on it."""

    argv: tuple[str, ...]
    cwd: str
    env: dict[str, str]
    timeout_seconds: float | None
    enforcement: str | None = None
    denial_signatures: tuple[str, ...] = ()
    runner_failure_rules: tuple[dict[str, Any], ...] = ()


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
    ) -> CommandPermit:
        """Answer whether this program may start, where, and for how long."""
        if not argv:
            raise ValueError("Command must not be empty")
        from kernel.environment.mount import inside
        from kernel.environment.sandbox_vocab import confines, writes

        mode = self.filesystem.access_mode
        directory = self.filesystem.locate(Path(cwd), write=writes(mode))
        if not directory.is_dir():
            raise ValueError(f"Command directory does not exist: {directory}")
        workspace = self.filesystem.root_path("workspace")
        if confines(mode) and not inside(workspace, directory):
            raise PermissionError("Command directory must be inside the workspace")
        if timeout_seconds is None and self.max_command_seconds is not None:
            timeout_seconds = self.max_command_seconds
        if timeout_seconds is not None and timeout_seconds <= 0:
            raise ValueError("Command timeout must be greater than 0")
        if (
            timeout_seconds is not None
            and self.max_command_seconds is not None
            and timeout_seconds > self.max_command_seconds
        ):
            raise ValueError("Command exceeds the room's maximum time")
        command = tuple(str(part) for part in argv)
        wrapped: dict[str, Any] = {}
        if confines(mode):
            if self.isolator is None:
                raise RuntimeError("No isolator; cannot run directly")
            wrapped = self.isolator(command, str(directory), workspace)
            command = tuple(str(part) for part in wrapped["argv"])
        return CommandPermit(
            argv=command,
            cwd=str(directory),
            env=self.identity.scrub_env(),
            timeout_seconds=timeout_seconds,
            enforcement=wrapped.get("enforcement"),
            denial_signatures=tuple(wrapped.get("denial_signatures") or ()),
            runner_failure_rules=tuple(wrapped.get("runner_failure_rules") or ()),
        )

    def run(
        self,
        argv: tuple[str, ...] | list[str],
        *,
        cwd: str,
        timeout_seconds: float | None,
    ) -> tuple[Any, CommandPermit]:
        """Prepare the command, run it, and fail closed when the runner itself fails."""
        import subprocess

        permit = self.prepare(argv, cwd=cwd, timeout_seconds=timeout_seconds)
        try:
            completed = subprocess.run(
                list(permit.argv),
                cwd=permit.cwd,
                env=permit.env,
                capture_output=True,
                text=True,
                timeout=permit.timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            limit = permit.timeout_seconds or timeout_seconds or 0
            raise TimeoutError(f"command timed out after {int(limit * 1000)}ms") from exc
        from kernel.environment.confine import runner_failure_detail

        detail = runner_failure_detail(
            completed.returncode,
            completed.stderr or "",
            permit.runner_failure_rules,
        )
        if detail is not None:
            raise RuntimeError(
                f'sandbox mode "{self.filesystem.access_mode}" is unavailable: {detail}'
            )
        return completed, permit

    def payload(self) -> dict[str, Any]:
        return {
            "max_concurrent_tasks": self.max_concurrent_tasks,
            "max_sync_workers": self.max_sync_workers,
            "max_command_seconds": self.max_command_seconds,
            "confine": self.isolator is not None,
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
        confine = bool(raw.get("confine", True))
        return cls(
            max_concurrent_tasks=int(raw.get("max_concurrent_tasks", 1)),
            max_sync_workers=int(raw.get("max_sync_workers", 1)),
            max_command_seconds=None if cap is None else float(cap),
            filesystem=filesystem,
            identity=identity,
            isolator=host_isolator(filesystem.access_mode) if confine else None,
        )
