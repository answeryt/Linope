"""One room: the seven doors a capability process is allowed to use."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kernel.environment.compute import ComputeDoor
from kernel.environment.file_io import FileDoor
from kernel.environment.filesystem import FilesystemView
from kernel.environment.identity import IdentityDoor, check_access_mode
from kernel.environment.lifecycle import LifecycleDoor
from kernel.environment.policy import HostExecutionPolicy
from kernel.environment.shell import ProcessEnvironment


@dataclass(frozen=True)
class KernelEnvironment:
    """The places and permissions one capability process can touch."""

    shell: ProcessEnvironment
    policy: HostExecutionPolicy
    filesystem: FilesystemView
    identity: IdentityDoor
    compute: ComputeDoor
    lifecycle: LifecycleDoor
    file_io: FileDoor

    def apply(self) -> None:
        self.shell.apply()

    def payload(self) -> dict[str, Any]:
        return {
            "shell": self.shell.payload(),
            "policy": self.policy.payload(),
            "filesystem": self.filesystem.payload(),
            "identity": self.identity.payload(),
            "compute": self.compute.payload(),
            "lifecycle": self.lifecycle.payload(),
        }

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "KernelEnvironment":
        filesystem = FilesystemView.from_payload(payload["filesystem"])
        shell = ProcessEnvironment.from_payload(payload["shell"])
        identity = IdentityDoor.from_payload(payload["identity"])
        if not identity.secret_names and shell.env_file_keys:
            identity = identity.with_secrets(shell.env_file, shell.env_file_keys)
        return cls(
            shell=shell,
            policy=HostExecutionPolicy.from_payload(payload.get("policy")),
            filesystem=filesystem,
            identity=identity,
            compute=ComputeDoor.from_parts(
                payload.get("compute") or {},
                filesystem=filesystem,
                identity=identity,
            ),
            lifecycle=LifecycleDoor.from_payload(payload.get("lifecycle")),
            file_io=FileDoor(filesystem),
        )

    @classmethod
    def build(
        cls,
        *,
        shell: ProcessEnvironment,
        policy: HostExecutionPolicy,
        max_concurrent_tasks: int,
        max_sync_workers: int,
        module_paths: tuple[str, ...] = (),
        grants: tuple[object, ...] = (),
        access_mode: str | None = None,
        max_command_seconds: float | None = None,
        confine: bool = True,
    ) -> "KernelEnvironment":
        from kernel.environment.confine import host_isolator

        mode = _access_mode(access_mode, grants)
        filesystem = FilesystemView.for_local(
            Path(shell.cwd),
            package_paths=tuple(Path(path) for path in module_paths),
            access_mode=mode,
            process_id=shell.process_id,
        )
        identity = IdentityDoor(
            process_id=shell.process_id,
            capability_id=shell.capability_id,
            access_mode=mode,
            secret_file=shell.env_file,
            secret_names=shell.env_file_keys,
        )
        return cls(
            shell=shell,
            policy=policy,
            filesystem=filesystem,
            identity=identity,
            compute=ComputeDoor(
                max_concurrent_tasks=max_concurrent_tasks,
                max_sync_workers=max_sync_workers,
                max_command_seconds=max_command_seconds,
                filesystem=filesystem,
                identity=identity,
                isolator=host_isolator(mode) if confine else None,
            ),
            lifecycle=LifecycleDoor.from_policy(policy),
            file_io=FileDoor(filesystem),
        )


def _access_mode(explicit: str | None, grants: tuple[object, ...]) -> str:
    if explicit:
        return check_access_mode(explicit)
    for grant in grants:
        kind = getattr(grant, "kind", "")
        if str(getattr(kind, "value", kind)) != "sandbox":
            continue
        metadata = getattr(grant, "metadata", {}) or {}
        call_params = getattr(grant, "call_params", {}) or {}
        chosen = ""
        if isinstance(call_params, dict) and call_params.get("mode"):
            chosen = str(call_params["mode"])
        elif isinstance(metadata, dict) and metadata.get("access_mode"):
            chosen = str(metadata["access_mode"])
        if chosen:
            return check_access_mode(chosen)
    return "workspace-write"
