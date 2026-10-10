"""Register layouts by name. Callers ask for a name and receive the interface."""

from __future__ import annotations

from kernel.process.process_manager.replica_layout.layout import ReplicaLayout

_RESERVED = "off"
_BUILTINS = frozenset({"numbered", "counted", "named"})
_registry: dict[str, ReplicaLayout] = {}


def register_layout(name: str, layout: ReplicaLayout) -> None:
    """Remember one layout under a name. `off` is reserved."""
    if name == _RESERVED:
        raise ValueError("off 是保留名，不能登记成一种布局")
    if not name or name.strip() != name or not name.strip():
        raise ValueError("布局名不能为空")
    _registry[name] = layout


def unregister_layout(name: str) -> None:
    """Drop a custom layout. Built-in names stay registered."""
    if name in _BUILTINS:
        raise ValueError("内置布局不能取消登记")
    _registry.pop(name, None)


def load_layout(name: str) -> ReplicaLayout:
    """Return the layout registered under this name."""
    try:
        layout = _registry[name]
    except KeyError:
        known = ", ".join(sorted(_registry))
        raise KeyError(f"未知布局 {name!r}。已知: {known}") from None
    isolated = getattr(layout, "isolated", None)
    if isolated is None:
        return layout
    return isolated()


def layout_names() -> tuple[str, ...]:
    return tuple(sorted(_registry))


def _register_builtins() -> None:
    if _BUILTINS.issubset(_registry):
        return
    from kernel.process.process_manager.replica_layout.counted.count import CountedLayout
    from kernel.process.process_manager.replica_layout.named.names import NamedLayout
    from kernel.process.process_manager.replica_layout.numbered.expand import (
        NumberedLayout,
    )

    register_layout("numbered", NumberedLayout())
    register_layout("counted", CountedLayout())
    register_layout("named", NamedLayout())


_register_builtins()
