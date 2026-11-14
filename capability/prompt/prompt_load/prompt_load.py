"""The system prompt. Sections are read in order and joined into one text."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Section:
    """One piece of the system prompt."""

    name: str
    order: int
    path: Path


def sections() -> tuple[Section, ...]:
    """Identity, then the operating protocol, then the tool guidance."""

    capability = Path(__file__).resolve().parents[2]
    root = capability.parent
    card = capability / "prompt" / "prompt_card" / "linope"
    return (
        Section(name="identity", order=-100, path=card / "identity.md"),
        Section(name="protocol", order=0, path=root / "example" / "linope.md"),
        Section(name="tools", order=100, path=card / "system_02_tools.md"),
    )


def system_prompt() -> str:
    """The joined system prompt. A missing file fails here."""

    parts: list[str] = []
    for section in sorted(sections(), key=lambda item: item.order):
        text = section.path.read_text(encoding="utf-8").strip()
        if text:
            parts.append(text)
    return "\n\n".join(parts)
