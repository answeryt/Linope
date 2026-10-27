"""Look up an object command by name and run it."""

from __future__ import annotations

import sys

from kernel.command.file.create import run as create
from kernel.command.file.env import run as load_env
from kernel.command.log import run as show_log
from kernel.command.process.clerk import run as session
from kernel.command.process.process import run as process
from kernel.command.process.talk import run as talk
from kernel.command.screen.resource import run as resource
from kernel.command.service import run as service

COMMANDS = {
    "ask": talk,
    "create": create,
    "list": talk,
    "load": load_env,
    "log": show_log,
    "ping": talk,
    "process": process,
    "resource": resource,
    "service": service,
    "session": session,
    "show": talk,
    "terminal": session,
    "trace": talk,
}


def command_table() -> dict:
    """The object commands a person can type."""
    return dict(COMMANDS)


def usage() -> str:
    """One line for every object command."""
    lines = (
        "linope create <path> [-- name=value]",
        "linope load env <path>",
        "linope process start <capability>",
        "linope process list",
        "linope process show <pid> [address]",
        "linope process trace <pid>",
        "linope service start <pid> [<pid> ...]",
        "linope service load <service id> -- <body>",
        "linope resource serve",
        "linope log [pid]",
        "linope terminal",
        "linope session",
    )
    return "usage:\n" + "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Dispatch one CLI invocation. A usage error exits 2."""
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] == "linope":
        args = args[1:]
    if not args:
        print(usage(), file=sys.stderr)
        return 2
    if args[0] in {"help", "--help", "-h"}:
        print(usage())
        return 0
    if args[0] == "load" and args[1:2] != ["env"]:
        from kernel.command.process.talk import run as speak

        return speak(args[1:])
    command = COMMANDS.get(args[0])
    if command is None:
        print(usage(), file=sys.stderr)
        return 2
    return command(args[1:])
