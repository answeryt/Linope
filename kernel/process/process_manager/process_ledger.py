"""Process rows, layout, and sharing. This is not a resource lease."""

from __future__ import annotations

import threading
from typing import Any


class ProcessSection:
    """Who is running, which layout is selected, and which capabilities share."""

    name = "process"
    flat_keys = ("processes", "layout", "shares", "failures")

    def __init__(self, lock: threading.RLock) -> None:
        self._lock = lock
        self._processes: dict[str, dict[str, Any]] = {}
        self._layout: tuple[str | None, dict[str, Any]] = (None, {})
        self._shares: set[str] = set()
        self.failures: list[str] = []

    def register_process(
        self,
        process_id: str,
        capability_id: str,
        pid: int | None,
        status: str,
    ) -> None:
        with self._lock:
            self._processes[process_id] = {
                "process_id": process_id,
                "capability_id": capability_id,
                "pid": pid,
                "status": status,
                "exit_code": None,
            }

    def update_process(
        self,
        process_id: str,
        *,
        pid: int | None = None,
        status: str,
        exit_code: int | None = None,
        identity: str | None = None,
    ) -> None:
        with self._lock:
            record = self._processes[process_id]
            if pid is not None:
                record["pid"] = pid
            if identity is not None:
                record["identity"] = identity
            record["status"] = status
            record["exit_code"] = exit_code

    def get_process(self, process_id: str) -> dict[str, Any] | None:
        with self._lock:
            record = self._processes.get(process_id)
            return None if record is None else dict(record)

    def rows(self) -> tuple[tuple[str, dict[str, Any]], ...]:
        with self._lock:
            return tuple(
                (process_id, dict(record))
                for process_id, record in self._processes.items()
            )

    def set_activation(self, process_id: str, payload: dict[str, Any]) -> None:
        with self._lock:
            self._processes[process_id]["activation"] = dict(payload)

    def activation_for(self, process_id: str) -> dict[str, Any]:
        with self._lock:
            record = self._processes.get(process_id)
            if record is None or not isinstance(record.get("activation"), dict):
                raise KeyError(process_id)
            return dict(record["activation"])

    def note_spawn_pid(self, process_id: str, pid: int) -> None:
        with self._lock:
            record = self._processes[process_id]
            record["pid"] = pid
            if record.get("status") not in {"running", "failed", "stopped"}:
                record["status"] = "starting"

    def set_desired(self, process_id: str, desired: str) -> None:
        with self._lock:
            self._processes[process_id]["desired"] = desired

    def mark_running(
        self,
        process_id: str,
        pid: int,
        identity: str | None,
        ready: dict[str, Any],
    ) -> None:
        with self._lock:
            record = self._processes[process_id]
            record.update(
                pid=pid,
                identity=identity,
                status="running",
                ready=dict(ready),
            )

    def mark_failed(
        self,
        process_id: str,
        pid: int | None,
        identity: str | None,
        ready: dict[str, Any],
    ) -> None:
        with self._lock:
            record = self._processes[process_id]
            if pid is not None:
                record["pid"] = pid
            if identity is not None:
                record["identity"] = identity
            record.update(status="failed", exit_code=1, ready=dict(ready))

    def record_failure(self, process_id: str, message: str) -> None:
        del process_id
        with self._lock:
            self.failures.append(str(message))

    def selected_layout(self) -> tuple[str | None, dict[str, Any]]:
        with self._lock:
            name, settings = self._layout
            return name, dict(settings)

    def select_layout(
        self,
        name: str | None,
        settings: dict[str, Any] | None = None,
    ) -> None:
        with self._lock:
            self._layout = (
                None if name in (None, "", "off") else str(name),
                dict(settings or {}),
            )

    def set_replica_name(self, process_id: str, replica_name: str) -> None:
        with self._lock:
            self._processes[process_id]["replica_name"] = replica_name

    def running_replicas(self, capability_id: str) -> tuple[dict[str, Any], ...]:
        with self._lock:
            return tuple(
                dict(record)
                for record in self._processes.values()
                if record.get("capability_id") == capability_id
                and record.get("status") in {"starting", "running"}
                and record.get("replica_name")
            )

    def running_processes(self, capability_id: str) -> tuple[dict[str, Any], ...]:
        with self._lock:
            return tuple(
                dict(record)
                for record in self._processes.values()
                if record.get("capability_id") == capability_id
                and record.get("status") in {"starting", "running"}
                and record.get("desired") != "stop"
            )

    def live_processes(self) -> tuple[dict[str, Any], ...]:
        with self._lock:
            return tuple(
                dict(record)
                for record in self._processes.values()
                if record.get("status") in {"starting", "running"}
                and record.get("desired") != "stop"
            )

    def set_worker_ceiling(self, process_id: str, ceiling: int) -> None:
        with self._lock:
            self._processes[process_id]["worker_ceiling"] = int(ceiling)

    def set_inflight_ceiling(self, process_id: str, ceiling: int) -> None:
        with self._lock:
            self._processes[process_id]["inflight_ceiling"] = int(ceiling)

    def shares_capability(self, capability_id: str) -> bool:
        with self._lock:
            return capability_id in self._shares

    def shared_capabilities(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(sorted(self._shares))

    def share_capabilities(self, capability_ids: tuple[str, ...]) -> None:
        with self._lock:
            self._shares = set(capability_ids)

    def clear_share(self) -> None:
        with self._lock:
            self._shares.clear()

    def export_part(self) -> dict[str, Any]:
        return {
            "processes": {
                process_id: dict(record)
                for process_id, record in self._processes.items()
            },
            "layout": [self._layout[0], dict(self._layout[1])],
            "shares": sorted(self._shares),
            "failures": list(self.failures),
        }

    def import_part(self, payload: dict[str, Any]) -> None:
        self._processes.clear()
        self._processes.update(
            {
                str(key): dict(value)
                for key, value in (payload.get("processes") or {}).items()
            }
        )
        raw_layout = payload.get("layout") or [None, {}]
        self._layout = (
            raw_layout[0],
            dict(raw_layout[1] or {}) if len(raw_layout) > 1 else {},
        )
        self._shares = {str(item) for item in payload.get("shares") or ()}
        self.failures = [str(value) for value in payload.get("failures") or ()]
