"""Page tables, a runtime cache, and address reads. The model prompt is not this cache."""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any

from kernel.resource.memory.backends import MemoryStore, open_store
from kernel.resource.memory.fit import fit_named_read
from kernel.resource.memory.records import STATES, MemoryRow, PageTableEntry, class_of
from kernel.scheduler.memory_space import CLASSES


class _ScopeLock:
    def __init__(self) -> None:
        self._guard = threading.Lock()
        self._locks: dict[str, threading.RLock] = {}

    def get(self, resource_id: str) -> threading.RLock:
        with self._guard:
            lock = self._locks.get(resource_id)
            if lock is None:
                lock = threading.RLock()
                self._locks[resource_id] = lock
            return lock


class MemoryRuntime:
    """One lease manager's memory. The store keeps rows after the cache is released."""

    def __init__(self, store: MemoryStore | None = None, *, cache_blocks: int = 64) -> None:
        self.store = store or open_store()
        self.cache_blocks = cache_blocks
        self._locks = _ScopeLock()
        self._pages: dict[tuple[str, str], dict[str, list[str]]] = {}
        self._cache: dict[tuple[str, str], MemoryRow] = {}
        self._cache_order: list[tuple[str, str]] = []
        self._access: dict[tuple[str, str, str], int] = {}
        self._clock = 0

    def append(
        self,
        *,
        resource_id: str,
        scope: str,
        holders: list[tuple[str, tuple[str, ...]]],
        writer_pid: str,
        kind: str,
        content: str,
        row_state: str = "",
    ) -> str:
        if row_state and row_state not in STATES:
            raise ValueError(f"Unknown state: {row_state}")
        class_name = class_of(kind)
        with self._locks.get(resource_id):
            row = self.store.append(
                resource_id,
                scope=scope,
                kind=kind,
                content=content,
                row_state=row_state,
                when=_now(),
            )
            self._cache_put(resource_id, row, pinned=False)
            return self._map(resource_id, scope, class_name, row.real, holders, writer_pid)

    def write_system(
        self,
        *,
        resource_id: str,
        scope: str,
        holders: list[tuple[str, tuple[str, ...]]],
        writer_pid: str,
        name: str,
        text: str,
        place: int | None = None,
    ) -> None:
        with self._locks.get(resource_id):
            row = self.store.write_system(
                resource_id,
                scope=scope,
                name=name,
                text=text,
                place=place,
                when=_now(),
            )
            self._cache_put(resource_id, row, pinned=True)
            self._map(resource_id, scope, "system", row.real, holders, writer_pid)

    def system_text(self, resource_id: str) -> str:
        with self._locks.get(resource_id):
            return self.store.system_text(resource_id)

    def latest_seq(self, resource_id: str) -> int:
        with self._locks.get(resource_id):
            return self.store.seq(resource_id)

    def contents(
        self,
        *,
        resource_id: str,
        scope: str,
        pid: str,
        classes: tuple[str, ...],
        selector: list[tuple[str | None, str, int | None, int | None]],
        foreign: dict[str, tuple[str, str]],
    ) -> list[dict[str, Any]]:
        """Rows this process can see. ``foreign`` maps a scope to resource id and scope."""

        with self._locks.get(resource_id):
            found: list[tuple[str, MemoryRow, str]] = []
            for memory_name, class_name, start, end in selector:
                if memory_name is None:
                    mapping = self._page(pid, resource_id)
                    rows = list(mapping.get(class_name) or [])
                    indexes = range(len(rows)) if start is None else range(start, (end if end is not None else start) + 1)
                    for index in indexes:
                        if index >= len(rows):
                            raise PermissionError("This address is outside this process's address space")
                        real = rows[index]
                        row = self._load(resource_id, real, pinned=class_name == "system")
                        if row is None:
                            continue
                        found.append((f"{class_name}/{index}", row, scope))
                    continue
                other = foreign.get(memory_name)
                if other is None:
                    raise PermissionError("This address is outside this process's address space")
                other_id, other_scope = other
                for index, row in self._real_slice(other_id, class_name, start, end):
                    found.append((f"{memory_name}/{class_name}/{index}", row, other_scope))
            found.sort(key=lambda item: (item[1].time, item[1].seq, item[2]))
            return [row.view(address, name) for address, row, name in found]

    def read_budget(
        self,
        rows: list[dict[str, Any]],
        budget: int,
    ) -> tuple[list[dict[str, Any]], str]:
        """Keep only the named rows that fit. The rest stay stored."""

        stored = [
            MemoryRow(
                real=str(item.get("real") or ""),
                class_name="",
                kind=str(item.get("kind") or ""),
                content=str(item.get("content") or ""),
                time=str(item.get("time") or ""),
                seq=int(item.get("seq") or 0),
                state=str(item.get("state") or ""),
                tokens=0,
            )
            for item in rows
        ]
        kept, left = fit_named_read(stored, budget)
        views = []
        for row in kept:
            source = next((item for item in rows if item.get("real") == row.real), None)
            if source is None:
                views.append({"kind": row.kind, "content": row.content, "address": row.real, "real": row.real})
                continue
            copied = dict(source)
            copied["content"] = row.content
            views.append(copied)
        nxt = ""
        if left:
            nxt = " ".join(
                str(item.get("address") or "")
                for item in rows
                if str(item.get("real") or "") in {row.real for row in left}
            )
        return views, nxt.strip()

    def release_resource(self, resource_id: str) -> None:
        """Drop the runtime cache and page tables. Stored rows remain."""

        with self._locks.get(resource_id):
            self.store.drop_pages(resource_id)
            self._pages = {key: value for key, value in self._pages.items() if key[1] != resource_id}
            self._cache_order = [key for key in self._cache_order if key[0] != resource_id]
            self._cache = {key: value for key, value in self._cache.items() if key[0] != resource_id}

    def cache_resident(self, resource_id: str) -> tuple[str, ...]:
        return tuple(real for stored_id, real in self._cache_order if stored_id == resource_id)

    def _map(
        self,
        resource_id: str,
        scope: str,
        class_name: str,
        real: str,
        holders: list[tuple[str, tuple[str, ...]]],
        writer_pid: str,
    ) -> str:
        address = ""
        targets = holders or [(writer_pid, CLASSES)]
        for pid, classes in targets:
            if class_name not in classes:
                continue
            pages = self._page(pid, resource_id)
            rows = pages.setdefault(class_name, [])
            if class_name == "system":
                if real not in rows:
                    rows.append(real)
            else:
                rows.append(real)
            self._touch(pid, resource_id, class_name, len(rows) - 1, real)
            self.store.save_page(pid, resource_id, pages)
            if pid == writer_pid:
                local = f"{class_name}/{len(rows) - 1}"
                address = f"{scope}/{local}" if scope else local
        return address

    def _page(self, pid: str, resource_id: str) -> dict[str, list[str]]:
        key = (pid, resource_id)
        found = self._pages.get(key)
        if found is None:
            found = self.store.load_page(pid, resource_id)
            self._pages[key] = found
        return found

    def _real_slice(
        self,
        resource_id: str,
        class_name: str,
        start: int | None,
        end: int | None,
    ) -> list[tuple[int, MemoryRow]]:
        stored = self.store.rows_of(resource_id, class_name)
        indexes = range(len(stored)) if start is None else range(start, (end if end is not None else start) + 1)
        found: list[tuple[int, MemoryRow]] = []
        for index in indexes:
            if index >= len(stored):
                raise PermissionError("This address is outside this process's address space")
            row = stored[index]
            self._cache_put(resource_id, row, pinned=class_name == "system")
            found.append((index, row))
        return found

    def _load(self, resource_id: str, real: str, *, pinned: bool) -> MemoryRow | None:
        key = (resource_id, real)
        cached = self._cache.get(key)
        if cached is not None:
            self._cache_touch(key)
            return cached
        row = self.store.row(resource_id, real)
        if row is not None:
            self._cache_put(resource_id, row, pinned=pinned)
        return row

    def _cache_put(self, resource_id: str, row: MemoryRow, *, pinned: bool) -> None:
        key = (resource_id, row.real)
        self._cache[key] = row
        self._cache_touch(key)
        if pinned:
            return
        while len(self._cache_order) > self.cache_blocks:
            victim = self._cache_order.pop(0)
            if victim == key:
                self._cache_order.append(victim)
                break
            self._cache.pop(victim, None)

    def _cache_touch(self, key: tuple[str, str]) -> None:
        if key in self._cache_order:
            self._cache_order.remove(key)
        self._cache_order.append(key)

    def _touch(self, pid: str, resource_id: str, class_name: str, position: int, real: str) -> None:
        self._clock += 1
        self._access[(pid, resource_id, f"{class_name}/{position}")] = self._clock
        PageTableEntry(pid, resource_id, class_name, position, real, "resident", self._clock, self._clock)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
