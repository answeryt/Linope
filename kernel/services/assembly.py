"""Turn a spec into member processes through the existing creation entry.

The assembler does not plan replicas, pick processes or judge liveness. It
asks the blueprint for members, asks the reconciler to launch each one, and
closes what it opened if any member fails.
"""

from __future__ import annotations

from typing import Any

from kernel.services.handle import ServiceHandle
from kernel.services.host import ServiceHost
from kernel.services.registry import load_blueprint
from kernel.services.spec import LaunchOptions, MemberPlan, ServicePlan, ServiceSpec


class ServiceAssembler:
    """Spec -> plan -> launched members -> handle."""

    def __init__(self, host: ServiceHost) -> None:
        self.host = host

    def open(self, spec: ServiceSpec, options: LaunchOptions) -> ServiceHandle:
        plan = load_blueprint(spec.kind).plan(spec)
        prepared = _declarations(self.host, plan)
        store = self.host.open_store(options.store_locator)
        try:
            _share(store, plan.shared)
            opened = self._launch_members(prepared, options, store)
        except BaseException:
            _close_quietly(store)
            raise
        return ServiceHandle(plan, opened, store)

    def _launch_members(
        self,
        prepared: tuple[tuple[MemberPlan, Any, Any], ...],
        options: LaunchOptions,
        store: Any,
    ) -> tuple[tuple[MemberPlan, tuple[Any, ...]], ...]:
        reconciler = self.host.reconciler(self.host.pool(store))
        opened: list[tuple[MemberPlan, tuple[Any, ...]]] = []
        try:
            for member, declaration, definition in prepared:
                processes = tuple(
                    reconciler.launch(
                        declaration,
                        definition=definition,
                        thread_policy=options.thread_policy,
                        replica_count=member.replica_count,
                        env_file=options.env_file,
                        env_file_keys=options.env_file_keys,
                        cwd=options.cwd,
                        host_policy=options.host_policy,
                    )
                )
                if not processes:
                    raise RuntimeError(f"没有拉起能力进程: {member.capability}")
                opened.append((member, processes))
        except BaseException:
            for _member, processes in opened:
                for process in processes:
                    _stop_quietly(process)
            raise
        return tuple(opened)


def _declarations(
    host: ServiceHost,
    plan: ServicePlan,
) -> tuple[tuple[MemberPlan, Any, Any], ...]:
    """Ask every member for its declaration before any ledger is opened."""
    return tuple(
        (member, *host.load_declaration(member.capability, member.changes))
        for member in plan.members
    )


def _share(store: Any, shared: tuple[str, ...]) -> None:
    """Add the blueprint's shared names. The person's own choices stay."""
    if not shared:
        return
    current = tuple(store.shared_capabilities())
    missing = tuple(name for name in shared if name not in current)
    if missing:
        store.share_capabilities(current + missing)


def _stop_quietly(process: Any) -> None:
    try:
        process.stop()
    except Exception:
        pass


def _close_quietly(store: Any) -> None:
    try:
        store.close()
    except Exception:
        pass
