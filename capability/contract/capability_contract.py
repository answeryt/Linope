"""Generic code-level capability contract declarations."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from kernel.compose.capability.contracts import Requirement
from kernel.compose.capability.contracts import parse_requirements


@dataclass(frozen=True, slots=True)
class CapabilityContract:
    """Describe a capability before implementation code is wired together."""

    name: str
    version: str = "1.0"
    provides: tuple[str, ...] = ()
    requires: tuple[Requirement, ...] = ()
    kind: str = "capability"
    constraints: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        name: str,
        *,
        version: str = "1.0",
        provides: Iterable[str] | None = None,
        requires: Iterable[Any] = (),
        kind: str = "capability",
        constraints: Mapping[str, Any] | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        if not isinstance(name, str) or not name:
            raise ValueError("capability contract name must be a non-empty string")
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "version", version)
        object.__setattr__(self, "provides", tuple(provides or (name,)))
        object.__setattr__(self, "requires", tuple(parse_requirements(requires)))
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "constraints", dict(constraints or {}))
        object.__setattr__(self, "metadata", dict(metadata or {}))

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "CapabilityContract":
        """Validate a literal plugin dict into a contract. Host-only."""
        if not isinstance(value, Mapping):
            raise TypeError("capability contract must be a mapping")
        reserved = {"name", "version", "provides", "requires", "kind", "constraints"}
        metadata = {str(key): item for key, item in value.items() if key not in reserved}
        return cls(
            str(value.get("name", "")),
            version=str(value.get("version", "1.0")),
            provides=value.get("provides"),
            requires=value.get("requires", ()),
            kind=str(value.get("kind", "capability")),
            constraints=value.get("constraints"),
            metadata=metadata,
        )

    def to_mapping(self, **extra: Any) -> dict[str, Any]:
        """Return descriptor-like metadata without importing compose internals."""
        return {
            "name": self.name,
            "version": self.version,
            "provides": list(self.provides),
            "requires": [
                {
                    "capability": requirement.capability,
                    "optional": requirement.optional,
                    "cardinality": requirement.cardinality.value,
                }
                for requirement in self.requires
            ],
            "kind": self.kind,
            "constraints": dict(self.constraints),
            **dict(self.metadata),
            **extra,
        }
