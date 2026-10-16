"""Process rows, layout, and sharing. This is not a resource lease."""

from __future__ import annotations

import threading
from typing import Any


class ProcessSection:
    """Who is running, which layout is selected, and which capabilities share."""

    name = "process"
    flat_keys = (
        "processes",
        "layout",
        "shares",
        "failures",
        "names",
        "specs",
        "services",
        "bindings",
    )

    def __init__(self, lock: threading.RLock) -> None:
        self._lock = lock
        self._processes: dict[str, dict[str, Any]] = {}
        self._layout: tuple[str | None, dict[str, Any]] = (None, {})
        self._shares: set[str] = set()
        self._services: dict[str, dict[str, Any]] = {}
        self._bindings: dict[str, dict[str, str]] = {}
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
    ) -> bool:
        with self._lock:
            record = self._processes[process_id]
            if record.get("desired") == "stop" or record.get("status") == "failed":
                return False
            record.update(
                pid=pid,
                identity=identity,
                status="running",
                ready=dict(ready),
            )
            return True

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

    def create_service(self, name: str) -> None:
        """Create an empty service. This does not start a process."""
        if not name or name.strip() != name:
            raise ValueError("服务名字不能为空")
        with self._lock:
            if name in self._services:
                raise ValueError(f"已经有这个服务: {name}")
            self._services[name] = {"name": name}
            self._bindings[name] = {}

    def service_record(self, name: str) -> dict[str, Any] | None:
        """One service, or none when create has not been run."""
        with self._lock:
            record = self._services.get(name)
            return None if record is None else dict(record)

    def service_names(self) -> tuple[str, ...]:
        """Service names in alphabetical order."""
        with self._lock:
            return tuple(sorted(self._services))

    def bind_service(self, name: str, process_id: str, role: str) -> dict[str, Any]:
        """Attach one existing process. The same pair is not stored twice."""
        if not role or role.strip() != role:
            raise ValueError("关系不能为空")
        with self._lock:
            if name not in self._services:
                raise KeyError(name)
            if process_id not in self._processes:
                raise KeyError(process_id)
            current = self._bindings.setdefault(name, {})
            if current.get(process_id) == role:
                return {"changed": False}
            current[process_id] = role
            return {"changed": True}

    def unbind_service(self, name: str, process_id: str) -> None:
        """Drop one membership. The process keeps running."""
        with self._lock:
            if name not in self._services:
                raise KeyError(name)
            current = self._bindings.get(name) or {}
            if process_id not in current:
                raise KeyError(process_id)
            del current[process_id]

    def delete_service(self, name: str) -> None:
        """Drop the service and its memberships. Processes keep running."""
        with self._lock:
            if name not in self._services:
                raise KeyError(name)
            self._services.pop(name, None)
            self._bindings.pop(name, None)

    def service_members(self, name: str) -> tuple[dict[str, Any], ...]:
        """Memberships of one service. Missing services have none."""
        with self._lock:
            if name not in self._services:
                return ()
            found = []
            for process_id, role in sorted(self._bindings.get(name, {}).items()):
                row = dict(self._processes.get(process_id) or {})
                found.append(
                    {
                        "process_id": process_id,
                        "role": role,
                        "capability_id": str(row.get("capability_id") or ""),
                        "status": str(row.get("status") or ""),
                        "pid": row.get("pid"),
                    }
                )
            return tuple(found)

    def service_member_ids(self, name: str) -> tuple[str, ...] | None:
        """Process ids of one service, or none when that service does not exist."""
        with self._lock:
            if name not in self._services:
                return None
            return tuple(sorted(self._bindings.get(name, {})))

    def services_for_process(self, process_id: str) -> tuple[str, ...]:
        """Every service this process currently belongs to."""
        with self._lock:
            return tuple(
                sorted(
                    name
                    for name, bindings in self._bindings.items()
                    if process_id in bindings
                )
            )

    def export_part(self) -> dict[str, Any]:
        return {
            "processes": {
                process_id: dict(record)
                for process_id, record in self._processes.items()
            },
            "layout": [self._layout[0], dict(self._layout[1])],
            "shares": sorted(self._shares),
            "failures": list(self.failures),
            "services": {name: dict(record) for name, record in self._services.items()},
            "bindings": {
                name: dict(bindings) for name, bindings in self._bindings.items()
            },
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
        if payload.get("names") or payload.get("specs"):
            raise ValueError("旧的服务配方不能再读入，请重新创建服务并绑定进程")
        self._services = {}
        raw_services = payload.get("services") or {}
        if isinstance(raw_services, dict):
            for name, record in raw_services.items():
                if isinstance(record, dict):
                    self._services[str(name)] = {"name": str(name)}
        self._bindings = {}
        raw_bindings = payload.get("bindings") or {}
        if isinstance(raw_bindings, dict):
            for name, bindings in raw_bindings.items():
                if not isinstance(bindings, dict):
                    continue
                cleaned = {
                    str(process_id): str(role)
                    for process_id, role in bindings.items()
                    if process_id and role
                }
                if str(name) in self._services:
                    self._bindings[str(name)] = cleaned
