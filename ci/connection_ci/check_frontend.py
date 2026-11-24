"""Fail when a frontend keeps a private prompt channel.

Run: python ci/connection_ci/check_frontend.py
"""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ELECTRON = ROOT / "ui" / "electron"
LOOPS = ROOT / "capability" / "agent_loop"


def sources(folder: Path, suffix: str) -> list[Path]:
    if not folder.is_dir():
        return []
    return [path for path in folder.rglob(f"*{suffix}") if "node_modules" not in path.parts]


def main() -> int:
    failures: list[str] = []
    for path in sources(ELECTRON, ".cjs"):
        text = path.read_text(encoding="utf-8")
        if "prompt:save" in text:
            failures.append(f"{path.relative_to(ROOT)}: prompt:save bypasses load message")
        if ".linope/prompts" in text and "readFile" in text:
            failures.append(f"{path.relative_to(ROOT)}: the desktop reads the prompt file itself")
    for path in sources(LOOPS, ".py") + sources(LOOPS, ".mjs"):
        text = path.read_text(encoding="utf-8")
        if ".linope/prompts" in text or ".linope\\prompts" in text:
            failures.append(f"{path.relative_to(ROOT)}: a loop reads the prompt file itself")
    if failures:
        print("\n".join(failures))
        print(f"{len(failures)} frontend boundary violation(s)")
        return 1
    print("frontend boundary check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
