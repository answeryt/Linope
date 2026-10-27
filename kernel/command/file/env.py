"""Remember which env file later process starts should read."""

from __future__ import annotations

from pathlib import Path

from kernel.command.convention import UsageError, guard

USAGE = "usage: linope load env <path>"


@guard(USAGE)
def run(argv: list[str]) -> int:
    if len(argv) != 2 or argv[0] != "env":
        raise UsageError(USAGE)
    path = Path(argv[1]).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    path = path.resolve()
    if not path.is_file():
        raise UsageError(f"Env file does not exist: {path}")
    from kernel.command.window import current_window

    window = current_window()
    if window is not None:
        window.note_env(str(path))
    print(f"env_file={path}", flush=True)
    return 0
