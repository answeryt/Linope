"""Linux-style command parsing: object, subcommand, long options, and a body."""

from __future__ import annotations

from kernel.process.profile import Change
from kernel.resource.store.locator import default_store_locator

_GLOBAL = {
    "resource-store": "str",
    "env-file": "str",
    "env": "repeat",
    "json": "bool",
}


class UsageError(Exception):
    """The command line does not match the grammar. The process exits 2."""


def env_key(raw: str) -> str:
    """Validate an environment key whose value lives in a file."""
    key = raw.strip()
    if not key or "=" in key or "\x00" in key:
        raise UsageError("命令只写键名，值放在环境文件里")
    return key


def parse_changes(raw: list[str]) -> tuple[Change, ...]:
    """Turn repeated ``key=value`` options into profile changes."""
    parsed: list[Change] = []
    for item in raw:
        if "=" not in item:
            raise UsageError("change 的写法是：--change 主题=值")
        topic, value = item.split("=", 1)
        if not topic:
            raise UsageError("change 的写法是：--change 主题=值")
        parsed.append((topic, value))
    return tuple(parsed)


def split_body(argv: list[str]) -> tuple[list[str], str | None]:
    """``--`` starts the free text. It is not an option."""
    if "--" not in argv:
        return list(argv), None
    index = argv.index("--")
    return argv[:index], " ".join(argv[index + 1 :])


def parse_flags(
    argv: list[str],
    flags: dict[str, str],
) -> tuple[tuple[str, ...], dict[str, object], str, str, tuple[str, ...], bool]:
    """Read positionals, declared options, and the global ledger/env/json options."""
    known = dict(_GLOBAL)
    known.update(flags)
    position: list[str] = []
    values: dict[str, object] = {}
    for name, kind in known.items():
        if kind == "bool":
            values[name] = False
        elif kind == "repeat":
            values[name] = []
        else:
            values[name] = None
    index = 0
    while index < len(argv):
        token = argv[index]
        if token == "--" or not token.startswith("--"):
            position.append(token)
            index += 1
            continue
        name, inline = _split_flag(token)
        kind = known.get(name)
        if kind is None:
            raise UsageError(f"不认识的选项: --{name}")
        if kind == "bool":
            if inline is not None:
                raise UsageError(f"--{name} 不带值")
            values[name] = True
            index += 1
            continue
        if inline is None:
            if index + 1 >= len(argv) or argv[index + 1].startswith("--"):
                raise UsageError(f"--{name} 后面要写值")
            raw = argv[index + 1]
            index += 2
        else:
            raw = inline
            index += 1
        if kind == "repeat":
            cast = values[name]
            if isinstance(cast, list):
                cast.append(raw)
            continue
        values[name] = _coerce(name, kind, raw)
    store = values.pop("resource-store")
    env_file = values.pop("env-file")
    env_values = values.pop("env")
    as_json = bool(values.pop("json"))
    keys = tuple(env_key(item) for item in env_values) if isinstance(env_values, list) else ()
    if keys and not env_file:
        raise UsageError("还没指定环境文件，不能选择键")
    return (
        tuple(position),
        values,
        str(store or default_store_locator()),
        str(env_file or ""),
        keys,
        as_json,
    )


def require_position(position: tuple[str, ...], count: int, usage: str) -> None:
    """Reject a command that does not have the expected number of arguments."""
    if len(position) != count:
        raise UsageError(usage)


def optional_count(raw: object) -> int | None:
    """``--count`` is absent or a positive integer."""
    if raw is None:
        return None
    number = int(raw)
    if number < 1:
        raise UsageError("份数至少为 1")
    return number


def _split_flag(token: str) -> tuple[str, str | None]:
    raw = token[2:]
    if "=" in raw:
        name, value = raw.split("=", 1)
        return name, value
    return raw, None


def _coerce(name: str, kind: str, raw: str) -> object:
    if kind == "int":
        try:
            return int(raw)
        except ValueError as exc:
            raise UsageError(f"--{name} 后面要写整数") from exc
    if kind == "float":
        try:
            return float(raw)
        except ValueError as exc:
            raise UsageError(f"--{name} 后面要写数字") from exc
    return raw
