"""The one built-in service shape: an explicit capability member set."""

from __future__ import annotations

from kernel.services.contracts import ServiceBlueprint


def load_blueprint(name: str) -> ServiceBlueprint:
    if name != "capability":
        raise KeyError(f"未知服务种类 {name!r}。已知: capability")
    from kernel.services.kinds.capability import CapabilityBlueprint

    return CapabilityBlueprint()


def service_kinds() -> tuple[str, ...]:
    return ("capability",)
