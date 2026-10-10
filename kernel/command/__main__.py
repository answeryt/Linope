"""Run the kernel command line: ``python -m kernel.command``."""

from __future__ import annotations

from kernel.command.dispatch import main

if __name__ == "__main__":
    raise SystemExit(main())
