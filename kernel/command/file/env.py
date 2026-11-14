"""Remember which env file later process starts should read."""

from __future__ import annotations

from pathlib import Path

from kernel.command.convention import UsageError, guard

USAGE = "usage: linope load env <path>"


@guard(USAGE)
def run(
    argv: list[str],
    *,
    runtime: object = None,
    request: dict[str, object] | None = None,
) -> int:
    del request
    if len(argv) != 2 or argv[0] != "env":
        raise UsageError(USAGE)
    from capability.sandbox.access import resolve_path, resolve_policy

    policy = resolve_policy(
        {
            "scope": "host",
            "mode": "danger-full-access",
            "cwd": str(Path.cwd()),
        }
    )
    path = resolve_path(argv[1], policy, write=False)
    if not path.is_file():
        raise UsageError(f"Env file does not exist: {path}")
    target = runtime
    if target is not None:
        target.note_env(str(path))
    return {"env_file": str(path)}
