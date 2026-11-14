"""Fail when kernel source takes on capability work.

Run: python ci/kernel_ci/check_boundary.py
"""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
KERNEL = ROOT / "kernel"

# These are the boundary rules. A match is a kernel file doing capability work.
RULES = (
    ("import capability", "kernel imports a capability package"),
    ("from capability", "kernel imports a capability package"),
    ("spec_from_file_location", "kernel loads a plugin file itself"),
    ("package.json", "kernel reads a package manifest"),
    ("linope.id", "kernel understands a package id"),
    ("linope.command", "kernel understands a package command"),
    ("model_turn", "kernel runs a model turn"),
    ('"role": "user"', "kernel writes a chat role"),
    ('"role": "system"', "kernel writes a chat role"),
    ("startswith(\"tools.\")", "kernel chooses tool offers"),
    ("startswith(\"model.\")", "kernel chooses model offers"),
    ("startswith('tools.')", "kernel chooses tool offers"),
    ("startswith('model.')", "kernel chooses model offers"),
)

COMMAND_OUTPUT_RULES = (
    ("import tui", "kernel command imports a UI package"),
    ("from tui", "kernel command imports a UI package"),
    ("print(", "kernel command writes human output"),
    ("sys.stdout", "kernel command owns stdout"),
    ("sys.stderr", "kernel command owns stderr"),
    ("redirect_stdout", "kernel command captures presentation output"),
    ("redirect_stderr", "kernel command captures presentation output"),
    ('"pid="', "kernel command emits a legacy pid display line"),
    ('"type": "done"', "kernel command emits a legacy completion display event"),
    ('"type": "model"', "kernel command emits a legacy model display event"),
    ('"type": "waiting"', "kernel command emits a legacy waiting display event"),
)


def sources() -> list[Path]:
    found: list[Path] = []
    for path in KERNEL.rglob("*.py"):
        if "tests" in path.parts:
            continue
        found.append(path)
    return found


def main() -> int:
    failures: list[str] = []
    for path in sources():
        text = path.read_text(encoding="utf-8")
        rules = RULES
        relative_parts = path.relative_to(ROOT).parts
        if "command" in relative_parts and path.name != "__main__.py":
            rules = (*rules, *COMMAND_OUTPUT_RULES)
        for needle, reason in rules:
            if needle not in text:
                continue
            for number, line in enumerate(text.splitlines(), start=1):
                if needle in line:
                    relative = path.relative_to(ROOT)
                    failures.append(f"{relative}:{number}: {reason}: {line.strip()}")
    allowed = {
        "ask",
        "create",
        "list",
        "load",
        "memory",
        "log",
        "ping",
        "process",
        "resource",
        "service",
        "session",
        "terminal",
        "trace",
        "show",
    }
    dispatch = (KERNEL / "command" / "dispatch.py").read_text(encoding="utf-8")
    start = dispatch.find("COMMANDS = {")
    end = dispatch.find("\n}", start)
    block = dispatch[start:end] if start >= 0 else ""
    for line in block.splitlines():
        stripped = line.strip()
        if not stripped.startswith('"'):
            continue
        key = stripped.split('"', 2)[1]
        if key not in allowed:
            failures.append(
                f"kernel/command/dispatch.py: command {key!r} is not a kernel command"
            )
    if failures:
        print("\n".join(failures))
        print(f"{len(failures)} kernel boundary violation(s)")
        return 1
    print("kernel boundary check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
