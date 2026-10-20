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
        process_id: str,
        activity: str,
        counterpart: str = "",
        way: str = "",
    ) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = {
            "time": datetime.now(timezone.utc).isoformat(),
            "process_id": process_id,
            "activity": activity,
            "with": counterpart,
            "way": way,
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(line, ensure_ascii=False) + "\n")

    def for_process(self, process_id: str) -> tuple[dict[str, Any], ...]:
        if not self.path.is_file():
            return ()
        found: list[dict[str, Any]] = []
        for raw in self.path.read_text(encoding="utf-8").splitlines():
            if not raw.strip():
                continue
            item = json.loads(raw)
            if str(item.get("process_id") or "") == process_id:
                found.append(item)
        return tuple(found)

    def latest(self, process_id: str) -> dict[str, Any] | None:
        rows = self.for_process(process_id)
        if not rows:
            return None
        return rows[-1]
