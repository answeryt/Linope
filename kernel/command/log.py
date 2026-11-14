"""Return the turn journal. It is not the activity trail."""

from __future__ import annotations

import json

from kernel.command.convention import UsageError, guard
from kernel.trace.journal import Journal, journal_path

USAGE = "usage: log [pid]"


@guard(USAGE)
def run(argv: list[str]) -> list[dict]:
    if len(argv) > 1:
        raise UsageError(USAGE)
    pid: int | None = None
    if argv:
        token = argv[0]
        if not token.isdigit() or int(token) <= 0:
            raise ValueError("pid must be a number")
        pid = int(token)
    journal = Journal(journal_path())
    if not journal.path.is_file():
        raise FileNotFoundError("No turn log yet")
    rows: list[dict] = []
    for raw in journal.path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        if pid is None:
            item = json.loads(raw)
            if isinstance(item, dict):
                rows.append(item)
            continue
        try:
            item = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if int(item.get("pid") or 0) == pid:
            rows.append(item)
    if pid is not None and not rows:
        raise LookupError(f"Turn log has no such pid: {pid}")
    return rows
