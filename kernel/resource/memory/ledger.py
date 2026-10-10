"""Usage against one model's context window."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from kernel.resource.memory.page import Page


@dataclass(frozen=True)
class Ledger:
    window: int
    used: int

    def __post_init__(self) -> None:
        if self.window < 0:
            raise ValueError("window cannot be negative")
        if self.used < 0:
            raise ValueError("used cannot be negative")

    def fits(self) -> bool:
        return self.used <= self.window


def ledger_for(pages: Iterable[Page], *, window: int) -> Ledger:
    used = sum(page.size for page in pages if page.occupies_window())
    return Ledger(window=window, used=used)
