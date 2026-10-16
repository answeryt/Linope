"""Run the real linope call command for one call, chain, group, and chord."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LINOPE = ROOT / "linope.cmd"
CAPABILITY = "context.sliding_window"


def _run(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    store = tmp_path / "resources.json"
    mode = "call"
    operations = args
    tail: list[str] = []
    if args and args[0] in {"chain", "group", "chord"}:
        mode = args[0]
        operations = args[1:]
    if mode == "chord" and "--" in operations:
        split = operations.index("--")
        tail = ["--", *operations[split + 1 :]]
        operations = operations[:split]
    command = [
        str(LINOPE),
        "capability",
        mode,
        CAPABILITY,
        *operations,
        "--resource-store",
        str(store),
        *tail,
    ]
    return subprocess.run(
        subprocess.list2cmdline(command),
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=True,
        check=False,
    )


def test_linope_call_ping(tmp_path: Path) -> None:
    result = _run(tmp_path, "ping")
    assert result.returncode == 0, result.stderr
    assert "'event': 'pong'" in result.stdout


def test_linope_call_chain_ping_ping(tmp_path: Path) -> None:
    result = _run(tmp_path, "chain", "ping", "ping")
    assert result.returncode == 0, result.stderr
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    assert len(lines) == 3
    assert "'event': 'pong'" in lines[0]
    assert lines[1] == f"prior={lines[0]}"
    assert "'event': 'pong'" in lines[2]


def test_linope_call_group_ping_ping(tmp_path: Path) -> None:
    result = _run(tmp_path, "group", "ping", "ping")
    assert result.returncode == 0, result.stderr
    assert result.stdout.count("'event': 'pong'") == 2


def test_linope_call_chord_ping_ping(tmp_path: Path) -> None:
    result = _run(tmp_path, "chord", "ping", "ping", "--", "ping")
    assert result.returncode == 0, result.stderr
    assert result.stdout.count("'event': 'pong'") == 1


def main() -> int:
    """Run the four linope call commands and print each result."""
    checks = (
        (("ping",), lambda out: out.count("'event': 'pong'") == 1),
        (
            ("chain", "ping", "ping"),
            lambda out: "prior=" in out and out.count("'event': 'pong'") == 3,
        ),
        (("group", "ping", "ping"), lambda out: out.count("'event': 'pong'") == 2),
        (("chord", "ping", "ping", "--", "ping"), lambda out: out.count("'event': 'pong'") == 1),
    )
    failed = 0
    for args, accept in checks:
        print(f"linope capability {CAPABILITY} {' '.join(args)}")
        with tempfile.TemporaryDirectory() as directory:
            result = _run(Path(directory), *args)
        if result.returncode != 0 or not accept(result.stdout):
            failed += 1
            print(result.stderr.strip() or result.stdout.strip())
        else:
            print(result.stdout.strip())
        print()
    return failed


if __name__ == "__main__":
    raise SystemExit(main())
