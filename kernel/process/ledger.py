"""One file copy of the process resource accounts.

The file holds the same fields as the in-memory records. It does not hold the
contract, call results, or file bodies.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


_RECORD_KEYS = {
    "process_id",
    "capability_id",
    "status",
    "claims",
    "leases",
    "room",
    "pid",
    "started",
}
_LEASE_KEYS = {
    "lease_id",
    "kind",
    "resource_id",
    "share_mode",
    "fencing_token",
    "handle",
    "identity",
}


class ProcessLedger:
    """Write every process account into one JSON file."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def write(self, records: list[dict[str, Any]]) -> None:
        body = {"records": [_check_record(item) for item in records]}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(body, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )
        os.replace(temporary, self.path)

    def read(self) -> list[dict[str, Any]]:
        if not self.path.is_file():
            return []
        body = json.loads(self.path.read_text(encoding="utf-8"))
        return [_check_record(item) for item in body.get("records") or ()]


def _check_record(item: dict[str, Any]) -> dict[str, Any]:
    extra = set(item) - _RECORD_KEYS
    if extra:
        raise ValueError(f"记录里有不该保存的字段: {', '.join(sorted(extra))}")
    missing = _RECORD_KEYS - set(item)
    if missing:
        raise ValueError(f"记录还缺字段: {', '.join(sorted(missing))}")
    leases = []
    for lease in item["leases"]:
        lease_extra = set(lease) - _LEASE_KEYS
        if lease_extra:
            raise ValueError(
                f"记录里有不该保存的字段: {', '.join(sorted(lease_extra))}"
            )
        leases.append(dict(lease))
    return {
        "process_id": item["process_id"],
        "capability_id": item["capability_id"],
        "status": item["status"],
        "claims": [dict(claim) for claim in item["claims"]],
        "leases": leases,
        "room": dict(item["room"]),
        "pid": int(item["pid"]),
        "started": str(item["started"]),
    }
