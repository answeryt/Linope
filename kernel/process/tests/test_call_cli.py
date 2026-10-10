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
    command = [
        str(LINOPE),
        "call",
        CAPABILITY,
        *args,
        "--resource-store",
        str(store),
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
    assert result.stdout.count("'event': 'pong'") == 1


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
        (("ping",), 1),
        (("chain", "ping", "ping"), 1),
        (("group", "ping", "ping"), 2),
        (("chord", "ping", "ping", "--", "ping"), 1),
    )
    failed = 0
    for args, replies in checks:
        print(f"linope call {CAPABILITY} {' '.join(args)}")
        with tempfile.TemporaryDirectory() as directory:
            result = _run(Path(directory), *args)
        if result.returncode != 0 or result.stdout.count("'event': 'pong'") != replies:
            failed += 1
            print(result.stderr.strip() or result.stdout.strip())
        else:
            print(result.stdout.strip())
        print()
    return failed


if __name__ == "__main__":
    raise SystemExit(main())
