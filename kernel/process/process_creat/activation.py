"""Serializable activation data used to create one capability process."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from kernel.environment import HostExecutionPolicy, KernelEnvironment, ProcessEnvironment
from kernel.process.process_creat.instances import CapabilityDefinition
from kernel.resource.handle_view import ResourceContext
from kernel.resource.definition import ResourceGrant
from kernel.thread.contracts import ThreadPolicy


@dataclass(frozen=True)
class ProcessActivation:
    """Bind exactly one capability to one process-scoped resource context."""

    definition: CapabilityDefinition
    grants: tuple[ResourceGrant, ...] = ()
    pid: int = 0
    environment: ProcessEnvironment | None = None
    host_policy: HostExecutionPolicy = field(default_factory=HostExecutionPolicy)
    thread_policy: ThreadPolicy = field(default_factory=ThreadPolicy)
    settings: dict[str, Any] = field(default_factory=dict)
    resource_context: ResourceContext = field(init=False)

    def __post_init__(self) -> None:
        if self.pid <= 0:
            raise ValueError("pid must be a positive operating-system process id")
        object.__setattr__(
            self,
            "resource_context",
            ResourceContext.create(
                pid=self.pid,
                capability_id=self.definition.instance_id,
                requirements=self.definition.resource_requirements,
                grants=self.grants,
                settings=self.settings,
            ),
        )
        if self.environment is None:
            object.__setattr__(
                self,
                "environment",
                ProcessEnvironment.current(
                    pid=self.pid,
                    capability_id=self.definition.instance_id,
                ),
            )
        elif (
            self.environment.pid != self.pid
            or self.environment.capability_id != self.definition.instance_id
        ):
            raise ValueError(
                "process environment identity does not match ProcessActivation"
            )

    def payload(self) -> dict[str, Any]:
        shell = self.environment
        if shell is None:
            raise RuntimeError("process environment was not prepared")
        room = KernelEnvironment.build(
            shell=shell,
            policy=self.host_policy,
            max_concurrent_tasks=self.thread_policy.max_concurrent_tasks,
            max_sync_workers=self.thread_policy.max_sync_workers,
            module_paths=self.definition.module_paths,
            grants=self.grants,
        )
        return {
            "pid": self.pid,
            "instance_id": self.definition.instance_id,
            "module_paths": self.definition.module_paths,
            "entrypoint": self.definition.entrypoint,
            "resource_context": self.resource_context.payload(),
            "environment": shell.payload(),
            "room": room.payload(),
            "host_policy": self.host_policy.payload(),
            "thread_policy": self.thread_policy.payload(),
        }
