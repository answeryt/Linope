"""Create a file, or write one name=value line into it."""

from __future__ import annotations

from pathlib import Path

from kernel.command.convention import UsageError, guard

USAGE = "usage: linope create <path> [-- name=value]"


@guard(USAGE)
def run(argv: list[str]) -> int:
    if not argv:
        raise UsageError(USAGE)
    if "--" in argv:
        index = argv.index("--")
        head, tail = argv[:index], argv[index + 1 :]
    else:
        head, tail = list(argv), []
    if len(head) != 1:
        raise UsageError(USAGE)
    path = _path(head[0])
    path.parent.mkdir(parents=True, exist_ok=True)
    if tail:
        if len(tail) != 1:
            raise UsageError(USAGE)
        key, value = _assignment(tail[0])
        _write_line(path, key, value)
    elif not path.exists():
        path.write_text("", encoding="utf-8")
    print(path)
    return 0


def _path(raw: str) -> Path:
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    return path.resolve()


def _assignment(raw: str) -> tuple[str, str]:
    if "=" not in raw:
        raise UsageError(USAGE)
    key, _, value = raw.partition("=")
    key = key.strip()
    if not key or "=" in key or "\x00" in key or "\x00" in value:
        raise UsageError(USAGE)
    return key, value


def _write_line(path: Path, key: str, value: str) -> None:
    lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    replaced = False
    kept: list[str] = []
    for line in lines:
        name, sep, _old = line.partition("=")
        if sep and name.strip() == key:
            kept.append(f"{key}={value}")
            replaced = True
        else:
            kept.append(line)
    if not replaced:
        kept.append(f"{key}={value}")
    text = "\n".join(kept)
    if text and not text.endswith("\n"):
        text += "\n"
    path.write_text(text, encoding="utf-8")
