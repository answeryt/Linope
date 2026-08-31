"""Stable metadata shared by plugin discovery, loading, and composition."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Mapping, Protocol, runtime_checkable


class PluginState(str, Enum):
    """Lifecycle state of one mounted plugin."""

    PENDING = "pending"
    LOADING = "loading"
    ACTIVE = "active"
    FAILED = "failed"
    UNLOADING = "unloading"
    DISPOSED = "disposed"


class Cardinality(str, Enum):
    """Number of providers accepted by a requirement."""

    ONE = "one"
    MANY = "many"


@dataclass(frozen=True, slots=True)
class Artifact:
    """Loadable plugin code without assumptions about its business API."""

    name: str
    version: str = "1"
    source: str = ""
    entry: str | None = None
    kind: str = "recipe"

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("artifact name must not be empty")
        if not self.version:
            raise ValueError("artifact version must not be empty")


@dataclass(frozen=True, slots=True)
class Capability:
    """One named value supplied by a mounted artifact."""

    key: str
    value: Any
    provider: str
    contract: str | None = None
    scope: str = "service"

    def __post_init__(self) -> None:
        if not self.key:
            raise ValueError("capability key must not be empty")
        if not self.provider:
            raise ValueError("capability provider must not be empty")


@dataclass(frozen=True, slots=True)
class Requirement:
    """A capability dependency controlling plugin activation."""

    capability: str
    optional: bool = False
    cardinality: Cardinality = Cardinality.ONE

    def __post_init__(self) -> None:
        if not self.capability:
            raise ValueError("requirement capability must not be empty")


@dataclass(frozen=True, slots=True)
class PluginDescriptor:
    """Serializable description emitted by any discovery source."""

    artifact: Artifact
    requirements: tuple[Requirement, ...] = ()
    config: Any = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(
        cls,
        value: Mapping[str, Any],
        *,
        base: str | Path | None = None,
    ) -> "PluginDescriptor":
        name = _non_empty(value.get("name"), "plugin name")
        version = str(value.get("version", "1"))
        source = str(value.get("source", value.get("path", "")))
        if base is not None and source:
            source = str((Path(base) / source).resolve())
        artifact = Artifact(
            name=name,
            version=version,
            source=source,
            entry=_optional_text(value.get("entry")),
            kind=str(value.get("kind", "recipe")),
        )
        raw_requirements = value.get("requires", value.get("inject", ()))
        requirements = tuple(parse_requirements(raw_requirements))
        reserved = {
            "name",
            "version",
            "source",
            "path",
            "entry",
            "kind",
            "requires",
            "inject",
            "config",
        }
        metadata = {
            str(key): item for key, item in value.items() if key not in reserved
        }
        return cls(
            artifact=artifact,
            requirements=requirements,
            config=value.get("config"),
            metadata=metadata,
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "name": self.artifact.name,
            "version": self.artifact.version,
            "source": self.artifact.source,
            "entry": self.artifact.entry,
            "kind": self.artifact.kind,
            "requires": [
                {
                    "capability": requirement.capability,
                    "optional": requirement.optional,
                    "cardinality": requirement.cardinality.value,
                }
                for requirement in self.requirements
            ],
            "config": self.config,
            **dict(self.metadata),
        }


@runtime_checkable
class ArtifactSource(Protocol):
    """Discovery boundary implemented outside the composition kernel."""

    def discover(self) -> Iterable[PluginDescriptor]:
        """Return descriptors without importing their plugin code."""


def parse_requirements(value: Any) -> list[Requirement]:
    """Normalize concise strings and explicit requirement mappings."""

    if value is None:
        return []
    if isinstance(value, str):
        value = [value]
    if isinstance(value, Mapping):
        value = [
            {"capability": name, **(settings if isinstance(settings, Mapping) else {})}
            for name, settings in value.items()
        ]
    if not isinstance(value, Iterable):
        raise TypeError("plugin requirements must be iterable")
    result: list[Requirement] = []
    for item in value:
        if isinstance(item, Requirement):
            result.append(item)
        elif isinstance(item, str):
            result.append(Requirement(item))
        elif isinstance(item, Mapping):
            cardinality = Cardinality(str(item.get("cardinality", "one")))
            result.append(
                Requirement(
                    _non_empty(
                        item.get("capability", item.get("name")),
                        "requirement capability",
                    ),
                    optional=bool(item.get("optional", False)),
                    cardinality=cardinality,
                )
            )
        else:
            raise TypeError("requirements must contain strings or mappings")
    return result


def _non_empty(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    return _non_empty(value, "entry")
