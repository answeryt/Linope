# -*- coding: utf-8 -*-
"""Thread-safe in-memory journal for deterministic Process replay."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Mapping


PLUGIN_NAME = "kernel_process_journal"
PLUGIN_VERSION = "1.0"


class _NoopLock:
    """Run-level serialization is supplied by the Host queue claim."""

    def __enter__(self) -> None:
        return None

    def __exit__(self, *_args: Any) -> None:
        return None


class NonDeterminismError(RuntimeError):
    """Raised when replay emits a different command at the same index."""


class ReplayedCommandError(RuntimeError):
    """Portable failure reconstructed from a previously failed command."""

    def __init__(self, error: Mapping[str, Any] | str) -> None:
        details = dict(error) if isinstance(error, Mapping) else {"message": str(error)}
        self.error = deepcopy(details)
        self.original_type = str(details.get("type") or "Exception")
        super().__init__(str(details.get("message") or self.original_type))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _error_record(error: BaseException | Mapping[str, Any] | str) -> dict[str, Any]:
    if isinstance(error, Mapping):
        return deepcopy(dict(error))
    if isinstance(error, BaseException):
        return {
            "type": type(error).__name__,
            "module": type(error).__module__,
            "message": str(error),
            "args": deepcopy(list(error.args)),
        }
    return {"type": "Exception", "message": str(error)}


class InMemoryJournal:
    """Command and event journal keyed by process, run, and command index."""

    def __init__(self) -> None:
        self._commands: dict[tuple[str, str, int], dict[str, Any]] = {}
        self._events: dict[tuple[str, str], list[dict[str, Any]]] = {}
        self._lock = _NoopLock()

    @staticmethod
    def _key(process_id: str, run_id: str, command_index: int) -> tuple[str, str, int]:
        index = int(command_index)
        if index < 0:
            raise ValueError("command_index must be non-negative")
        return str(process_id), str(run_id), index

    def append_command(
        self,
        process_id: str,
        run_id: str,
        command_index: int,
        command_type: str,
        command_name: str,
        definition_version: str,
        input: Any = None,
        **fields: Any,
    ) -> dict[str, Any]:
        key = self._key(process_id, run_id, command_index)
        semantics = {
            "command_type": str(command_type),
            "command_name": str(command_name),
            "definition_version": str(definition_version),
            "input": deepcopy(input),
        }
        with self._lock:
            existing = self._commands.get(key)
            if existing is not None:
                if any(existing.get(name) != value for name, value in semantics.items()):
                    raise NonDeterminismError(
                        f"command {key!r} changed during replay"
                    )
                return deepcopy(existing)
            timestamp = _now()
            record = {
                "process_id": key[0],
                "run_id": key[1],
                "command_index": key[2],
                **semantics,
                "status": "pending",
                "result": None,
                "error": None,
                "created_at": timestamp,
                "updated_at": timestamp,
            }
            record.update(deepcopy(fields))
            self._commands[key] = record
            return deepcopy(record)

    def get_command(
        self, process_id: str, run_id: str, command_index: int
    ) -> dict[str, Any] | None:
        key = self._key(process_id, run_id, command_index)
        with self._lock:
            item = self._commands.get(key)
            return None if item is None else deepcopy(item)

    def complete_command(
        self,
        process_id: str,
        run_id: str,
        command_index: int,
        result: Any = None,
    ) -> dict[str, Any]:
        key = self._key(process_id, run_id, command_index)
        with self._lock:
            record = self._require(key)
            record["status"] = "completed"
            record["result"] = deepcopy(result)
            record["error"] = None
            record["updated_at"] = _now()
            return deepcopy(record)

    def fail_command(
        self,
        process_id: str,
        run_id: str,
        command_index: int,
        error: BaseException | Mapping[str, Any] | str,
    ) -> dict[str, Any]:
        key = self._key(process_id, run_id, command_index)
        with self._lock:
            record = self._require(key)
            record["status"] = "failed"
            record["error"] = _error_record(error)
            record["result"] = None
            record["updated_at"] = _now()
            return deepcopy(record)

    def list_commands(
        self, process_id: str, run_id: str
    ) -> list[dict[str, Any]]:
        prefix = (str(process_id), str(run_id))
        with self._lock:
            items = [
                deepcopy(record)
                for key, record in self._commands.items()
                if key[:2] == prefix
            ]
        return sorted(items, key=lambda item: int(item["command_index"]))

    def append_event(
        self,
        process_id: str,
        run_id: str,
        event: Mapping[str, Any] | str,
        **fields: Any,
    ) -> dict[str, Any]:
        key = (str(process_id), str(run_id))
        record = (
            deepcopy(dict(event))
            if isinstance(event, Mapping)
            else {"event_type": str(event)}
        )
        record.update(deepcopy(fields))
        with self._lock:
            events = self._events.setdefault(key, [])
            record.setdefault("event_index", len(events))
            record.setdefault("created_at", _now())
            events.append(record)
            return deepcopy(record)

    def list_events(self, process_id: str, run_id: str) -> list[dict[str, Any]]:
        with self._lock:
            return deepcopy(self._events.get((str(process_id), str(run_id)), []))

    @staticmethod
    def replayed_error(error: Mapping[str, Any] | str) -> ReplayedCommandError:
        return ReplayedCommandError(error)

    def _require(self, key: tuple[str, str, int]) -> dict[str, Any]:
        record = self._commands.get(key)
        if record is None:
            raise KeyError(key)
        return record
