"""Serializable input and output of a service blueprint."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from kernel.environment import HostExecutionPolicy
from kernel.process.profile import Change
from kernel.thread.contracts import ThreadPolicy


@dataclass(frozen=True)
class ServiceSpec:
    """The only input to open a service.

    ``members`` are the capability names typed on the command line. Each
    blueprint reads them by its own rule. ``changes`` apply to the first
    member. ``replica_count`` is handed on unchanged to the process layer.
    """

    kind: str
    members: tuple[str, ...] = ()
    changes: tuple[Change, ...] = ()
    replica_count: int | None = None
    options: dict[str, Any] = field(default_factory=dict)
    name: str = ""

    def __post_init__(self) -> None:
        if not self.kind or self.kind.strip() != self.kind:
            raise ValueError("服务种类不能为空")
        if self.replica_count is not None and self.replica_count < 1:
            raise ValueError("份数至少为 1")


@dataclass(frozen=True)
class MemberPlan:
    """One peer process the service will ask the process layer to create."""

    role: str
    capability: str
    changes: tuple[Change, ...] = ()
    replica_count: int | None = None

    def __post_init__(self) -> None:
        if not self.role:
            raise ValueError("成员角色不能为空")
        if not self.capability:
            raise ValueError("成员能力名不能为空")


@dataclass(frozen=True)
class ServicePlan:
    """What a blueprint returns. ``route`` maps a request kind to a role."""

    members: tuple[MemberPlan, ...]
    shared: tuple[str, ...] = ()
    route: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.members:
            raise ValueError("服务至少要有一个成员")
        roles = [member.role for member in self.members]
        if len(set(roles)) != len(roles):
            raise ValueError("成员角色不能重复")
        unknown = set(self.route.values()) - set(roles)
        if unknown:
            raise ValueError(f"路由指向不存在的角色: {', '.join(sorted(unknown))}")

    def roles(self) -> tuple[str, ...]:
        return tuple(member.role for member in self.members)


@dataclass(frozen=True)
class LaunchOptions:
    """The room and policies for every member. Not part of the composition."""

    store_locator: str | None = None
    thread_policy: ThreadPolicy | None = None
    host_policy: HostExecutionPolicy | None = None
    env_file: str = ""
    env_file_keys: tuple[str, ...] = ()
    cwd: str | None = None
    shared: tuple[str, ...] = ()
    once: bool = False
    chosen: tuple[str, ...] = ()
    ledger_path: str | None = None
