"""Service kind registration."""

from __future__ import annotations

import pytest

from kernel.services.registry import (
    load_blueprint,
    register_service_kind,
    service_kinds,
    unregister_service_kind,
)
from kernel.services.spec import MemberPlan, ServicePlan, ServiceSpec


class _Echo:
    def plan(self, spec: ServiceSpec) -> ServicePlan:
        return ServicePlan(members=(MemberPlan(role="only", capability=spec.members[0]),))


def test_builtins_are_registered() -> None:
    assert service_kinds() == ("capability", "mcp", "model")


def test_unknown_kind_lists_the_known_names() -> None:
    with pytest.raises(KeyError, match="未知服务种类 'missing'"):
        load_blueprint("missing")


def test_a_custom_kind_can_be_added_and_removed() -> None:
    register_service_kind("echo", _Echo())
    try:
        assert "echo" in service_kinds()
        plan = load_blueprint("echo").plan(ServiceSpec("echo", members=("tools.bash",)))
        assert plan.members[0].capability == "tools.bash"
    finally:
        unregister_service_kind("echo")
    assert "echo" not in service_kinds()


def test_a_builtin_kind_cannot_be_removed() -> None:
    with pytest.raises(ValueError, match="内置"):
        unregister_service_kind("model")


def test_a_blank_name_is_refused() -> None:
    with pytest.raises(ValueError):
        register_service_kind("  ", _Echo())


def test_a_blueprint_without_plan_is_refused() -> None:
    with pytest.raises(TypeError):
        register_service_kind("bare", object())  # type: ignore[arg-type]
