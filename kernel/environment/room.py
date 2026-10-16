"""One room: the seven doors a capability process is allowed to use."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from kernel.environment.communication import CommunicationDoor
from kernel.environment.compute import ComputeDoor
from kernel.environment.file_io import FileDoor
from kernel.environment.filesystem import FilesystemView
from kernel.environment.identity import IdentityDoor, check_access_mode
from kernel.environment.lifecycle import LifecycleDoor
from kernel.environment.memory import MemoryDoor
from kernel.environment.policy import HostExecutionPolicy
from kernel.environment.shell import ProcessEnvironment


@dataclass(frozen=True)
class KernelEnvironment:
    """The places and permissions one capability process can touch."""

    shell: ProcessEnvironment
    policy: HostExecutionPolicy
    filesystem: FilesystemView
    identity: IdentityDoor
    memory: MemoryDoor
    communication: CommunicationDoor
    compute: ComputeDoor
    lifecycle: LifecycleDoor
    file_io: FileDoor

    def apply(self) -> None:
        self.shell.apply()

    def widen(self, approver: str) -> "KernelEnvironment":
        identity = self.identity.approve_wider(approver)
        filesystem = self.filesystem.with_access_mode(identity.access_mode)
        return replace(
            self,
            identity=identity,
            filesystem=filesystem,
            file_io=FileDoor(filesystem),
            compute=replace(self.compute, identity=identity, filesystem=filesystem),
        )

    def payload(self) -> dict[str, Any]:
        return {
            "shell": self.shell.payload(),
            "policy": self.policy.payload(),
            "filesystem": self.filesystem.payload(),
            "identity": self.identity.payload(),
            "memory": self.memory.payload(),
            "communication": self.communication.payload(),
            "compute": self.compute.payload(),
            "lifecycle": self.lifecycle.payload(),
        }

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "KernelEnvironment":
        filesystem = FilesystemView.from_payload(payload["filesystem"])
        shell = ProcessEnvironment.from_payload(payload["shell"])
        identity = IdentityDoor.from_payload(payload["identity"]).with_secrets(
            shell.env_file,
            shell.env_file_keys,
        )
        return cls(
            shell=shell,
            policy=HostExecutionPolicy.from_payload(payload.get("policy")),
            filesystem=filesystem,
            identity=identity,
            memory=MemoryDoor.from_payload(payload.get("memory")),
            communication=CommunicationDoor.from_payload(payload.get("communication")),
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
        channel_name: str,
        channel_settings: dict[str, Any] | None = None,
        module_paths: tuple[str, ...] = (),
        grants: tuple[object, ...] = (),
        access_mode: str | None = None,
        outbound_hosts: tuple[str, ...] = (),
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
            memory=MemoryDoor.from_grants(grants),
            communication=CommunicationDoor.from_parts(
                channel_name=channel_name,
                channel_settings=channel_settings,
                grants=grants,
                outbound_hosts=outbound_hosts,
            ),
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
        if str(getattr(kind, "value", kind)) != "workspace":
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
