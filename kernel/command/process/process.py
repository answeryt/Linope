"""Process commands. ``start`` opens one capability and keeps its resource account."""

from __future__ import annotations

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
from kernel.command.window import current_window

USAGE = (
    "用法: linope process start <能力> [--change 主题=值] [--count 份数] "
    "[--share 资源种类] [--with 种类=身份] [--once] [--ping]\n"
    "      linope process list\n"
    "      linope process show <进程号> [地址]\n"
    "      linope process trace <进程号>"
)


@guard(USAGE)
def run(argv: list[str]) -> int:
    if not argv:
        raise UsageError(USAGE)
    window = current_window()
    if window is not None and _in_window(window, argv):
        return 0
    if argv[0] == "start":
        return start_capability(argv[1:])
    if argv[0] == "list" and len(argv) == 1:
        return saved_list()
    if argv[0] == "show" and len(argv) == 2:
        return saved_show(argv[1])
    if argv[0] == "trace" and len(argv) == 2:
        return saved_trace(argv[1])
    raise UsageError(USAGE)


def _in_window(window: object, argv: list[str]) -> bool:
    """Run the process command against the living window. False leaves the CLI path."""
    if argv[0] == "start":
        window.launch(argv[1:])
        return True
    if argv[0] == "list" and len(argv) == 1:
        _print_list(window)
        return True
    if argv[0] == "show" and len(argv) >= 2:
        _print_show(window, argv[1], " ".join(argv[2:]))
        return True
    if argv[0] == "trace" and len(argv) == 2:
        _print_trace(window, argv[1])
        return True
    return False
