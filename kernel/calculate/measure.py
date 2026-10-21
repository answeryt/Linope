"""Count memory tokens and peers on one network channel."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from capability.model.model_API.model_paramaters.context_limits.context_limits import (
    resolve_default_context_length,
)


_IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".webp")


@dataclass(frozen=True)
class Pressure:
    """What load balancing needs before it decides to add one helper."""

    tokens: int
    context_limit: int
    context_full: bool
    channel: str
    peers: int
    activity: str


def count_tokens(model: str, content: Any) -> int:
    """Token count for one piece of text, code, or one image."""
    import litellm

    name = model or "gpt-4o"
    if _is_image(content):
        url = content if isinstance(content, str) else str(content.get("url") or "")
        return _counter(
            litellm,
            name,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": url}},
                    ],
                }
            ],
            use_default_image_token_count=True,
        )
    text = content if isinstance(content, str) else ""
    if not text:
        return 0
    return _counter(litellm, name, text=text)


def measure(
    *,
    pool: Any | None,
    record: Any,
    book: Any | None,
    activity: str,
) -> Pressure:
    """Read this process's memory and the other processes on its channel."""
    leases = tuple(getattr(record, "leases", ()) or ())
    model = _model_id(leases)
    tokens = 0
    entity = _memory_entity(pool, leases)
    state = {}
    if entity is not None and isinstance(getattr(entity, "state", None), dict):
        state = entity.state
    for content in _contents(state):
        tokens += count_tokens(model, content)
    limit = resolve_default_context_length(model or "unknown/model")
    channel = _channel(leases)
    return Pressure(
        tokens=tokens,
        context_limit=limit,
        context_full=limit > 0 and tokens >= limit,
        channel=channel,
        peers=_peers(book, record, channel),
        activity=str(activity or "sleeping"),
    )


def _counter(litellm: Any, model: str, **kwargs: Any) -> int:
    try:
        return int(litellm.token_counter(model=model, **kwargs))
    except Exception:
        return int(litellm.token_counter(model="gpt-4o", **kwargs))


def _is_image(content: Any) -> bool:
    if isinstance(content, dict) and content.get("url"):
        return True
    if not isinstance(content, str):
        return False
    text = content.strip()
    lowered = text.lower()
    if lowered.startswith("data:image/"):
        return True
    if not lowered.startswith("http"):
        return False
    path = lowered.split("?", 1)[0]
    return path.endswith(_IMAGE_SUFFIXES)


def _contents(state: dict[str, Any]) -> list[Any]:
    items = state.get("items")
    found: list[Any] = []
    saw_system = False
    if isinstance(items, dict):
        for item in items.values():
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


def _model_id(leases: tuple[Any, ...]) -> str:
    for lease in leases:
        if str(getattr(lease, "kind", "")) != "model":
            continue
        identity = getattr(lease, "identity", {}) or {}
        return str(identity.get("id") or "")
    return ""


def _channel(leases: tuple[Any, ...]) -> str:
    for lease in leases:
        if str(getattr(lease, "kind", "")) != "network":
            continue
        identity = getattr(lease, "identity", {}) or {}
        return str(identity.get("channel") or "")
    return ""


def _memory_entity(pool: Any | None, leases: tuple[Any, ...]) -> Any | None:
    if pool is None:
        return None
    store = getattr(pool, "store", None)
    if store is None:
        return None
    for lease in leases:
        if str(getattr(lease, "kind", "")) != "memory":
            continue
        return store.entity(getattr(lease, "resource_id", ""))
    return None


def _peers(book: Any | None, record: Any, channel: str) -> int:
    if book is None or not channel:
        return 0
    pid = int(getattr(record, "pid", 0) or 0)
    count = 0
    for other in book.records():
        if int(other.pid) == pid:
            continue
        if str(getattr(other.status, "value", other.status)) in {"closed", "closing"}:
            continue
        if _channel(tuple(other.leases)) == channel:
            count += 1
    return count
