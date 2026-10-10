"""Command specification shared by every CLI entry."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

Command = Callable[[list[str]], int]


@dataclass(frozen=True)
class CommandSpec:
    """One substitutable command.

    ``aliases`` are extra names. Each alias carries its own runner so a
    listing command can sit beside the command that changes state, without
    the dispatcher knowing either name.
    """

    name: str
    run: Command
    aliases: tuple[tuple[str, Command], ...] = ()
