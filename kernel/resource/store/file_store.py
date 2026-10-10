"""Atomic local-file ledger adapter."""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any

from kernel.resource.store.persistent_store import StateBackedStore


# 只看一眼的操作。它们可以读进内存，但不能把整本账再换一遍。
_LOOKS = frozenset(
    {
        "activation_for",
        "active_for",
        "active_handles",
        "endpoint_for",
        "entity",
        "get_process",
        "link_at",
        "live_processes",
        "lookup_request",
        "mailbox_counts",
        "page_at",
        "resource_seats",
        "running_processes",
        "running_replicas",
        "selected_channel",
        "selected_layout",
        "shared_capabilities",
        "shares_capability",
        "take_request",
    }
)


class FileStore(StateBackedStore):
    """A restartable store backed by one local JSON file."""

    def __init__(self, path: str | Path, *, memory: Any, reap: bool = True) -> None:
        self._file_thread_lock = threading.RLock()
        self.path = Path(path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.locator = f"file:{self.path}"
        memory.locator = self.locator
        super().__init__(memory)
        self._load_disk()
        if reap:
            self._run_operation("reap_dead_processes")

    def peek_process(self, process_id: str) -> dict[str, Any] | None:
        """Read one process row. Looking does not rewrite the ledger."""
        with self._file_lock():
            self._load_disk()
            return self._delegate("get_process", process_id)

    def _run_operation(self, name: str, *args: Any, **kwargs: Any) -> Any:
        with self._file_lock():
            self._load_disk()
            result = self._delegate(name, *args, **kwargs)
            if _changed(name, result):
                self._save_disk()
            return result

    def _load_disk(self) -> None:
        if not self.path.exists():
            return
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"无法读取本地存储 {self.path}: {exc}") from exc
        if not isinstance(payload, dict):
            raise RuntimeError(f"本地存储不是有效账本: {self.path}")
        self.import_state(payload)

    def _save_disk(self) -> None:
        payload = json.dumps(
            self.export_state(),
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        temporary = self.path.with_name(f".{self.path.name}.tmp-{os.getpid()}")
        temporary.write_text(payload + "\n", encoding="utf-8")
        os.replace(temporary, self.path)

    def _file_lock(self):
        return _InterProcessFileLock(
            self._file_thread_lock,
            self.path.with_suffix(self.path.suffix + ".lock"),
        )

    def check(self) -> dict[str, Any]:
        return {
            "locator": self.locator,
            "backend": "file",
            "ready": True,
            "persistent": True,
            "path": str(self.path),
        }

    def close(self) -> None:
        return None


def _changed(name: str, result: Any) -> bool:
    """A look, or a claim that found nothing, leaves the file alone."""
    if name in _LOOKS:
        return False
    if name == "claim_request":
        return result is not None
    if name == "release_request":
        return result is True
    return True


class _InterProcessFileLock:
    """Small stdlib-only lock that works on Windows and POSIX."""

    def __init__(self, thread_lock: threading.RLock, path: Path) -> None:
        self._thread_lock = thread_lock
        self._path = path
        self._stream = None

    def __enter__(self):
        self._thread_lock.acquire()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._stream = self._path.open("a+b")
        self._stream.seek(0)
        self._stream.write(b"0")
        self._stream.flush()
        if os.name == "nt":
            import msvcrt

            self._stream.seek(0)
            msvcrt.locking(self._stream.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl

            fcntl.flock(self._stream.fileno(), fcntl.LOCK_EX)
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        if self._stream is not None:
            if os.name == "nt":
                import msvcrt

                self._stream.seek(0)
                msvcrt.locking(self._stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(self._stream.fileno(), fcntl.LOCK_UN)
            self._stream.close()
            self._stream = None
        self._thread_lock.release()
