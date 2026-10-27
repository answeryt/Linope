"""Print the turn journal. It is not the activity trail."""

from __future__ import annotations

import json
import sys

from kernel.command.convention import UsageError, guard
from kernel.trace.journal import Journal, journal_path

USAGE = "usage: log [pid]"


@guard(USAGE)
def run(argv: list[str]) -> int:
    if len(argv) > 1:
        raise UsageError(USAGE)
    pid: int | None = None
    if argv:
        token = argv[0]
        if not token.isdigit() or int(token) <= 0:
            print("pid must be a number", file=sys.stderr)
            return 1
        pid = int(token)
    journal = Journal(journal_path())
    if not journal.path.is_file():
        print("No turn log yet", file=sys.stderr)
        return 1
    matched = 0
    for raw in journal.path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        if pid is None:
            print(raw, flush=True)
            matched += 1
            continue
        try:
            item = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if int(item.get("pid") or 0) == pid:
            print(raw, flush=True)
            matched += 1
    if pid is not None and matched == 0:
        print(f"Turn log has no such pid: {pid}", file=sys.stderr)
        return 1
    return 0
