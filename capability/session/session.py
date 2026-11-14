"""One session is an address list for a memory scope.

The file records where a line lives. The words stay in memory. A later process
reads them back with the show command it already has.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


class SessionError(RuntimeError):
    """A session line can no longer be read."""


ReadRow = Callable[[str], dict[str, Any] | None]


@dataclass(frozen=True)
class IndexLine:
    """One committed address. The body is not here."""

    seq: int
    real: str
    kind: str
    tool_call_id: str = ""
    name: str = ""


class SessionLog:
    """An append-only list of memory addresses for one scope."""

    def __init__(
        self,
        root: Path,
        scope: str,
        *,
        clock: Callable[[], str] | None = None,
        ids: Callable[[], str] | None = None,
    ) -> None:
        self.scope = _safe_scope(scope)
        self.path = Path(root) / ".linope" / "sessions" / f"{self.scope}.jsonl"
        self._clock = clock or _utc_now
        self._ids = ids or (lambda: uuid.uuid4().hex)

    def ensure(self) -> None:
        """Write the header once. A later open leaves it in place."""

        if self.path.exists() and self.path.stat().st_size > 0:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        header = {"id": self._ids(), "scope": self.scope, "created": self._clock()}
        self.path.write_text(_line(header), encoding="utf-8")

    def entries(self) -> list[IndexLine]:
        """The addresses already committed, in the order they were written."""

        return _load(self.path)[1]

    def restart(self) -> SessionLog:
        """Drop this list. The rows it names are not in the memory now open."""

        if self.path.exists():
            self.path.unlink()
        self.ensure()
        return self

    def note(
        self,
        rows: list[dict[str, Any]],
        calls: list[tuple[str, str]] | None = None,
    ) -> list[IndexLine]:
        """Append addresses this file has not recorded. The body stays out."""

        self.ensure()
        known = self.entries()
        seen = max((item.seq for item in known), default=0)
        have = {item.real for item in known}
        fresh = _fresh(rows, seen, have)
        paired = _pair(fresh, list(calls or []))
        added: list[IndexLine] = []
        with self.path.open("a", encoding="utf-8") as handle:
            for row, call in zip(fresh, paired):
                item = IndexLine(
                    seq=int(row["seq"]),
                    real=str(row["real"]),
                    kind=str(row.get("kind") or ""),
                    tool_call_id=call[0] if call else "",
                    name=call[1] if call else "",
                )
                handle.write(_line(_record(item)))
                added.append(item)
                have.add(item.real)
        return added

    def messages(
        self,
        read: ReadRow,
        chosen: list[IndexLine] | None = None,
    ) -> list[dict[str, Any]]:
        """Rebuild the model messages. A missing row fails the session."""

        found: list[dict[str, Any]] = []
        for entry in self.entries() if chosen is None else chosen:
            row = read(entry.real)
            if not isinstance(row, dict) or str(row.get("real") or "") != entry.real:
                raise SessionError(f"This session line is gone: {entry.real}")
            found.append(_message(entry, row))
        return found


def parse_page(value: Any) -> dict[str, Any] | None:
    """Validate a structured process page returned by the kernel."""

    if isinstance(value, dict):
        payload = value
    elif isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return None
    else:
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def scope_of(page: dict[str, Any]) -> str:
    """The memory scope this page already links to."""

    links = page.get("links")
    if not isinstance(links, list):
        return ""
    for link in links:
        if isinstance(link, dict) and link.get("rel") == "memory":
            return str(link.get("resource") or "")
    return ""


def rows_of(page: dict[str, Any]) -> list[dict[str, Any]]:
    """Memory rows on this page. A page with no memory has none."""

    memory = page.get("memory")
    if not isinstance(memory, dict):
        return []
    items = memory.get("items")
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def _fresh(
    rows: list[dict[str, Any]],
    seen: int,
    have: set[str],
) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    taken = set(have)
    for row in rows:
        real = str(row.get("real") or "")
        try:
            seq = int(row.get("seq") or 0)
        except (TypeError, ValueError):
            continue
        if not real or real in taken or seq <= seen or seq <= 0:
            continue
        found.append(row)
        taken.add(real)
    found.sort(key=lambda item: int(item["seq"]))
    return found


def _pair(
    rows: list[dict[str, Any]],
    calls: list[tuple[str, str]],
) -> list[tuple[str, str] | None]:
    """Attach a tool call only when this page shows which new row it is."""

    marks: list[tuple[str, str] | None] = [None] * len(rows)
    if not calls or not rows:
        return marks
    if len(calls) == len(rows):
        return list(calls)
    if len(calls) != 1:
        return marks
    tool_rows = [index for index, row in enumerate(rows) if str(row.get("kind") or "") == "tool"]
    if len(rows) == 1 or len(tool_rows) == 1:
        marks[tool_rows[0] if tool_rows else 0] = calls[0]
    return marks


def _message(entry: IndexLine, row: dict[str, Any]) -> dict[str, Any]:
    content = str(row.get("content") or "")
    if entry.real == "system" or entry.kind == "system":
        return {"role": "system", "content": content}
    if entry.kind == "model":
        return {"role": "assistant", "content": content}
    if entry.kind == "tool":
        message: dict[str, Any] = {"role": "tool", "content": content}
        if entry.tool_call_id:
            message["tool_call_id"] = entry.tool_call_id
        if entry.name:
            message["name"] = entry.name
        return message
    if entry.kind == "user":
        return {"role": "user", "content": content}
    return {"role": entry.kind, "content": content}


def _record(item: IndexLine) -> dict[str, Any]:
    record: dict[str, Any] = {"seq": item.seq, "real": item.real, "kind": item.kind}
    if item.tool_call_id:
        record["tool_call_id"] = item.tool_call_id
    if item.name:
        record["name"] = item.name
    return record


def _load(path: Path) -> tuple[dict[str, Any], list[IndexLine]]:
    if not path.exists() or path.stat().st_size == 0:
        return {}, []
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not lines:
        return {}, []
    header = json.loads(lines[0])
    if not isinstance(header, dict) or "scope" not in header or "real" in header:
        raise SessionError("This session file is unreadable")
    entries: list[IndexLine] = []
    for line in lines[1:]:
        item = json.loads(line)
        if not isinstance(item, dict) or "real" not in item:
            raise SessionError("This session file is unreadable")
        entries.append(
            IndexLine(
                seq=int(item.get("seq") or 0),
                real=str(item.get("real") or ""),
                kind=str(item.get("kind") or ""),
                tool_call_id=str(item.get("tool_call_id") or ""),
                name=str(item.get("name") or ""),
            )
        )
    return header, entries


def _line(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False) + "\n"


def _safe_scope(scope: str) -> str:
    text = str(scope or "").strip()
    if not text or text in {".", ".."} or "/" in text or "\\" in text or ".." in text:
        raise ValueError(f"Bad session scope: {scope}")
    return text


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
