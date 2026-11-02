"""Shapes for logical memory. These are not physical pages."""

from __future__ import annotations

from dataclasses import dataclass


KIND_CLASS = {"user": "message", "model": "message", "tool": "artifact", "other": "task"}
STATES = ("asked", "continue", "resulted", "rejected", "answered")
RESIDENT = ("resident", "cold", "pinned")


def class_of(kind: str) -> str:
    if kind not in KIND_CLASS:
        raise ValueError(f"Unknown memory: {kind}")
    return KIND_CLASS[kind]


@dataclass(frozen=True)
class MemoryRow:
    """One stored line. ``real`` is the name inside the memory resource."""

    real: str
    class_name: str
    kind: str
    content: str
    time: str
    seq: int
    state: str = ""
    tokens: int = 0
    version: int = 1

    def view(self, address: str, name: str) -> dict[str, object]:
        found: dict[str, object] = {
            "address": address,
            "real": self.real,
            "name": name,
            "kind": self.kind,
            "content": self.content,
            "time": self.time,
            "seq": self.seq,
        }
        if self.state:
            found["state"] = self.state
        return found


@dataclass(frozen=True)
class MemoryBlock:
    """A logical block: one or more rows loaded and released together."""

    resource_id: str
    reals: tuple[str, ...]
    tokens: int
    version: int
    resident: str = "cold"

    def __post_init__(self) -> None:
        if self.resident not in RESIDENT:
            raise ValueError(f"Unknown residency: {self.resident}")


@dataclass(frozen=True)
class PageTableEntry:
    """One process-local address. It points at a real row, not a physical frame."""

    pid: str
    resource_id: str
    class_name: str
    position: int
    real: str
    resident: str = "cold"
    version: int = 1
    last_access: int = 0


@dataclass(frozen=True)
class PromptFootprint:
    """Tokens that would actually be sent, plus the room left for a read."""

    context_limit: int
    system_tokens: int = 0
    message_tokens: int = 0
    action_tokens: int = 0
    read_tokens: int = 0
    output_reserve: int = 0
    safety_margin: int = 0

    @property
    def used(self) -> int:
        return self.system_tokens + self.message_tokens + self.action_tokens + self.read_tokens

    @property
    def available(self) -> int:
        return self.context_limit - self.used - self.output_reserve - self.safety_margin

    @property
    def over_hard_limit(self) -> bool:
        return self.context_limit > 0 and self.used + self.output_reserve + self.safety_margin > self.context_limit
