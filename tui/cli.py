"""Render one-shot kernel command values for a human or JSON host."""

from __future__ import annotations

import json
import sys
from typing import Any

from kernel.command.dispatch import main
from kernel.command.parser import UsageError


def run(argv: list[str]) -> int:
    """Run a command and choose presentation outside the kernel."""

    try:
        value = main(argv)
    except (UsageError, ValueError, KeyError, RuntimeError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if value is not None:
        if isinstance(value, str):
            print(value)
        else:
            print(json.dumps(value, ensure_ascii=False, default=str))
    return 0
