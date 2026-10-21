"""The content range one process may touch. It comes from the memory lease.

Real memory is the one shared store. Each item has a real name. Each process
keeps its own map from its addresses to those names.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


CLASSES = ("system", "message", "task", "artifact")
_KIND_CLASS = {"user": "message", "model": "message", "tool": "artifact", "other": "task"}
_KINDS = set(_KIND_CLASS)
_ROLES = {"user": "user", "model": "assistant", "tool": "tool", "other": "user", "system": "system"}
# What one row asks the next step to do. Empty is a row written before states existed.
STATES = ("asked", "continue", "resulted", "rejected", "answered")

# (pid, resource_id) -> class -> real names, in the order this process saw them.
_MAPS: dict[tuple[str, str], dict[str, list[str]]] = {}


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
    params = getattr(grant, "call_params", None) or {}
    raw = ""
    if isinstance(params, dict):
        raw = str(params.get("space") or "")
    if not raw.strip():
        return CLASSES
    names: list[str] = []
    for part in raw.replace(" ", "").split(","):
        if part not in CLASSES:
            raise ValueError(f"不认识的记忆类: {part or raw}")
        if part not in names:
            names.append(part)
    return tuple(names)


def memory_system(pool: Any, grants: Any) -> str:
    """The rules kept for this process. Empty when it has none."""
    grant = memory_grant(grants)
    if grant is None or pool is None:
        return ""
    if "system" not in visible_classes(grant):
        return ""
    entity = pool.store.entity(grant.resource_id)
    if entity is None or not isinstance(entity.state, dict):
        return ""
    item = _items(entity.state).get("system")
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
    """Keep one prompt file. A new file is appended. A place inserts it and shifts the rest."""
    entity = _memory_entity(pool, grants)
    if entity is None:
        raise RuntimeError("这个进程没有记忆")
    grant = memory_grant(grants)
    _guard_name(grants)
    if grant is None or "system" not in visible_classes(grant):
        raise PermissionError("这个范围不在这个进程的地址空间里")
    label = str(name).strip()
    if not label:
        raise ValueError("还缺文件")
    if place is not None and int(place) < 1:
        raise ValueError("份数从 1 开始")
    state = _state(entity)
    sections = _prompt_sections(state)
    index = next((i for i, item in enumerate(sections) if item["name"] == label), None)
    if index is not None:
        sections.pop(index)
    section = {"name": label, "content": text}
    if place is None and index is not None:
        sections.insert(index, section)
    elif place is None or int(place) - 1 >= len(sections):
        sections.append(section)
    else:
        sections.insert(int(place) - 1, section)
    joined = "\n\n".join(item["content"] for item in sections)
    items = _items(state)
    items["system"] = {
        "class": "system",
        "kind": "system",
        "content": joined,
        "time": _now(),
        "seq": _next_seq(state),
    }
    state["items"] = items
    state["system"] = joined
    state["prompt_files"] = sections
    entity.state = state
    _ensure_system_row(pool, entity.resource_id, grant)


def remember(
    pool: Any,
    grants: Any,
    kind: str,
    content: str,
    state: str = "",
) -> str | None:
    """Append one thing that just happened. Returns this process's new address."""
    if kind not in _KINDS:
        raise ValueError(f"不认识的记忆: {kind}")
    if state and state not in STATES:
        raise ValueError(f"不认识的状态: {state}")
    entity = _memory_entity(pool, grants)
    if entity is None:
        return None
    grant = memory_grant(grants)
    _guard_name(grants)
    class_name = _KIND_CLASS[kind]
    if grant is None or class_name not in visible_classes(grant):
        raise PermissionError("这个范围不在这个进程的地址空间里")
    memory = _state(entity)
    items = _items(memory)
    nxt = _next(memory)
    real = f"{class_name}/{int(nxt.get(class_name) or 0)}"
    nxt[class_name] = int(nxt.get(class_name) or 0) + 1
    items[real] = {
        "class": class_name,
        "kind": kind,
        "content": content,
        "time": _now(),
        "seq": _next_seq(memory),
    }
    if state:
        items[real]["state"] = state
    memory["items"] = items
    memory["next"] = nxt
    entity.state = memory
    return _map_real(pool, entity.resource_id, class_name, real, grant)


def latest_seq(pool: Any, grants: Any) -> int:
    """The order number of the newest row in this memory. Zero when it is empty."""
    entity = _memory_entity(pool, grants)
    if entity is None or not isinstance(entity.state, dict):
        return 0
    return int(entity.state.get("seq") or 0)


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
    items: list[dict[str, str]] = []
    for address, real, item, name in rows:
        if real == "system" and not system:
            system = str(item.get("content") or "")
        items.append(_view(address, real, item, name))
    return {"system": system, "items": items}


def memory_messages(
    pool: Any,
    grants: Any,
    selector: str = "",
) -> list[dict[str, str]]:
    """Rules first, then everything this process can see, earliest first."""
    messages: list[dict[str, str]] = []
    grant = memory_grant(grants)
    if grant is not None:
        _guard_name(grants)
    named = _names_another_memory(selector)
    system = "" if named else memory_system(pool, grants)
    if system:
        when = _system_time(pool, grants)
        message = {"role": "system", "content": system, "name": address_scope(grants)}
        if when:
            message["time"] = when
        messages.append(message)
    if grant is None:
        return messages
    for address, real, item, name in _selected(pool, grants, selector):
        if real == "system" and not named:
            continue
        kind = str(item.get("kind") or "")
        if kind not in _ROLES:
            continue
        messages.append(
            {
                "role": _ROLES[kind],
                "content": str(item.get("content") or ""),
                "time": str(item.get("time") or ""),
                "address": address,
                "name": name,
            }
        )
    return messages


def page_messages(pool: Any, grants: Any, page: dict[str, Any]) -> list[dict[str, str]]:
    """The rules, then the page. Older rows reach the model only through its addresses."""
    import json

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
        raise PermissionError("这个范围不在这个进程的地址空间里")


def _guard_name(grants: Any) -> None:
    grant = memory_grant(grants)
    if grant is None:
        return
    admit(grants, address_scope(grants))


def _memory_entity(pool: Any, grants: Any) -> Any | None:
    grant = memory_grant(grants)
    if grant is None or pool is None:
        return None
    return pool.store.entity(grant.resource_id)


def _state(entity: Any) -> dict[str, Any]:
    state = dict(entity.state or {})
    space = state.get("address_space")
    if not isinstance(space, dict):
        state["address_space"] = {}
    return state


def _prompt_sections(state: dict[str, Any]) -> list[dict[str, str]]:
    raw = state.get("prompt_files")
    if not isinstance(raw, list):
        return []
    found: list[dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        label = str(item.get("name") or "").strip()
        if not label:
            continue
        found.append({"name": label, "content": str(item.get("content") or "")})
    return found


def _items(state: dict[str, Any]) -> dict[str, Any]:
    raw = state.get("items")
    if not isinstance(raw, dict):
        return {}
    return dict(raw)


def _next(state: dict[str, Any]) -> dict[str, int]:
    raw = state.get("next")
    counts = {"message": 0, "task": 0, "artifact": 0}
    if isinstance(raw, dict):
        for name in counts:
            counts[name] = int(raw.get(name) or 0)
    return counts


def _next_seq(state: dict[str, Any]) -> int:
    seq = int(state.get("seq") or 0) + 1
    state["seq"] = seq
    return seq


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def _system_time(pool: Any, grants: Any) -> str:
    entity = _memory_entity(pool, grants)
    if entity is None or not isinstance(entity.state, dict):
        return ""
    item = _items(entity.state).get("system")
    if not isinstance(item, dict):
        return ""
    return str(item.get("time") or "")


def _selected(
    pool: Any,
    grants: Any,
    selector: str,
) -> list[tuple[str, str, dict[str, Any], str]]:
    grant = memory_grant(grants)
    entity = _memory_entity(pool, grants)
    if grant is None or entity is None or not isinstance(entity.state, dict):
        return []
    allowed = visible_classes(grant)
    own_name = str(_identity(grant).get("scope") or "")
    pid = _holder_id(pool, grant)
    mapping = _MAPS.get((pid, entity.resource_id), {})
    items = _items(entity.state)
    chosen: list[tuple[str, str, dict[str, Any], str]] = []
    for memory_name, class_name, start, end in _targets(selector, allowed):
        if memory_name is None:
            rows = list(mapping.get(class_name) or [])
            indexes = range(len(rows)) if start is None else range(start, end + 1)
            for index in indexes:
                if index >= len(rows):
                    raise PermissionError("这个地址不在这个进程的地址空间里")
                real = rows[index]
                item = items.get(real)
                if not isinstance(item, dict):
                    continue
                chosen.append((f"{class_name}/{index}", real, item, own_name))
            continue
        foreign = _memory_named(pool, memory_name)
        for index, real, item in _real_slice(foreign, class_name, start, end):
            chosen.append(
                (f"{memory_name}/{class_name}/{index}", real, item, memory_name)
            )
    chosen.sort(
        key=lambda row: (
            str(row[2].get("time") or ""),
            int(row[2].get("seq") or 0),
            row[3],
        )
    )
    return chosen


def _memory_named(pool: Any, scope: str) -> Any:
    finder = getattr(getattr(pool, "store", None), "memory_named", None)
    entity = None if finder is None else finder(scope)
    if entity is None or not isinstance(getattr(entity, "state", None), dict):
        raise ValueError("没有这份记忆")
    return entity


def _real_slice(
    entity: Any,
    class_name: str,
    start: int | None,
    end: int | None,
) -> list[tuple[int, str, dict[str, Any]]]:
    state = entity.state if isinstance(entity.state, dict) else {}
    items = _items(state)
    if class_name == "system":
        keys = ["system"] if isinstance(items.get("system"), dict) else []
    else:
        count = int(_next(state).get(class_name) or 0)
        keys = [f"{class_name}/{index}" for index in range(count)]
    indexes = range(len(keys)) if start is None else range(start, end + 1)
    found: list[tuple[int, str, dict[str, Any]]] = []
    for index in indexes:
        if index >= len(keys):
            raise PermissionError("这个地址不在这个进程的地址空间里")
        real = keys[index]
        item = items.get(real)
        if isinstance(item, dict):
            found.append((index, real, item))
    return found


def _targets(
    selector: str,
    allowed: tuple[str, ...],
) -> list[tuple[str | None, str, int | None, int | None]]:
    text = selector.strip()
    if not text:
        return [(None, name, None, None) for name in CLASSES if name in allowed]
    parsed: list[tuple[str | None, str, int | None, int | None]] = []
    for part in text.replace(",", " ").split():
        parsed.extend(_one_target(part, allowed))
    return parsed


def _one_target(
    part: str,
    allowed: tuple[str, ...],
) -> list[tuple[str | None, str, int | None, int | None]]:
    pieces = [piece for piece in part.split("/") if piece]
    if not pieces:
        raise ValueError("地址写错了")
    if pieces[0] in CLASSES:
        memory_name = None
        class_name = pieces[0]
        rest = pieces[1:]
    else:
        memory_name = pieces[0]
        rest = pieces[1:]
        if not rest:
            return [
                (memory_name, name, None, None) for name in CLASSES if name in allowed
            ]
        class_name = rest[0]
        rest = rest[1:]
    if class_name not in CLASSES:
        raise ValueError(f"不认识的记忆类: {class_name}")
    if class_name not in allowed:
        raise PermissionError("这个范围不在这个进程的地址空间里")
    if not rest:
        return [(memory_name, class_name, None, None)]
    if len(rest) != 1:
        raise ValueError("地址写错了")
    start, end = _span(rest[0])
    return [(memory_name, class_name, start, end)]


def _names_another_memory(selector: str) -> bool:
    for part in selector.replace(",", " ").split():
        head = part.split("/", 1)[0]
        if head and head not in CLASSES:
            return True
    return False


def _named_address(scope: Any, local: str) -> str:
    name = str(scope or "").strip()
    if not name:
        return local
    return f"{name}/{local}"


def _span(raw: str) -> tuple[int, int]:
    if "-" in raw:
        start_text, end_text = raw.split("-", 1)
    else:
        start_text = end_text = raw
    try:
        start = int(start_text)
        end = int(end_text)
    except ValueError as exc:
        raise ValueError("地址写错了") from exc
    if start < 0 or end < start:
        raise ValueError("地址写错了")
    return start, end


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
