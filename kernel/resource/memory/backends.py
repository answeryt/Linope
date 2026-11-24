"""Memory backends. The kernel does not choose a database for the user."""

from __future__ import annotations

import json
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

    def restore(
        self,
        resource_id: str,
        *,
        scope: str,
        seq: int,
        nxt: dict[str, int],
        prompts: list[dict[str, str]],
        system: str,
        rows: list[MemoryRow],
        system_row: MemoryRow | None,
    ) -> None:
        """Install rows read from a folder. Page tables stay empty."""

        with self._lock:
            self._scopes[resource_id] = scope
            self._seq[resource_id] = seq
            self._next[resource_id] = {
                "message": int(nxt.get("message") or 0),
                "task": int(nxt.get("task") or 0),
                "artifact": int(nxt.get("artifact") or 0),
            }
            self._prompts[resource_id] = [
                {"name": str(item.get("name") or ""), "content": str(item.get("content") or "")}
                for item in prompts
            ]
            self._system[resource_id] = system
            stored: dict[str, MemoryRow] = {}
            order: dict[str, list[str]] = {}
            for row in rows:
                stored[row.real] = row
                order.setdefault(row.class_name, []).append(row.real)
            if system_row is not None:
                stored["system"] = system_row
                order.setdefault("system", [])
                if "system" not in order["system"]:
                    order["system"].append("system")
            self._rows[resource_id] = stored
            self._order[resource_id] = order

    def state_snapshot(self, resource_id: str) -> dict[str, Any]:
        with self._lock:
            nxt = self._next.get(resource_id) or {"message": 0, "task": 0, "artifact": 0}
            body: dict[str, Any] = {
                "next": {
                    "message": int(nxt.get("message") or 0),
                    "task": int(nxt.get("task") or 0),
                    "artifact": int(nxt.get("artifact") or 0),
                },
                "prompts": [dict(item) for item in self._prompts.get(resource_id) or []],
                "scope": str(self._scopes.get(resource_id) or ""),
                "seq": int(self._seq.get(resource_id) or 0),
                "system": str(self._system.get(resource_id) or ""),
            }
            system_row = self._rows.get(resource_id, {}).get("system")
            if system_row is not None:
                body["system_seq"] = system_row.seq
                body["system_time"] = system_row.time
                body["system_tokens"] = system_row.tokens
            return body

    def page_snapshot(self, resource_id: str) -> dict[str, dict[str, list[str]]]:
        with self._lock:
            return {
                pid: {key: list(value) for key, value in pages.items()}
                for (pid, stored_id), pages in self._pages.items()
                if stored_id == resource_id
            }


class LocalStore:
    """One folder of dictionaries. Selected by the user, never assumed."""

    name = "local"

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._lock = threading.RLock()
        self._inner = InMemoryStore()
        self._loaded: set[str] = set()
        self.path.mkdir(parents=True, exist_ok=True)
        self._clear_saved_pages()

    def append(self, resource_id: str, *, scope: str, kind: str, content: str, row_state: str, when: str) -> MemoryRow:
        with self._lock:
            self._ensure(resource_id)
            row = self._inner.append(
                resource_id,
                scope=scope,
                kind=kind,
                content=content,
                row_state=row_state,
                when=when,
            )
            folder = self._folder(resource_id)
            folder.mkdir(parents=True, exist_ok=True)
            with (folder / "rows.jsonl").open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(_row_body(row), ensure_ascii=False, sort_keys=True) + "\n")
            _replace_json(folder / "state.json", self._inner.state_snapshot(resource_id))
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
            self._ensure(resource_id)
            row = self._inner.write_system(
                resource_id,
                scope=scope,
                name=name,
                text=text,
                place=place,
                when=when,
            )
            folder = self._folder(resource_id)
            folder.mkdir(parents=True, exist_ok=True)
            _replace_json(folder / "state.json", self._inner.state_snapshot(resource_id))
            return row

    def row(self, resource_id: str, real: str) -> MemoryRow | None:
        with self._lock:
            self._ensure(resource_id)
            return self._inner.row(resource_id, real)

    def rows_of(self, resource_id: str, class_name: str) -> list[MemoryRow]:
        with self._lock:
            self._ensure(resource_id)
            return self._inner.rows_of(resource_id, class_name)

    def seq(self, resource_id: str) -> int:
        with self._lock:
            self._ensure(resource_id)
            return self._inner.seq(resource_id)

    def system_text(self, resource_id: str) -> str:
        with self._lock:
            self._ensure(resource_id)
            return self._inner.system_text(resource_id)

    def save_page(self, pid: str, resource_id: str, pages: dict[str, list[str]]) -> None:
        with self._lock:
            self._ensure(resource_id)
            self._inner.save_page(pid, resource_id, pages)
            folder = self._folder(resource_id)
            folder.mkdir(parents=True, exist_ok=True)
            _replace_json(folder / "pages.json", self._inner.page_snapshot(resource_id))

    def load_page(self, pid: str, resource_id: str) -> dict[str, list[str]]:
        with self._lock:
            self._ensure(resource_id)
            return self._inner.load_page(pid, resource_id)

    def drop_pages(self, resource_id: str) -> None:
        with self._lock:
            if resource_id in self._loaded:
                self._inner.drop_pages(resource_id)
            pages = self._folder(resource_id) / "pages.json"
            if pages.is_file():
                pages.unlink()

    def _ensure(self, resource_id: str) -> None:
        if resource_id in self._loaded:
            return
        self._load(resource_id)
        self._loaded.add(resource_id)

    def _load(self, resource_id: str) -> None:
        folder = self._folder(resource_id)
        rows = _read_rows(folder / "rows.jsonl")
        raw = _read_json(folder / "state.json")
        nxt = {"message": 0, "task": 0, "artifact": 0}
        saved_next = raw.get("next") if isinstance(raw.get("next"), dict) else {}
        for key in nxt:
            nxt[key] = int(saved_next.get(key) or 0)
        for row in rows:
            if row.class_name not in nxt:
                continue
            part = row.real.rsplit("/", 1)[-1]
            if part.isdigit():
                nxt[row.class_name] = max(nxt[row.class_name], int(part) + 1)
        prompts = []
        for item in raw.get("prompts") or []:
            if isinstance(item, dict):
                prompts.append({"name": str(item.get("name") or ""), "content": str(item.get("content") or "")})
        system = str(raw.get("system") or "")
        system_seq = int(raw.get("system_seq") or 0)
        system_row = None
        if system or system_seq or raw.get("system_time"):
            system_row = MemoryRow(
                real="system",
                class_name="system",
                kind="system",
                content=system,
                time=str(raw.get("system_time") or ""),
                seq=system_seq,
                state="",
                tokens=int(raw.get("system_tokens") or estimate_tokens(system)),
                version=system_seq,
            )
        seq = max(
            int(raw.get("seq") or 0),
            system_seq,
            max((row.seq for row in rows), default=0),
        )
        scope = str(raw.get("scope") or "")
        self._inner.restore(
            resource_id,
            scope=scope,
            seq=seq,
            nxt=nxt,
            prompts=prompts,
            system=system,
            rows=rows,
            system_row=system_row,
        )

    def _folder(self, resource_id: str) -> Path:
        return self.path / _folder_name(resource_id)

    def _clear_saved_pages(self) -> None:
        for pages in self.path.glob("*/pages.json"):
            pages.unlink()


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


_RESERVED = {"CON", "PRN", "AUX", "NUL"} | {f"COM{number}" for number in range(1, 10)} | {f"LPT{number}" for number in range(1, 10)}


def _folder_name(resource_id: str) -> str:
    encoded = "".join(char if char.isalnum() or char in "._-" else f"%{ord(char):02X}" for char in resource_id)
    encoded = encoded.rstrip(" .")
    stem = encoded.split(".", 1)[0].upper()
    if not encoded or stem in _RESERVED:
        encoded = f"_{encoded}"
    return encoded


def _row_body(row: MemoryRow) -> dict[str, Any]:
    return {
        "class": row.class_name,
        "content": row.content,
        "kind": row.kind,
        "real": row.real,
        "seq": row.seq,
        "state": row.state,
        "time": row.time,
        "tokens": row.tokens,
    }


def _read_rows(path: Path) -> list[MemoryRow]:
    if not path.is_file():
        return []
    rows: list[MemoryRow] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        raw = json.loads(line)
        if not isinstance(raw, dict):
            raise ValueError("memory row is not an object")
        seq = int(raw.get("seq") or 0)
        rows.append(
            MemoryRow(
                real=str(raw.get("real") or ""),
                class_name=str(raw.get("class") or raw.get("class_name") or ""),
                kind=str(raw.get("kind") or ""),
                content=str(raw.get("content") or ""),
                time=str(raw.get("time") or ""),
                seq=seq,
                state=str(raw.get("state") or ""),
                tokens=int(raw.get("tokens") or 0),
                version=seq,
            )
        )
    return rows


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("memory state is not an object")
    return raw


def _replace_json(path: Path, body: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(body, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    temporary.replace(path)


def configured_backend(home: Path | None = None) -> tuple[str, str]:
    """Read the user's backend choice. Missing config means the memory backend."""

    root = home or Path.cwd()
    path = root / ".linope" / "memory-backend.json"
    if not path.is_file():
        return "memory", ""
    raw = json.loads(path.read_text(encoding="utf-8"))
    name = str(raw.get("name") or "memory")
    if name == "sqlite":
        return "memory", ""
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
    if backend == "local":
        if not str(location).strip():
            raise ValueError("local backend requires a path")
        folder = Path(location)
        if not folder.is_absolute():
            folder = (home or Path.cwd()) / folder
        return LocalStore(folder)
    raise ValueError(f"Unknown memory backend: {backend}")
