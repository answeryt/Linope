"""The content range one process may touch. It comes from the memory lease."""

from __future__ import annotations

from typing import Any


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


def memory_system(pool: Any, grants: Any) -> str:
    """The rules kept for this process. Empty when it has none."""
    grant = memory_grant(grants)
    if grant is None or pool is None:
        return ""
    entity = pool.store.entity(grant.resource_id)
    if entity is None or not isinstance(entity.state, dict):
        return ""
    return str(entity.state.get("system") or "")


def keep_memory_system(pool: Any, grants: Any, text: str) -> None:
    """Write the prompt file into this process's rules. A later file replaces them."""
    entity = _memory_entity(pool, grants)
    if entity is None:
        raise RuntimeError("这个进程没有记忆")
    state = dict(entity.state or {})
    state["system"] = text
    entity.state = state


_KINDS = {"user", "model", "tool", "other"}
_ROLES = {"user": "user", "model": "assistant", "tool": "tool", "other": "user"}


def remember(pool: Any, grants: Any, kind: str, content: str) -> None:
    """Append one thing that just happened. Nothing is written without memory."""
    if kind not in _KINDS:
        raise ValueError(f"不认识的记忆: {kind}")
    entity = _memory_entity(pool, grants)
    if entity is None:
        return
    state = dict(entity.state or {})
    turns = [dict(item) for item in _turn_list(state)]
    turns.append({"kind": kind, "content": content})
    state["turns"] = turns
    entity.state = state


def memory_contents(pool: Any, grants: Any) -> dict[str, Any] | None:
    """The rules and later lines. None when this process has no memory."""
    if memory_grant(grants) is None:
        return None
    entity = _memory_entity(pool, grants)
    state = {} if entity is None or not isinstance(entity.state, dict) else entity.state
    turns: list[dict[str, str]] = []
    for item in _turn_list(state):
        kind = str(item.get("kind") or "")
        if kind not in _KINDS:
            continue
        turns.append({"kind": kind, "content": str(item.get("content") or "")})
    return {"system": str(state.get("system") or ""), "turns": turns}


def memory_messages(pool: Any, grants: Any) -> list[dict[str, str]]:
    """Rules first, then everything kept so far, in the order it happened."""
    messages: list[dict[str, str]] = []
    system = memory_system(pool, grants)
    if system:
        messages.append({"role": "system", "content": system})
    entity = _memory_entity(pool, grants)
    state = {} if entity is None or not isinstance(entity.state, dict) else entity.state
    for item in _turn_list(state):
        kind = str(item.get("kind") or "")
        if kind not in _KINDS:
            continue
        messages.append(
            {"role": _ROLES[kind], "content": str(item.get("content") or "")}
        )
    return messages


def _memory_entity(pool: Any, grants: Any) -> Any | None:
    grant = memory_grant(grants)
    if grant is None or pool is None:
        return None
    return pool.store.entity(grant.resource_id)


def _turn_list(state: dict[str, Any]) -> list[dict[str, Any]]:
    raw = state.get("turns") or ()
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def admit(leases: Any, scope: str) -> None:
    """Refuse a scope that is not this process's memory lease."""
    allowed = address_scope(leases)
    if not scope or scope != allowed:
        raise PermissionError("这个范围不在这个进程的地址空间里")
