"""An append-only journal of turns. Scheduling does not read it."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def journal_path(folder: str | Path | None = None) -> Path:
    """``.linope/log/session.jsonl`` under ``folder``, or under the working directory."""
    root = Path.cwd() if folder is None else Path(folder)
    return root / ".linope" / "log" / "session.jsonl"


def journal_beside(ledger_path: str | Path) -> Path:
    """The journal that sits next to one ledger file."""
    return Path(ledger_path).resolve().parent / "log" / "session.jsonl"


class Journal:
    """One JSON object per line. Earlier lines are left as they were written."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def append(self, event: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = {"time": datetime.now(timezone.utc).isoformat(), **event}
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(line, ensure_ascii=False) + "\n")

    def rows(self) -> tuple[dict[str, Any], ...]:
        if not self.path.is_file():
            return ()
        found: list[dict[str, Any]] = []
        for raw in self.path.read_text(encoding="utf-8").splitlines():
            if not raw.strip():
                continue
            found.append(json.loads(raw))
        return tuple(found)
