"""Look up a command by name and run it."""

from __future__ import annotations

import sys

from kernel.command.catalog import specs
from kernel.command.parser import USAGE
from kernel.command.protocol import Command


def command_table() -> dict[str, Command]:
    """Build the name table from registered specifications."""
    table: dict[str, Command] = {}
    for spec in specs():
        _bind(table, spec.name, spec.run)
        for alias, runner in spec.aliases:
            _bind(table, alias, runner)
    return table


def main(argv: list[str] | None = None) -> int:
    """Dispatch one CLI invocation."""
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        raise SystemExit(USAGE)
    command = command_table().get(args[0])
    if command is None:
        raise SystemExit(USAGE)
    return command(args[1:])


def _bind(table: dict[str, Command], name: str, runner: Command) -> None:
    if name in table:
        raise RuntimeError(f"命令 {name} 登记了两次")
    table[name] = runner
