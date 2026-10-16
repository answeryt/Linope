"""One parsed command line. Objects and subcommands live in the command modules."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from typing import Any

from kernel.command.parser import UsageError, parse_flags, split_body


@dataclass
class Invocation:
    """The arguments one subcommand received."""

    position: tuple[str, ...] = ()
    options: dict[str, Any] = field(default_factory=dict)
    store: str = ""
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
    store: str = ""
    env_file: str = ""
    env_keys: tuple[str, ...] = ()
    mode: str = ""
    operations: tuple[str, ...] = ()
    final: str | None = None


def parse(argv: list[str], *, flags: dict[str, str], usage: str) -> Invocation:
    """Parse one subcommand. ``usage`` is printed by the caller when this fails."""
    del usage
    head, body = split_body(list(argv))
    position, options, store, env_file, env_keys, as_json = parse_flags(head, flags)
    return Invocation(
        position=position,
        options=options,
        store=store,
        env_file=env_file,
        env_keys=env_keys,
        json=as_json,
        body=body,
    )


def emit(value: Any, *, as_json: bool, text: str | None = None) -> None:
    """Print either one JSON document or the human line."""
    if as_json:
        print(json.dumps(value, ensure_ascii=False, default=str))
        return
    print(value if text is None else text)


def guard(usage: str):
    """Turn a usage error into exit code 2. Runtime errors stay in the command."""

    def wrap(function):
        def runner(*args: Any, **kwargs: Any) -> int:
            try:
                return function(*args, **kwargs)
            except UsageError as exc:
                print(exc, file=sys.stderr)
                return 2

        runner.__usage__ = usage
        return runner

    return wrap
