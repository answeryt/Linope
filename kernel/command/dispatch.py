"""Look up an object command by name and run it."""

from __future__ import annotations

import sys
from typing import Any

from kernel.command.file.create import run as create
from kernel.command.memory import run as memory_backend
from kernel.command.file.env import run as load_env
from kernel.command.log import run as show_log
from kernel.command.model import run as model
from kernel.command.process.clerk import run as session
from kernel.command.process.process import run as process
from kernel.command.process.talk import run as talk
from kernel.command.screen.resource import run as resource
from kernel.command.service import run as service
from kernel.command.parser import UsageError

COMMANDS = {
    "ask": talk,
    "create": create,
    "list": talk,
    "load": load_env,
    "memory": memory_backend,
    "model": model,
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


def usage() -> tuple[str, ...]:
    """Return command syntax as data for a host help renderer."""

    return (
        "linope create <path> [-- name=value]",
        "linope load env <path>",
        "linope process start <capability>",
        "linope process list",
        "linope process show <pid> [address]",
        "linope process trace <pid>",
        "linope model cores <count>",
        "linope model use <model capability> [--change topic=value]",
        "linope model run -- <message or JSON request>",
        "linope service start <pid> [<pid> ...]",
        "linope service load <service id> -- <body>",
        "linope memory backend [memory | sqlite --path <file>]",
        "linope resource serve",
        "linope log [pid]",
        "linope terminal",
        "linope session",
    )


def main(
    argv: list[str] | None = None,
    *,
    runtime: Any = None,
    request: dict[str, Any] | None = None,
) -> object:
    """Dispatch one CLI invocation. A usage error exits 2."""
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] == "linope":
        args = args[1:]
    if not args:
        raise UsageError("missing_command")
    if args[0] in {"help", "--help", "-h"}:
        return {"commands": usage()}
    if args[0] == "load" and args[1:2] != ["env"]:
        from kernel.command.process.talk import run as speak

        return speak(args[1:], runtime=runtime, request=request)
    command = COMMANDS.get(args[0])
    if command is None:
        raise UsageError("unknown_command")
    if command in {process, talk, load_env, model, service}:
        return command(args[1:], runtime=runtime, request=request)
    return command(args[1:])
