"""Approve and perform memory access. Rows live in the memory runtime."""

from __future__ import annotations

import json
from typing import Any

from kernel.resource.memory.fit import ContextCapacity
from kernel.resource.memory.footprint import context_limit_for, footprint
from kernel.resource.memory.records import STATES, class_of
from kernel.resource.memory.runtime import MemoryRuntime
from kernel.scheduler.memory_space import (
    PointerSpace,
    authorize_resource,
    authorize_selector,
)


def address_scope(leases: Any) -> str:
    """The scope written on this process's memory lease. Empty when it has none."""

    for item in leases:
        if _kind(item) != "memory":
            continue
        return str(_identity(item).get("scope") or "")
    return ""


def memory_grant(grants: Any) -> Any | None:
    """The memory lease on this process, if it asked for one."""

    for item in grants:
        if _kind(item) == "memory":
            return item
    return None


def visible_classes(grant: Any) -> tuple[str, ...]:
    """Classes this process may map. Empty space means every class."""

    from kernel.scheduler.memory_space import classes_of

    return classes_of(grant)


def memory_system(pool: Any, grants: Any) -> str:
    """The rules kept for this process. Empty when it has none."""

    grant = memory_grant(grants)
    if grant is None or pool is None:
        return ""
    if "system" not in visible_classes(grant):
        return ""
    entity = _entity(pool, grants)
    resource_id = getattr(entity, "resource_id", None)
    if entity is None or not resource_id:
        return ""
    return _runtime(pool).system_text(resource_id)


def keep_memory_system(
    pool: Any,
    grants: Any,
    text: str,
    *,
    name: str,
    place: int | None = None,
) -> None:
    """Keep one prompt file after the scheduler accepts the system class."""

    entity = _entity(pool, grants)
    if entity is None:
        raise RuntimeError("This process has no memory")
    grant = memory_grant(grants)
    _guard_name(grants)
    PointerSpace.from_grants("", grants).require("system")
    _runtime(pool).write_system(
        resource_id=entity.resource_id,
        scope=str(_identity(grant).get("scope") or ""),
        holders=_holders(pool, entity.resource_id),
        writer_pid=_holder_id(pool, grant),
        name=name,
        text=text,
        place=place,
    )


def remember(
    pool: Any,
    grants: Any,
    kind: str,
    content: str,
    state: str = "",
) -> str | None:
    """Append one thing that just happened. Returns this process's new address."""

    class_of(kind)
    if state and state not in STATES:
        raise ValueError(f"Unknown state: {state}")
    entity = _entity(pool, grants)
    if entity is None:
        return None
    grant = memory_grant(grants)
    _guard_name(grants)
    class_name = class_of(kind)
    PointerSpace.from_grants("", grants).require(class_name)
    return _runtime(pool).append(
        resource_id=entity.resource_id,
        scope=str(_identity(grant).get("scope") or ""),
        holders=_holders(pool, entity.resource_id),
        writer_pid=_holder_id(pool, grant),
        kind=kind,
        content=content,
        row_state=state,
    )


def latest_seq(pool: Any, grants: Any) -> int:
    """The order number of the newest row in this memory. Zero when it is empty."""

    entity = _entity(pool, grants)
    if entity is None:
        return 0
    return _runtime(pool).latest_seq(entity.resource_id)


def memory_contents(
    pool: Any,
    grants: Any,
    selector: str = "",
) -> dict[str, Any] | None:
    """The rules and later lines this process can see. None without memory."""

    grant = memory_grant(grants)
    if grant is None:
        return None
    entity = _entity(pool, grants)
    if entity is None:
        return None
    _guard_name(grants)
    parsed = authorize_selector(grants, selector)
    scope = str(_identity(grant).get("scope") or "")
    space = PointerSpace.from_grants("", grants)
    foreign = {
        pointer.scope: (pointer.resource_id, pointer.scope)
        for pointer in space.pointers
        if pointer.resource_id
    }
    rows = _runtime(pool).contents(
        resource_id=entity.resource_id,
        scope=scope,
        pid=_holder_id(pool, grant),
        classes=visible_classes(grant),
        selector=parsed,
        foreign=foreign,
    )
    system = ""
    for item in rows:
        if item.get("real") == "system" and not system:
            system = str(item.get("content") or "")
    return {"system": system, "items": rows}


def page_messages(pool: Any, grants: Any, page: dict[str, Any]) -> list[dict[str, str]]:
    """The rules, then this page. The page carries only what this turn is showing."""

    messages: list[dict[str, str]] = []
    system = memory_system(pool, grants)
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": json.dumps(page, ensure_ascii=False)})
    return messages


def prompt_budget(pool: Any, grants: Any, page: dict[str, Any], model: str = "") -> int:
    """Room left for one explicit read after the system text and this page."""

    limit = context_limit_for(model)
    system = memory_system(pool, grants)
    action = json.dumps(page, ensure_ascii=False)
    size = footprint(context_limit=limit, system=system, action=action)
    if size.over_hard_limit:
        raise ContextCapacity("context_capacity")
    return max(0, size.available)


def admit(leases: Any, scope: str) -> None:
    """Refuse a scope that is not this process's memory lease."""

    allowed = address_scope(leases)
    if not scope or scope != allowed:
        raise PermissionError("This range is outside this process's address space")


def _guard_name(grants: Any) -> None:
    grant = memory_grant(grants)
    if grant is None:
        return
    admit(grants, address_scope(grants))


def _entity(pool: Any, grants: Any) -> Any | None:
    grant = memory_grant(grants)
    if grant is None or pool is None:
        return None
    authorize_resource(grants, grant.resource_id)
    return pool.store.entity(grant.resource_id)


def _runtime(pool: Any) -> MemoryRuntime:
    store = getattr(pool, "store", None)
    runtime = getattr(store, "memory", None)
    if runtime is None:
        runtime = MemoryRuntime()
        if store is not None:
            store.memory = runtime
    return runtime


def _kind(item: Any) -> str:
    kind = getattr(item, "kind", "")
    return str(getattr(kind, "value", kind))


def _identity(item: Any) -> dict[str, Any]:
    identity = getattr(item, "identity", None)
    if isinstance(identity, dict):
        return identity
    metadata = getattr(item, "metadata", None) or {}
    if isinstance(metadata, dict):
        nested = metadata.get("identity")
        if isinstance(nested, dict):
            return nested
    return {}


def _holders(pool: Any, resource_id: str) -> list[tuple[str, tuple[str, ...]]]:
    found: list[tuple[str, tuple[str, ...]]] = []
    grants_for = getattr(pool, "_grants_for_process", None) or {}
    for pid, grants in grants_for.items():
        for grant in grants:
            if getattr(grant, "resource_id", None) != resource_id:
                continue
            if _kind(grant) != "memory":
                continue
            found.append((str(pid), visible_classes(grant)))
    return found


def _holder_id(pool: Any, grant: Any) -> str:
    handle = getattr(grant, "handle", None)
    for pid, grants in (getattr(pool, "_grants_for_process", None) or {}).items():
        for item in grants:
            if getattr(item, "handle", None) == handle:
                return str(pid)
    return ""
