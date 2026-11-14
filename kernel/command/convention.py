"""One parsed command line. Objects and subcommands live in the command modules."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from kernel.command.parser import UsageError, parse_flags, split_body


@dataclass
class Invocation:
    """The arguments one subcommand received."""

    position: tuple[str, ...] = ()
    options: dict[str, Any] = field(default_factory=dict)
    env_file: str = ""
    env_keys: tuple[str, ...] = ()
    json: bool = False
    body: str | None = None


@dataclass
class Line:
    """Fields shared by a call, a load, and a file command."""

    name: str = ""
    kind: str = ""
    body: str = ""
    words: tuple[str, ...] = ()
    choice: str = ""
    changes: tuple[tuple[str, str], ...] = ()
    count: int | None = None
    members: tuple[str, ...] = ()
    env_file: str = ""
    env_keys: tuple[str, ...] = ()
    mode: str = ""
    operations: tuple[str, ...] = ()
    final: str | None = None


def parse(argv: list[str], *, flags: dict[str, str], usage: str) -> Invocation:
    """Parse one subcommand. Hosts decide how usage failures are rendered."""
    del usage
    head, body = split_body(list(argv))
    position, options, env_file, env_keys, as_json = parse_flags(head, flags)
    return Invocation(
        position=position,
        options=options,
        env_file=env_file,
        env_keys=env_keys,
        json=as_json,
        body=body,
    )


def emit(value: Any, *, as_json: bool, text: str | None = None) -> Any:
    """Return a command value without selecting a presentation."""

    del as_json
    return value if text is None else text


def guard(usage: str):
    """Attach usage metadata while leaving errors to the host."""

    def wrap(function):
        def runner(*args: Any, **kwargs: Any) -> Any:
            try:
                return function(*args, **kwargs)
            except UsageError as exc:
                if not str(exc):
                    raise UsageError(usage) from exc
                raise

        runner.__usage__ = usage
        return runner

    return wrap
