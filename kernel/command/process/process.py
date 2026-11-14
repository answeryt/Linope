"""Process commands. ``start`` opens one capability and keeps its resource account."""

from __future__ import annotations

from typing import Any

from kernel.command.convention import UsageError, guard
from kernel.command.process.listen import (
    _print_list,
    _print_show,
    _print_trace,
    saved_list,
    saved_show,
    saved_trace,
)
from kernel.command.process.start import START_USAGE, run as start_capability

USAGE = (
    "usage: linope process start <capability> [--change topic=value] [--count count] "
    "[--share resource kind] [--with kind=identity] [--once] [--ping]\n"
    "      linope process list\n"
    "      linope process show <pid> [address]\n"
    "      linope process trace <pid>"
)


@guard(USAGE)
def run(
    argv: list[str],
    *,
    runtime: Any = None,
    request: dict[str, Any] | None = None,
) -> Any:
    del request
    if not argv:
        raise UsageError(USAGE)
    target = runtime
    if target is not None:
        result = _in_runtime(target, argv)
        if result is not False:
            return result
    if argv[0] == "start":
        return start_capability(argv[1:])
    if argv[0] == "list" and len(argv) == 1:
        return saved_list()
    if argv[0] == "show" and len(argv) == 2:
        return saved_show(argv[1])
    if argv[0] == "trace" and len(argv) == 2:
        return saved_trace(argv[1])
    raise UsageError(USAGE)


def _in_runtime(runtime: object, argv: list[str]) -> Any:
    """Run the process command against an explicit kernel runtime."""
    if argv[0] == "start":
        return runtime.launch(argv[1:])
    if argv[0] == "list" and len(argv) == 1:
        return _print_list(runtime)
    if argv[0] == "show" and len(argv) >= 2:
        return _print_show(runtime, argv[1], " ".join(argv[2:]))
    if argv[0] == "trace" and len(argv) == 2:
        return _print_trace(runtime, argv[1])
    return False
