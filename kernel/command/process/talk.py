"""Lines spoken to a process that is already open in this window."""

from __future__ import annotations

import sys

from kernel.command.process.listen import PING_TIMEOUT, _one_line
from kernel.command.window import current_line, current_window


def run(argv: list[str]) -> int:
    """Hand one recognized line to the living window."""
    del argv
    window = current_window()
    if window is None:
        from kernel.command.dispatch import usage

        print(usage(), file=sys.stderr)
        return 2
    raw = current_line()
    handed = _one_line(window, raw, PING_TIMEOUT, emit_done=False)
    if handed:
        window.close_once(raw)
    return 0
