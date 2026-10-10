"""Pages this process is allowed to see. The ledger still owns the pages."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


_STATES = {"resident", "pinned", "swapped"}


@dataclass(frozen=True)
class VisiblePage:
    """One page address the process may look at. Not the ledger's entity id."""

    address: str
    size: int
    state: str = "resident"

    def __post_init__(self) -> None:
        if not self.address:
            raise ValueError("page address is required")
        if self.size < 0:
            raise ValueError("page size cannot be negative")
        if self.state not in _STATES:
            raise ValueError(f"unknown page state: {self.state}")

    @property
    def resident_now(self) -> bool:
        return self.state != "swapped"

    def payload(self) -> dict[str, Any]:
        return {"address": self.address, "size": self.size, "state": self.state}

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "VisiblePage":
        return cls(
            address=str(payload["address"]),
            size=int(payload.get("size", 0)),
            state=str(payload.get("state", "resident")),
        )


@dataclass(frozen=True)
class MemoryDoor:
    """Empty when this process holds no memory handle."""

    pages: tuple[VisiblePage, ...] = ()

    def resident(self) -> tuple[VisiblePage, ...]:
        return tuple(page for page in self.pages if page.resident_now)

    def swapped(self) -> tuple[VisiblePage, ...]:
        return tuple(page for page in self.pages if page.state == "swapped")

    def payload(self) -> dict[str, Any]:
        return {"pages": [page.payload() for page in self.pages]}

    @classmethod
    def from_payload(cls, payload: dict[str, Any] | None) -> "MemoryDoor":
        raw = dict(payload or {})
        return cls(
            pages=tuple(
                VisiblePage.from_payload(item) for item in raw.get("pages", ())
            )
        )

    @classmethod
    def from_grants(cls, grants: tuple[object, ...]) -> "MemoryDoor":
        pages: list[VisiblePage] = []
        for grant in grants:
            if _kind(grant) != "memory":
                continue
            listed = _metadata(grant).get("pages")
            if isinstance(listed, list) and listed:
                for item in listed:
                    if isinstance(item, dict) and item.get("address"):
                        pages.append(VisiblePage.from_payload(item))
                continue
            limits = getattr(grant, "limits", {}) or {}
            size = int(limits.get("bytes", limits.get("size", 0)) or 0)
            pages.append(
                VisiblePage(address=str(grant.handle), size=size, state="resident")
            )
        return cls(pages=tuple(pages))


def _kind(grant: object) -> str:
    kind = getattr(grant, "kind", "")
    return str(getattr(kind, "value", kind))


def _metadata(grant: object) -> dict[str, Any]:
    metadata = getattr(grant, "metadata", {}) or {}
    return dict(metadata) if isinstance(metadata, dict) else {}
