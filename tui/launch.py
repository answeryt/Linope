"""Open the blue terminal, or pass every other command to the kernel."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args == ["terminal"]:
        return open_tui()
    from kernel.command.dispatch import main as dispatch

    return dispatch(args)


def open_tui() -> int:
    root = Path(__file__).resolve().parents[1]
    entry = root / "tui" / "main.ts"
    node = shutil.which("node")
    if node is None:
        print("Node.js is required to open the Linope terminal.", file=sys.stderr)
        return 1
    command = _runner(root, node, entry)
    if command is None:
        print("Node.js is required to open the Linope terminal.", file=sys.stderr)
        return 1
    env = os.environ.copy()
    env["LINOPE_PYTHON"] = sys.executable
    if os.name == "nt":
        completed = subprocess.run(command, env=env)
        return int(completed.returncode or 0)
    os.execvpe(command[0], command, env)
    return 1


def _runner(root: Path, node: str, entry: Path) -> list[str] | None:
    bin_name = "tsx.cmd" if os.name == "nt" else "tsx"
    tsx_bin = root / "ui-tui" / "node_modules" / ".bin" / bin_name
    cli = root / "ui-tui" / "node_modules" / "tsx" / "dist" / "cli.mjs"
    if tsx_bin.is_file() and cli.is_file():
        return [node, str(cli), str(entry)]
    if tsx_bin.is_file() and os.name != "nt":
        return [str(tsx_bin), str(entry)]
    npx = shutil.which("npx")
    if npx is None:
        return None
    return [npx, "--yes", "tsx", str(entry)]


if __name__ == "__main__":
    raise SystemExit(main())
