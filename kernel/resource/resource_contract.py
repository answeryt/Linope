"""The only registry of resource kinds.

A new kind is one entry here: its name, the identity it must give, whether it
may be shared, and optional open and close functions. The pool, the lease
table, and the process record do not grow a branch for each kind.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

Open = Callable[[dict[str, Any]], dict[str, Any]]
Close = Callable[[dict[str, Any], dict[str, Any] | None], None]


def kind_name(kind: object) -> str:
    """The registry name of a kind, whether it is an enum or a plain string."""
    return str(getattr(kind, "value", kind))


@dataclass(frozen=True)
class ResourceContract:
    """What one kind must say about itself. Nothing else is stored for it."""

    name: str
    required_identity_keys: tuple[str, ...]
    allow_shared: bool = True
    open: Open | None = None
    close: Close | None = None


_CONTRACTS: dict[str, ResourceContract] = {}


def register(contract: ResourceContract, *, replace: bool = False) -> None:
    """Add one kind. Repeat registration is refused unless it is a replacement."""
    name = kind_name(contract.name)
    if not name or name != contract.name:
        raise ValueError("资源名字不能为空")
    if name in _CONTRACTS and not replace:
        raise ValueError(f"资源已经登记过: {name}")
    _CONTRACTS[name] = contract


def unregister(name: str) -> None:
    """Drop a kind that a test registered. Built-in kinds stay."""
    _CONTRACTS.pop(kind_name(name), None)


def known(name: object) -> bool:
    return kind_name(name) in _CONTRACTS


def require(name: object) -> ResourceContract:
    """Return the registration, or refuse a name that was never registered."""
    try:
        return _CONTRACTS[kind_name(name)]
    except KeyError:
        raise ValueError(f"不认识的资源: {kind_name(name)}") from None


def names() -> tuple[str, ...]:
    return tuple(sorted(_CONTRACTS))


def validate_claim(kind: object, identity: dict[str, Any], *, shared: bool) -> None:
    """Refuse a claim whose identity is incomplete or whose share is not allowed."""
    contract = require(kind)
    missing = [
        key
        for key in contract.required_identity_keys
        if not str((identity or {}).get(key) or "").strip()
    ]
    if missing:
        joined = ", ".join(missing)
        raise ValueError(f"{contract.name} 还缺身份: {joined}")
    if shared and not contract.allow_shared:
        raise ValueError(f"{contract.name} 不能共用")


def open_entity(
    kind: object,
    identity: dict[str, Any],
    loader: Any | None = None,
) -> dict[str, Any]:
    """Prepare one entity. A kind with no open function is only marked loaded."""
    contract = require(kind)
    if contract.open is not None:
        state = contract.open(dict(identity))
        return dict(state)
    if loader is not None:
        loaded = loader.load(kind_name(kind), dict(identity))
        return dict(loaded)
    return {
        "loaded": True,
        "kind": kind_name(kind),
        "identity": dict(identity),
    }


def close_entity(
    kind: object,
    identity: dict[str, Any],
    state: dict[str, Any] | None,
    loader: Any | None = None,
) -> None:
    """Close one entity. A kind with no close function is only unmarked."""
    contract = require(kind)
    if contract.close is not None:
        contract.close(dict(identity), None if state is None else dict(state))
        return
    if loader is not None:
        loader.unload(kind_name(kind), dict(identity), state)


def _open_memory(identity: dict[str, Any]) -> dict[str, Any]:
    """The memory entity is the address range named by its scope."""
    return {"address_space": {"scope": str(identity.get("scope") or "")}}


def _install_builtins() -> None:
    builtins = (
        ResourceContract("memory", ("scope",), open=_open_memory),
        ResourceContract("tool", ("id",)),
        ResourceContract("sandbox", ("root",)),
        ResourceContract("model", ("provider", "id")),
        ResourceContract("network", ("channel",)),
    )
    for contract in builtins:
        register(contract, replace=True)


_install_builtins()
