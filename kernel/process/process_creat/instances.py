"""Resolve one capability name to the command that starts it.

The capability tree writes the table. This module only reads that file.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kernel.resource.definition import ResourceDefinition


TABLE_NAME = "programs.json"


@dataclass(frozen=True)
class CapabilityDefinition:
    instance_id: str
    module_paths: tuple[str, ...] = ()
    entrypoint: str | None = "load"
    resource_requirements: tuple[ResourceDefinition, ...] = ()
    argv: tuple[str, ...] = ()
    secret_names: tuple[str, ...] = ()

    def activation(self) -> dict[str, Any]:
        return {
            "instance_id": self.instance_id,
            "module_paths": self.module_paths,
            "entrypoint": self.entrypoint,
            "argv": list(self.argv),
            "resource_requirements": [
                {
                    "kind": str(getattr(item.kind, "value", item.kind)),
                    "required": item.required,
                    "share_mode": item.share_mode.value,
                }
                for item in self.resource_requirements
            ],
        }

    def command(self) -> tuple[str, ...]:
        if not self.argv:
            raise RuntimeError(f"This capability has no command: {self.instance_id}")
        return self.argv


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def capability_root() -> Path:
    return repo_root() / "capability"


def discover_instances(root: Path | None = None) -> dict[str, list[Path]]:
    """Return one program path per capability id."""
    table = load_table(root)
    return {
        key: [Path(item) for item in row.get("module_paths") or ()]
        for key, row in table.items()
        if isinstance(row, dict)
    }


def describe_instance(
    instance_id: str,
    catalog: dict[str, Any] | None = None,
) -> CapabilityDefinition:
    table = load_table() if catalog is None else catalog
    return _definition(instance_id, _row(table, instance_id))


def resolve_instance_id(
    instance_id: str,
    catalog: dict[str, list[Path]] | None = None,
) -> str:
    catalog = discover_instances() if catalog is None else catalog
    if instance_id not in catalog:
        known = ", ".join(sorted(catalog))
        raise KeyError(f"Unknown capability instance {instance_id!r}. Known: {known}")
    return instance_id


def described(instance_id: str, changes: Any = ()) -> tuple[Any, CapabilityDefinition]:
    """The declaration and the command for one capability, including startup changes."""
    from kernel.process.declaration import ProcessDeclaration

    table = load_table()
    row = _row(table, instance_id)
    definition = _definition(instance_id, row)
    payload = _declaration_payload(instance_id, row, changes)
    return ProcessDeclaration.from_payload(payload), definition


def load_capability(instance_id: str) -> tuple[list[Any], CapabilityDefinition]:
    """The program loads its own modules. The kernel only keeps the command."""
    definition = describe_instance(instance_id)
    return [], definition


def load_instance(instance_id: str) -> list[Any]:
    modules, _definition = load_capability(instance_id)
    return modules


def load_table(root: Path | None = None) -> dict[str, Any]:
    """Read the table the capability tree already wrote."""
    path = (capability_root() if root is None else Path(root)) / TABLE_NAME
    if not path.is_file():
        raise RuntimeError(f"The capability table is missing: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"The capability table is unreadable: {path}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"The capability table is unreadable: {path}")
    return payload


def _row(table: dict[str, Any], instance_id: str) -> dict[str, Any]:
    row = table.get(instance_id)
    if not isinstance(row, dict):
        known = ", ".join(sorted(key for key, value in table.items() if isinstance(value, dict)))
        raise KeyError(f"Unknown capability instance {instance_id!r}. Known: {known}")
    return row


def _definition(instance_id: str, row: dict[str, Any]) -> CapabilityDefinition:
    repo = capability_root().parent
    paths = tuple(_resolve(repo, item) for item in row.get("module_paths") or ())
    argv = tuple(str(item) for item in row.get("argv") or ())
    return CapabilityDefinition(
        instance_id=instance_id,
        module_paths=paths,
        entrypoint=str(row.get("entrypoint") or "load"),
        argv=argv,
        secret_names=tuple(str(item) for item in row.get("secret_names") or ()),
    )


def _declaration_payload(instance_id: str, row: dict[str, Any], changes: Any) -> dict[str, Any]:
    settings = dict(row.get("settings") or {})
    allowed = {str(item) for item in row.get("changes") or ()}
    for topic, raw in changes or ():
        name = str(topic)
        if name not in allowed:
            raise ValueError(f"Unknown topic: {name}")
        settings[name] = _parse_value(str(raw))
    return {
        "capability": instance_id,
        "resources": list(row.get("resources") or ()),
        "settings": settings,
    }


def _resolve(repo: Path, value: str) -> str:
    path = Path(value)
    if path.is_absolute():
        return str(path)
    return str((repo / value).resolve())


def _parse_value(raw: str) -> Any:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw
