"""Process-local concurrency configuration.

Thread layout is intentionally not a replica layout.  It is not persisted as
an independently addressable object and it never owns a resource lease.
"""

from __future__ import annotations

from kernel.thread.contracts import ThreadPlan, ThreadPolicy, ThreadSpec


def configure_thread_policy(
    settings: dict[str, object] | None = None,
    *,
    max_concurrent_tasks: int | None = None,
    max_sync_workers: int | None = None,
) -> ThreadPolicy:
    """Build a policy from activation settings and optional CLI overrides."""

    raw = dict(settings or {})
    if max_concurrent_tasks is not None:
        raw["max_concurrent_tasks"] = max_concurrent_tasks
    if max_sync_workers is not None:
        raw["max_sync_workers"] = max_sync_workers
    return ThreadPolicy.from_payload(raw)


def plan_threads(policy: ThreadPolicy) -> ThreadPlan:
    """Describe sync execution slots without persisting them as replicas."""

    return ThreadPlan(
        desired=tuple(
            ThreadSpec(name=f"linope-sync-{index}", index=index)
            for index in range(policy.max_sync_workers)
        )
    )
