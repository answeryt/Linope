"""Register service kinds by name. The core never imports a blueprint."""

from __future__ import annotations

from kernel.services.contracts import ServiceBlueprint

_BUILTINS = frozenset({"capability", "model", "agent", "mcp"})
_registry: dict[str, ServiceBlueprint] = {}


def register_service_kind(name: str, blueprint: ServiceBlueprint) -> None:
    """Remember one blueprint under a name."""
    if not name or name.strip() != name:
        raise ValueError("服务种类名不能为空")
    if not callable(getattr(blueprint, "plan", None)):
        raise TypeError("蓝图必须提供 plan(spec)")
    _registry[name] = blueprint


def unregister_service_kind(name: str) -> None:
    """Drop a custom kind. Built-in names stay registered."""
    if name in _BUILTINS:
        raise ValueError("内置服务种类不能取消登记")
    _registry.pop(name, None)


def load_blueprint(name: str) -> ServiceBlueprint:
    """Return the blueprint registered under this name."""
    _register_builtins()
    try:
        return _registry[name]
    except KeyError:
        known = ", ".join(service_kinds())
        raise KeyError(f"未知服务种类 {name!r}。已知: {known}") from None


def service_kinds() -> tuple[str, ...]:
    _register_builtins()
    return tuple(sorted(_registry))


def _register_builtins() -> None:
    if _BUILTINS.issubset(_registry):
        return
    import kernel.services.kinds  # noqa: F401  registers on import
