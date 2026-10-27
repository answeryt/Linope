"""The dict that holds one logical process memory. No access policy lives here."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def open_state(identity: dict[str, Any]) -> dict[str, Any]:
    """A new memory entity is the address range named by its scope."""

    return {"address_space": {"scope": str(identity.get("scope") or "")}}


def prepare(state: dict[str, Any] | None) -> dict[str, Any]:
    """Copy one entity state and make sure it has an address range."""

    copied = dict(state or {})
    space = copied.get("address_space")
    if not isinstance(space, dict):
        copied["address_space"] = {}
    return copied


def items(state: dict[str, Any]) -> dict[str, Any]:
    raw = state.get("items")
    if not isinstance(raw, dict):
        return {}
    return dict(raw)


def counters(state: dict[str, Any]) -> dict[str, int]:
    raw = state.get("next")
    counts = {"message": 0, "task": 0, "artifact": 0}
    if isinstance(raw, dict):
        for name in counts:
            counts[name] = int(raw.get(name) or 0)
    return counts


def bump_seq(state: dict[str, Any]) -> int:
    seq = int(state.get("seq") or 0) + 1
    state["seq"] = seq
    return seq


def latest_seq(state: dict[str, Any] | None) -> int:
    if not isinstance(state, dict):
        return 0
    return int(state.get("seq") or 0)


def prompt_sections(state: dict[str, Any]) -> list[dict[str, str]]:
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


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def text_contents(state: dict[str, Any]) -> list[Any]:
    """The raw texts stored in this memory. Token counts are derived from these."""

    found: list[Any] = []
    saw_system = False
    for item in items(state).values():
        if isinstance(item, dict):
            if item.get("class") == "system" or item.get("kind") == "system":
                saw_system = True
            content = item.get("content")
            if content not in (None, ""):
                found.append(content)
        elif item not in (None, ""):
            found.append(item)
    system = state.get("system")
    if not saw_system and isinstance(system, str) and system:
        found.append(system)
    return found


def real_slice(
    state: dict[str, Any],
    class_name: str,
    start: int | None,
    end: int | None,
) -> list[tuple[int, str, dict[str, Any]]]:
    stored = items(state)
    if class_name == "system":
        keys = ["system"] if isinstance(stored.get("system"), dict) else []
    else:
        count = int(counters(state).get(class_name) or 0)
        keys = [f"{class_name}/{index}" for index in range(count)]
    indexes = range(len(keys)) if start is None else range(start, end + 1)
    found: list[tuple[int, str, dict[str, Any]]] = []
    for index in indexes:
        if index >= len(keys):
            raise PermissionError("This address is outside this process's address space")
        real = keys[index]
        item = stored.get(real)
        if isinstance(item, dict):
            found.append((index, real, item))
    return found
