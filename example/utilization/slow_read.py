"""Wait, then print a file or the names in a directory.

Both experiment arms call this same script. A directory stands in for a fast
local lookup. A positive ``seconds`` is the controlled wait used to measure
model idle time.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path


def read_target(path: Path, seconds: float) -> str:
    """Wait, then return file text or a sorted directory listing."""

    if seconds < 0:
        raise ValueError("seconds must be zero or greater")
    if seconds:
        time.sleep(seconds)
    if path.is_dir():
        names = sorted(item.name for item in path.iterdir())
        return "\n".join(names)
    return path.read_text(encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", required=True)
    parser.add_argument("--seconds", type=float, default=0)
    args = parser.parse_args(argv)
    print(read_target(Path(args.path), args.seconds), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
