"""Sectioned ledger envelope. Sections share one lock and one saved document."""

from __future__ import annotations

from typing import Any, Protocol


class LedgerSection(Protocol):
    """One slice of the saved document."""

    name: str
    flat_keys: tuple[str, ...]

    def export_part(self) -> dict[str, Any]:
        """Return this section's saved fields. The caller holds the lock."""

    def import_part(self, payload: dict[str, Any]) -> None:
        """Replace this section from saved fields. The caller holds the lock."""


def export_sections(sections: tuple[LedgerSection, ...]) -> dict[str, Any]:
    """Write every section under its own name. The caller holds the lock."""
    return {
        "version": 2,
        "sections": {section.name: section.export_part() for section in sections},
    }


def import_sections(
    sections: tuple[LedgerSection, ...],
    payload: dict[str, Any],
) -> None:
    """Load a version-2 document, or split an older flat document into sections."""
    version = int(payload.get("version") or 1)
    nested = payload.get("sections")
    if version >= 2 and isinstance(nested, dict):
        for section in sections:
            raw = nested.get(section.name) or {}
            if not isinstance(raw, dict):
                raw = {}
            section.import_part(raw)
        return
    for section in sections:
        section.import_part({key: payload.get(key) for key in section.flat_keys})
