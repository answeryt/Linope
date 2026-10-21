"""One append-only trail of what each capability is doing."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class ActivityLog:
    """sleeping, self, with, and closed, in the order they happened."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def append(
        self,
        pid: int,
        activity: str,
        counterpart: str = "",
        way: str = "",
    ) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = {
            "time": datetime.now(timezone.utc).isoformat(),
            "pid": int(pid),
            "activity": activity,
            "with": counterpart,
            "way": way,
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(line, ensure_ascii=False) + "\n")

    def forget(self, pid: int) -> None:
        """Drop earlier rows for this pid so a reused process number starts clean."""
        if not self.path.is_file():
            return
        kept: list[str] = []
        for raw in self.path.read_text(encoding="utf-8").splitlines():
            if not raw.strip():
                continue
            item = json.loads(raw)
            if int(item.get("pid") or 0) == int(pid):
                continue
            kept.append(raw)
        text = ""
        if kept:
            text = "\n".join(kept) + "\n"
        self.path.write_text(text, encoding="utf-8")

    def for_process(self, pid: int) -> tuple[dict[str, Any], ...]:
        if not self.path.is_file():
            return ()
        found: list[dict[str, Any]] = []
        for raw in self.path.read_text(encoding="utf-8").splitlines():
            if not raw.strip():
                continue
            item = json.loads(raw)
            if int(item.get("pid") or 0) == int(pid):
                found.append(item)
        return tuple(found)

    def latest(self, pid: int) -> dict[str, Any] | None:
        rows = self.for_process(pid)
        if not rows:
            return None
        return rows[-1]
