"""Several models measure one shared set of context pages."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from kernel.resource.memory.ledger import Ledger, ledger_for
from kernel.resource.memory.page import Page


@dataclass(frozen=True)
class Reader:
    model_id: str
    window: int

    def __post_init__(self) -> None:
        if not self.model_id:
            raise ValueError("model_id is required")
        if self.window < 0:
            raise ValueError("window cannot be negative")


def measure(pages: Iterable[Page], readers: Sequence[Reader]) -> tuple[Ledger, ...]:
    stored = tuple(pages)
    return tuple(ledger_for(stored, window=reader.window) for reader in readers)


def tightest_window(readers: Sequence[Reader]) -> int:
    if not readers:
        raise ValueError("at least one reader is required")
    return min(reader.window for reader in readers)
