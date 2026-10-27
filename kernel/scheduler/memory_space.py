"""The address space one process may touch, managed by the scheduler.

``space`` on a memory grant is only an input. It names which classes belong in
the pointer. The pointer itself is the right to enter one memory resource.
``message/0`` and ``message/0-10`` are selectors inside that resource, not the
right to open it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


CLASSES = ("system", "message", "task", "artifact")


@dataclass(frozen=True)
class MemoryPointer:
    """One authorized memory resource page. Not a row such as ``message/0``."""

    scope: str
    resource_id: str
    classes: tuple[str, ...]
    handle: str


@dataclass(frozen=True)
class PointerSpace:
    """Every memory resource this process may enter."""

    pid: str
    pointers: tuple[MemoryPointer, ...]

    @classmethod
    def from_grants(cls, pid: object, grants: Any) -> "PointerSpace":
        """Rebuild the space from the grants. Nothing else is consulted."""

        found: list[MemoryPointer] = []
        for item in grants or ():
            if _kind(item) != "memory":
                continue
            identity = _identity(item)
            found.append(
                MemoryPointer(
                    scope=str(identity.get("scope") or ""),
                    resource_id=str(getattr(item, "resource_id", "") or ""),
                    classes=classes_of(item),
                    handle=str(getattr(item, "handle", "") or ""),
                )
            )
        return cls(str(pid or ""), tuple(found))

    def own(self) -> MemoryPointer | None:
        """The memory this process was given. Empty when it has none."""

        return self.pointers[0] if self.pointers else None

    def for_scope(self, scope: str | None) -> MemoryPointer | None:
        """The pointer for this scope. An empty scope means the process's own."""

        if not scope:
            return self.own()
        for pointer in self.pointers:
            if pointer.scope == scope:
                return pointer
        return None

    def require(self, class_name: str, scope: str | None = None) -> MemoryPointer:
        """Refuse a class or scope this process was not given a pointer for."""

        pointer = self.for_scope(scope)
        if pointer is None or class_name not in pointer.classes:
            raise PermissionError("This range is outside this process's address space")
        return pointer


def classes_of(grant: Any) -> tuple[str, ...]:
    """Classes named by ``call_params['space']``. Empty means every class."""

    params = getattr(grant, "call_params", None) or {}
    raw = ""
    if isinstance(params, dict):
        raw = str(params.get("space") or "")
    if not raw.strip():
        return CLASSES
    names: list[str] = []
    for part in raw.replace(" ", "").split(","):
        if part not in CLASSES:
            raise ValueError(f"Unknown memory class: {part or raw}")
        if part not in names:
            names.append(part)
    return tuple(names)


def authorize_resource(grants: Any, resource_id: str) -> MemoryPointer:
    """Refuse a resource id this process does not hold a pointer for."""

    wanted = str(resource_id or "")
    space = PointerSpace.from_grants("", grants)
    for pointer in space.pointers:
        if pointer.resource_id and pointer.resource_id == wanted:
            return pointer
    raise PermissionError("This range is outside this process's address space")


def authorize_selector(grants: Any, selector: str) -> list[tuple[str | None, str, int | None, int | None]]:
    """Parse a read selector and refuse anything outside this pointer space."""

    space = PointerSpace.from_grants("", grants)
    own = space.own()
    allowed = own.classes if own is not None else ()
    parsed = parse_selector(selector, allowed)
    for memory_name, class_name, _start, _end in parsed:
        space.require(class_name, memory_name)
    return parsed


def parse_selector(
    selector: str,
    allowed: tuple[str, ...],
) -> list[tuple[str | None, str, int | None, int | None]]:
    """Selectors inside an already authorized pointer. A bare class uses its own memory."""

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
        raise ValueError("Bad address")
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
        raise ValueError(f"Unknown memory class: {class_name}")
    if class_name not in allowed:
        raise PermissionError("This range is outside this process's address space")
    if not rest:
        return [(memory_name, class_name, None, None)]
    if len(rest) != 1:
        raise ValueError("Bad address")
    start, end = _span(rest[0])
    return [(memory_name, class_name, start, end)]


def _span(raw: str) -> tuple[int, int]:
    if "-" in raw:
        start_text, end_text = raw.split("-", 1)
    else:
        start_text = end_text = raw
    try:
        start = int(start_text)
        end = int(end_text)
    except ValueError as exc:
        raise ValueError("Bad address") from exc
    if start < 0 or end < start:
        raise ValueError("Bad address")
    return start, end


def _kind(item: Any) -> str:
    kind = getattr(item, "kind", "")
    return str(getattr(kind, "value", kind))


def _identity(item: Any) -> dict[str, Any]:
    identity = getattr(item, "identity", None)
    if isinstance(identity, dict) and identity:
        return identity
    metadata = getattr(item, "metadata", None) or {}
    if isinstance(metadata, dict):
        nested = metadata.get("identity")
        if isinstance(nested, dict):
            return nested
    return {}
