"""Count memory tokens and peers on one network channel."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

FALLBACK_CONTEXT_LIMIT = 256_000


def context_limit_from(settings: Any) -> int:
    """Read a declared context limit. The kernel does not keep a model catalog."""

    if isinstance(settings, dict):
        raw = settings.get("context_limit")
        if isinstance(raw, int) and not isinstance(raw, bool) and raw > 0:
            return raw
    return FALLBACK_CONTEXT_LIMIT


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


_IMAGE_TOKENS = 85


def count_tokens(model: str, content: Any) -> int:
    """Token count for one piece of text, code, or one image.

    The kernel estimates length itself. It does not import a provider tokenizer.
    """
    if not str(model or "").strip():
        return 0
    if _is_image(content):
        return _IMAGE_TOKENS
    text = content if isinstance(content, str) else ""
    if not text:
        return 0
    from kernel.resource.memory.token_meter import estimate_tokens

    return estimate_tokens(text)


def measure(
    *,
    pool: Any | None,
    record: Any,
    book: Any | None,
    activity: str,
    context_limit: int = 0,
) -> Pressure:
    """Read this process's memory and the other processes on its channel."""
    leases = tuple(getattr(record, "leases", ()) or ())
    from kernel.resource.memory.token_meter import estimate_tokens
    from kernel.scheduler.access import memory_system

    tokens = estimate_tokens(memory_system(pool, leases))
    limit = context_limit if isinstance(context_limit, int) and context_limit > 0 else FALLBACK_CONTEXT_LIMIT
    channel = _channel(leases)
    return Pressure(
        tokens=tokens,
        context_limit=limit,
        context_full=limit > 0 and tokens >= limit,
        channel=channel,
        peers=_peers(book, record, channel),
        activity=str(activity or "sleeping"),
    )


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


def _channel(leases: tuple[Any, ...]) -> str:
    for lease in leases:
        if str(getattr(lease, "kind", "")) != "network":
            continue
        identity = getattr(lease, "identity", {}) or {}
        return str(identity.get("channel") or "")
    return ""


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
