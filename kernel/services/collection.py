"""A service is a saved list of process ids. It is not a process."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ServiceGroup:
    """One service: a number and the process ids in it."""

    service_id: int
    pids: tuple[int, ...]


class ServiceBook:
    """The file copy of service lists."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def groups(self) -> tuple[ServiceGroup, ...]:
        if not self.path.is_file():
            return ()
        body = json.loads(self.path.read_text(encoding="utf-8"))
        found = []
        for item in body.get("services") or ():
            if not isinstance(item, dict):
                raise ValueError("The service list has a record that cannot be read")
            extra = set(item) - {"id", "pids"}
            if extra:
                raise ValueError(
                    f"The service list has fields that must not be saved: {', '.join(sorted(extra))}"
                )
            if "id" not in item or "pids" not in item:
                raise ValueError("The service list is missing fields")
            service_id = int(item["id"])
            pids = tuple(int(pid) for pid in item["pids"])
            if service_id <= 0 or not pids or any(pid <= 0 for pid in pids):
                raise ValueError("A pid in the service list is invalid")
            if len(pids) != len(set(pids)):
                raise ValueError("The same pid was given twice")
            found.append(ServiceGroup(service_id=service_id, pids=pids))
        return tuple(found)

    def get(self, service_id: int) -> ServiceGroup | None:
        for group in self.groups():
            if group.service_id == int(service_id):
                return group
        return None

    def add(self, pids: tuple[int, ...]) -> ServiceGroup:
        chosen = tuple(int(pid) for pid in pids)
        if not chosen or any(pid <= 0 for pid in chosen):
            raise ValueError("A service must have at least one process")
        if len(chosen) != len(set(chosen)):
            raise ValueError("The same pid was given twice")
        current = self.groups()
        service_id = 1 + max((item.service_id for item in current), default=0)
        created = ServiceGroup(service_id=service_id, pids=chosen)
        self._write((*current, created))
        return created

    def _write(self, groups: tuple[ServiceGroup, ...]) -> None:
        body = {
            "services": [
                {"id": item.service_id, "pids": list(item.pids)} for item in groups
            ]
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(body, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )
        os.replace(temporary, self.path)
