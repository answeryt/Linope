"""Approve and perform memory access. The resource module only stores rows."""

from __future__ import annotations

import json
from typing import Any

from kernel.resource.memory.state import (
    items as state_items,
    latest_seq as stored_seq,
    prepare,
    real_slice,
)
from kernel.resource.memory.store import STATES, append_row, class_of, write_prompt
from kernel.scheduler.memory_space import (
    PointerSpace,
    authorize_resource,
    authorize_selector,
    classes_of,
)

_MAPS: dict[tuple[str, str], dict[str, list[str]]] = {}


def capacity_full(tokens: int, limit: int) -> bool:
    """The scheduler's capacity decision. The token number is only an input."""

    return limit > 0 and tokens >= limit


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

    return classes_of(grant)


def memory_system(pool: Any, grants: Any) -> str:
    """The rules kept for this process. Empty when it has none."""

    grant = memory_grant(grants)
    if grant is None or pool is None:
        return ""
    if "system" not in visible_classes(grant):
        return ""
    entity = _entity(pool, grants)
    if entity is None or not isinstance(entity.state, dict):
        return ""
    item = state_items(entity.state).get("system")
    if isinstance(item, dict):
        return str(item.get("content") or "")
    return str(entity.state.get("system") or "")


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
    memory = prepare(entity.state)
    write_prompt(memory, name=name, text=text, place=place)
    entity.state = memory
    _ensure_system_row(pool, entity.resource_id, grant)


def remember(
    pool: Any,
    grants: Any,
    kind: str,
    content: str,
    state: str = "",
) -> str | None:
    """Append one thing that just happened. Returns this process's new address."""

    class_name = class_of(kind)
    if state and state not in STATES:
        raise ValueError(f"Unknown state: {state}")
    entity = _entity(pool, grants)
    if entity is None:
        return None
    grant = memory_grant(grants)
    _guard_name(grants)
    PointerSpace.from_grants("", grants).require(class_name)
    memory = prepare(entity.state)
    real = append_row(memory, kind, content, state)
    entity.state = memory
    return _map_real(pool, entity.resource_id, class_name, real, grant)


def latest_seq(pool: Any, grants: Any) -> int:
    """The order number of the newest row in this memory. Zero when it is empty."""

    entity = _entity(pool, grants)
    if entity is None or not isinstance(entity.state, dict):
        return 0
    return stored_seq(entity.state)


def memory_contents(
    pool: Any,
    grants: Any,
    selector: str = "",
) -> dict[str, Any] | None:
    """The rules and later lines this process can see. None without memory."""

    if memory_grant(grants) is None:
        return None
    _guard_name(grants)
    rows = _selected(pool, grants, selector)
    system = ""
    found: list[dict[str, str]] = []
    for address, real, item, name in rows:
        if real == "system" and not system:
            system = str(item.get("content") or "")
        found.append(_view(address, real, item, name))
    return {"system": system, "items": found}


def page_messages(pool: Any, grants: Any, page: dict[str, Any]) -> list[dict[str, str]]:
    """The rules, then the page. Older rows reach the model only through its addresses."""

    messages: list[dict[str, str]] = []
    system = memory_system(pool, grants)
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": json.dumps(page, ensure_ascii=False)})
    return messages


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


def _holders(pool: Any, resource_id: str) -> list[tuple[str, Any]]:
    found: list[tuple[str, Any]] = []
    grants_for = getattr(pool, "_grants_for_process", None) or {}
    for pid, grants in grants_for.items():
        for grant in grants:
            if getattr(grant, "resource_id", None) != resource_id:
                continue
            if _kind(grant) != "memory":
                continue
            found.append((str(pid), grant))
    return found


def _holder_id(pool: Any, grant: Any) -> str:
    handle = getattr(grant, "handle", None)
    for pid, grants in (getattr(pool, "_grants_for_process", None) or {}).items():
        for item in grants:
            if getattr(item, "handle", None) == handle:
                return str(pid)
    return ""


def _rows(pid: str, resource_id: str) -> dict[str, list[str]]:
    return _MAPS.setdefault((pid, resource_id), {})


def _ensure_system_row(pool: Any, resource_id: str, writer: Any) -> None:
    holders = _holders(pool, resource_id) or [(_holder_id(pool, writer), writer)]
    for pid, grant in holders:
        if "system" not in visible_classes(grant):
            continue
        rows = _rows(pid, resource_id).setdefault("system", [])
        if "system" not in rows:
            rows.append("system")


def _map_real(pool: Any, resource_id: str, class_name: str, real: str, writer: Any) -> str:
    writer_id = _holder_id(pool, writer)
    writer_address = ""
    holders = _holders(pool, resource_id)
    if not holders:
        holders = [(writer_id, writer)]
    for pid, grant in holders:
        if class_name not in visible_classes(grant):
            continue
        rows = _rows(pid, resource_id).setdefault(class_name, [])
        rows.append(real)
        if pid == writer_id:
            writer_address = _named_address(
                _identity(writer).get("scope"),
                f"{class_name}/{len(rows) - 1}",
            )
    return writer_address


def _selected(
    pool: Any,
    grants: Any,
    selector: str,
) -> list[tuple[str, str, dict[str, Any], str]]:
    grant = memory_grant(grants)
    entity = _entity(pool, grants)
    if grant is None or entity is None or not isinstance(entity.state, dict):
        return []
    own_name = str(_identity(grant).get("scope") or "")
    pid = _holder_id(pool, grant)
    mapping = _MAPS.get((pid, entity.resource_id), {})
    stored = state_items(entity.state)
    chosen: list[tuple[str, str, dict[str, Any], str]] = []
    for memory_name, class_name, start, end in authorize_selector(grants, selector):
        if memory_name is None:
            rows = list(mapping.get(class_name) or [])
            indexes = range(len(rows)) if start is None else range(start, end + 1)
            for index in indexes:
                if index >= len(rows):
                    raise PermissionError("This address is outside this process's address space")
                real = rows[index]
                item = stored.get(real)
                if not isinstance(item, dict):
                    continue
                chosen.append((f"{class_name}/{index}", real, item, own_name))
            continue
        pointer = PointerSpace.from_grants("", grants).for_scope(memory_name)
        foreign = None if pointer is None else pool.store.entity(pointer.resource_id)
        if foreign is None or not isinstance(getattr(foreign, "state", None), dict):
            raise PermissionError("This range is outside this process's address space")
        for index, real, item in real_slice(foreign.state, class_name, start, end):
            chosen.append((f"{memory_name}/{class_name}/{index}", real, item, memory_name))
    chosen.sort(
        key=lambda row: (
            str(row[2].get("time") or ""),
            int(row[2].get("seq") or 0),
            row[3],
        )
    )
    return chosen


def _named_address(scope: Any, local: str) -> str:
    name = str(scope or "").strip()
    if not name:
        return local
    return f"{name}/{local}"


def _view(address: str, real: str, item: dict[str, Any], name: str) -> dict[str, Any]:
    view: dict[str, Any] = {
        "address": address,
        "real": real,
        "name": name,
        "kind": str(item.get("kind") or ""),
        "content": str(item.get("content") or ""),
        "time": str(item.get("time") or ""),
        "seq": int(item.get("seq") or 0),
    }
    if item.get("state"):
        view["state"] = str(item["state"])
    return view
