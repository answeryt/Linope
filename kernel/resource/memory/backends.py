"""Memory backends. The kernel does not choose a database for the user."""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any, Protocol

from kernel.resource.memory.records import MemoryRow, class_of
from kernel.resource.memory.token_meter import estimate_tokens


class MemoryStore(Protocol):
    """The source of truth for one process lifetime or one durable file."""

    name: str

    def append(
        self,
        resource_id: str,
        *,
        scope: str,
        kind: str,
        content: str,
        row_state: str,
        when: str,
    ) -> MemoryRow: ...

    def write_system(
        self,
        resource_id: str,
        *,
        scope: str,
        name: str,
        text: str,
        place: int | None,
        when: str,
    ) -> MemoryRow: ...

    def row(self, resource_id: str, real: str) -> MemoryRow | None: ...

    def rows_of(self, resource_id: str, class_name: str) -> list[MemoryRow]: ...

    def seq(self, resource_id: str) -> int: ...

    def system_text(self, resource_id: str) -> str: ...

    def save_page(self, pid: str, resource_id: str, pages: dict[str, list[str]]) -> None: ...

    def load_page(self, pid: str, resource_id: str) -> dict[str, list[str]]: ...

    def drop_pages(self, resource_id: str) -> None: ...


def _row_from(real: str, class_name: str, kind: str, content: str, when: str, seq: int, row_state: str) -> MemoryRow:
    return MemoryRow(
        real=real,
        class_name=class_name,
        kind=kind,
        content=content,
        time=when,
        seq=seq,
        state=row_state,
        tokens=estimate_tokens(content),
        version=seq,
    )


class InMemoryStore:
    """Rows for this runtime only. Tests and the default backend use this."""

    name = "memory"

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._rows: dict[str, dict[str, MemoryRow]] = {}
        self._order: dict[str, dict[str, list[str]]] = {}
        self._seq: dict[str, int] = {}
        self._next: dict[str, dict[str, int]] = {}
        self._prompts: dict[str, list[dict[str, str]]] = {}
        self._system: dict[str, str] = {}
        self._pages: dict[tuple[str, str], dict[str, list[str]]] = {}
        self._scopes: dict[str, str] = {}

    def append(self, resource_id: str, *, scope: str, kind: str, content: str, row_state: str, when: str) -> MemoryRow:
        with self._lock:
            class_name = class_of(kind)
            nxt = self._next.setdefault(resource_id, {"message": 0, "task": 0, "artifact": 0})
            number = int(nxt.get(class_name) or 0)
            nxt[class_name] = number + 1
            seq = int(self._seq.get(resource_id) or 0) + 1
            self._seq[resource_id] = seq
            self._scopes[resource_id] = scope
            real = f"{class_name}/{number}"
            row = _row_from(real, class_name, kind, content, when, seq, row_state)
            self._rows.setdefault(resource_id, {})[real] = row
            self._order.setdefault(resource_id, {}).setdefault(class_name, []).append(real)
            return row

    def write_system(
        self,
        resource_id: str,
        *,
        scope: str,
        name: str,
        text: str,
        place: int | None,
        when: str,
    ) -> MemoryRow:
        with self._lock:
            sections = list(self._prompts.get(resource_id) or [])
            sections = _place_section(sections, name, text, place)
            joined = "\n\n".join(item["content"] for item in sections)
            seq = int(self._seq.get(resource_id) or 0) + 1
            self._seq[resource_id] = seq
            self._scopes[resource_id] = scope
            self._prompts[resource_id] = sections
            self._system[resource_id] = joined
            row = _row_from("system", "system", "system", joined, when, seq, "")
            self._rows.setdefault(resource_id, {})["system"] = row
            order = self._order.setdefault(resource_id, {}).setdefault("system", [])
            if "system" not in order:
                order.append("system")
            return row

    def row(self, resource_id: str, real: str) -> MemoryRow | None:
        with self._lock:
            return self._rows.get(resource_id, {}).get(real)

    def rows_of(self, resource_id: str, class_name: str) -> list[MemoryRow]:
        with self._lock:
            stored = self._rows.get(resource_id, {})
            return [stored[real] for real in self._order.get(resource_id, {}).get(class_name, []) if real in stored]

    def seq(self, resource_id: str) -> int:
        with self._lock:
            return int(self._seq.get(resource_id) or 0)

    def system_text(self, resource_id: str) -> str:
        with self._lock:
            return str(self._system.get(resource_id) or "")

    def save_page(self, pid: str, resource_id: str, pages: dict[str, list[str]]) -> None:
        with self._lock:
            self._pages[(pid, resource_id)] = {key: list(value) for key, value in pages.items()}

    def load_page(self, pid: str, resource_id: str) -> dict[str, list[str]]:
        with self._lock:
            found = self._pages.get((pid, resource_id))
            if not found:
                return {}
            return {key: list(value) for key, value in found.items()}

    def drop_pages(self, resource_id: str) -> None:
        with self._lock:
            for key in [item for item in self._pages if item[1] == resource_id]:
                self._pages.pop(key, None)


class SqliteStore:
    """One durable file. Selected by the user, never assumed."""

    name = "sqlite"

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._lock = threading.RLock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(self.path, check_same_thread=False)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.executescript(
            """
            CREATE TABLE IF NOT EXISTS rows (
                resource_id TEXT NOT NULL,
                real_name TEXT NOT NULL,
                class_name TEXT NOT NULL,
                kind TEXT NOT NULL,
                content TEXT NOT NULL,
                written_at TEXT NOT NULL,
                seq INTEGER NOT NULL,
                row_state TEXT NOT NULL,
                tokens INTEGER NOT NULL,
                PRIMARY KEY (resource_id, real_name)
            );
            CREATE TABLE IF NOT EXISTS counters (
                resource_id TEXT PRIMARY KEY,
                scope TEXT NOT NULL,
                seq INTEGER NOT NULL,
                message_next INTEGER NOT NULL,
                task_next INTEGER NOT NULL,
                artifact_next INTEGER NOT NULL,
                system_text TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS prompts (
                resource_id TEXT NOT NULL,
                name TEXT NOT NULL,
                content TEXT NOT NULL,
                place INTEGER NOT NULL,
                PRIMARY KEY (resource_id, name)
            );
            CREATE TABLE IF NOT EXISTS pages (
                pid TEXT NOT NULL,
                resource_id TEXT NOT NULL,
                body TEXT NOT NULL,
                PRIMARY KEY (pid, resource_id)
            );
            """
        )
        self._db.commit()

    def close(self) -> None:
        with self._lock:
            self._db.close()

    def append(self, resource_id: str, *, scope: str, kind: str, content: str, row_state: str, when: str) -> MemoryRow:
        with self._lock:
            class_name = class_of(kind)
            seq, nxt, _system = self._counter(resource_id, scope)
            number = nxt[class_name]
            nxt[class_name] = number + 1
            seq += 1
            real = f"{class_name}/{number}"
            row = _row_from(real, class_name, kind, content, when, seq, row_state)
            self._write_counter(resource_id, scope, seq, nxt, _system)
            self._db.execute(
                """
                INSERT OR REPLACE INTO rows (
                    resource_id, real_name, class_name, kind, content, written_at, seq, row_state, tokens
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (resource_id, real, class_name, kind, content, when, seq, row_state, row.tokens),
            )
            self._db.commit()
            return row

    def write_system(
        self,
        resource_id: str,
        *,
        scope: str,
        name: str,
        text: str,
        place: int | None,
        when: str,
    ) -> MemoryRow:
        with self._lock:
            sections = self._sections(resource_id)
            sections = _place_section(sections, name, text, place)
            self._db.execute("DELETE FROM prompts WHERE resource_id = ?", (resource_id,))
            for index, item in enumerate(sections, start=1):
                self._db.execute(
                    "INSERT INTO prompts (resource_id, name, content, place) VALUES (?, ?, ?, ?)",
                    (resource_id, item["name"], item["content"], index),
                )
            joined = "\n\n".join(item["content"] for item in sections)
            seq, nxt, _system = self._counter(resource_id, scope)
            seq += 1
            self._write_counter(resource_id, scope, seq, nxt, joined)
            row = _row_from("system", "system", "system", joined, when, seq, "")
            self._db.execute(
                """
                INSERT OR REPLACE INTO rows (
                    resource_id, real_name, class_name, kind, content, written_at, seq, row_state, tokens
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (resource_id, "system", "system", "system", joined, when, seq, "", row.tokens),
            )
            self._db.commit()
            return row

    def row(self, resource_id: str, real: str) -> MemoryRow | None:
        with self._lock:
            found = self._db.execute(
                """
                SELECT real_name, class_name, kind, content, written_at, seq, row_state, tokens
                FROM rows WHERE resource_id = ? AND real_name = ?
                """,
                (resource_id, real),
            ).fetchone()
            return None if found is None else _stored(found)

    def rows_of(self, resource_id: str, class_name: str) -> list[MemoryRow]:
        with self._lock:
            found = self._db.execute(
                """
                SELECT real_name, class_name, kind, content, written_at, seq, row_state, tokens
                FROM rows WHERE resource_id = ? AND class_name = ?
                ORDER BY seq, real_name
                """,
                (resource_id, class_name),
            ).fetchall()
            return [_stored(item) for item in found]

    def seq(self, resource_id: str) -> int:
        with self._lock:
            found = self._db.execute("SELECT seq FROM counters WHERE resource_id = ?", (resource_id,)).fetchone()
            return 0 if found is None else int(found[0])

    def system_text(self, resource_id: str) -> str:
        with self._lock:
            found = self._db.execute(
                "SELECT system_text FROM counters WHERE resource_id = ?",
                (resource_id,),
            ).fetchone()
            return "" if found is None else str(found[0] or "")

    def save_page(self, pid: str, resource_id: str, pages: dict[str, list[str]]) -> None:
        with self._lock:
            self._db.execute(
                "INSERT OR REPLACE INTO pages (pid, resource_id, body) VALUES (?, ?, ?)",
                (pid, resource_id, json.dumps(pages)),
            )
            self._db.commit()

    def load_page(self, pid: str, resource_id: str) -> dict[str, list[str]]:
        with self._lock:
            found = self._db.execute(
                "SELECT body FROM pages WHERE pid = ? AND resource_id = ?",
                (pid, resource_id),
            ).fetchone()
            if found is None:
                return {}
            raw = json.loads(found[0])
            return {str(key): [str(item) for item in value] for key, value in raw.items()}

    def drop_pages(self, resource_id: str) -> None:
        with self._lock:
            self._db.execute("DELETE FROM pages WHERE resource_id = ?", (resource_id,))
            self._db.commit()

    def _counter(self, resource_id: str, scope: str) -> tuple[int, dict[str, int], str]:
        found = self._db.execute(
            """
            SELECT seq, message_next, task_next, artifact_next, system_text
            FROM counters WHERE resource_id = ?
            """,
            (resource_id,),
        ).fetchone()
        if found is None:
            return 0, {"message": 0, "task": 0, "artifact": 0}, ""
        return (
            int(found[0]),
            {"message": int(found[1]), "task": int(found[2]), "artifact": int(found[3])},
            str(found[4] or ""),
        )

    def _write_counter(self, resource_id: str, scope: str, seq: int, nxt: dict[str, int], system: str) -> None:
        self._db.execute(
            """
            INSERT OR REPLACE INTO counters (
                resource_id, scope, seq, message_next, task_next, artifact_next, system_text
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (resource_id, scope, seq, nxt["message"], nxt["task"], nxt["artifact"], system),
        )

    def _sections(self, resource_id: str) -> list[dict[str, str]]:
        found = self._db.execute(
            "SELECT name, content FROM prompts WHERE resource_id = ? ORDER BY place",
            (resource_id,),
        ).fetchall()
        return [{"name": str(name), "content": str(content)} for name, content in found]


def _stored(found: tuple[Any, ...]) -> MemoryRow:
    return MemoryRow(
        real=str(found[0]),
        class_name=str(found[1]),
        kind=str(found[2]),
        content=str(found[3]),
        time=str(found[4]),
        seq=int(found[5]),
        state=str(found[6] or ""),
        tokens=int(found[7]),
        version=int(found[5]),
    )


def _place_section(
    sections: list[dict[str, str]],
    name: str,
    text: str,
    place: int | None,
) -> list[dict[str, str]]:
    label = str(name).strip()
    if not label:
        raise ValueError("Missing file")
    if place is not None and int(place) < 1:
        raise ValueError("Count starts at 1")
    index = next((i for i, item in enumerate(sections) if item["name"] == label), None)
    if index is not None:
        sections.pop(index)
    section = {"name": label, "content": text}
    if place is None and index is not None:
        sections.insert(index, section)
    elif place is None or int(place) - 1 >= len(sections):
        sections.append(section)
    else:
        sections.insert(int(place) - 1, section)
    return sections


def configured_backend(home: Path | None = None) -> tuple[str, str]:
    """Read the user's backend choice. Missing config means the memory backend."""

    root = home or Path.cwd()
    path = root / ".linope" / "memory-backend.json"
    if not path.is_file():
        return "memory", ""
    raw = json.loads(path.read_text(encoding="utf-8"))
    name = str(raw.get("name") or "memory")
    return name, str(raw.get("path") or "")


def write_backend_config(name: str, path: str = "", home: Path | None = None) -> Path:
    root = home or Path.cwd()
    folder = root / ".linope"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "memory-backend.json"
    body = {"name": name, "path": path}
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(body, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    temporary.replace(target)
    return target


def open_store(name: str | None = None, path: str = "", home: Path | None = None) -> MemoryStore:
    chosen, configured = configured_backend(home)
    backend = name or chosen
    location = path or configured
    if backend == "memory":
        return InMemoryStore()
    if backend == "sqlite":
        if not location:
            raise ValueError("sqlite backend requires a path")
        return SqliteStore(location)
    raise ValueError(f"Unknown memory backend: {backend}")
