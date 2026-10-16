"""Look up an object command by name and run it."""

from __future__ import annotations

import sys

from kernel.command.capability import run as capability
from kernel.command.channel import run as channel
from kernel.command.env import run as env
from kernel.command.layout import run as layout
from kernel.command.process import run as process
from kernel.command.resource import run as resource
from kernel.command.service import run as service
from kernel.command.store import run as store
from kernel.command.terminal import run as terminal

COMMANDS = {
    "capability": capability,
    "channel": channel,
    "env": env,
    "layout": layout,
    "process": process,
    "resource": resource,
    "service": service,
    "store": store,
    "terminal": terminal,
}


def command_table() -> dict:
    """The object commands a person can type."""
    return dict(COMMANDS)


def usage() -> str:
    """One line for every object command."""
    lines = (
        "linope service create|status|bind|unbind|delete|call",
        "linope process start|list|status|stop|scale|share|workers",
        "linope resource serve|file",
        "linope capability load|call|chain|group|chord",
        "linope store current|use|check|init|migrate",
        "linope channel use|off",
        "linope layout use|off",
        "linope env init|use",
        "linope terminal",
    )
    return "用法:\n" + "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Dispatch one CLI invocation. A usage error exits 2."""
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print(usage(), file=sys.stderr)
        return 2
    if args[0] in {"help", "--help", "-h"}:
        print(usage())
        return 0
    command = COMMANDS.get(args[0])
    if command is None:
        print(usage(), file=sys.stderr)
        return 2
    return command(args[1:])
