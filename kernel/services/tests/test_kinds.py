"""What each built-in blueprint declares, without launching anything."""

from __future__ import annotations

import pytest

from kernel.services.registry import load_blueprint
from kernel.services.spec import ServiceSpec


def test_capability_is_one_member_with_no_route() -> None:
    plan = load_blueprint("capability").plan(
        ServiceSpec("capability", members=("tools.bash",), changes=(("timeout", "1"),), replica_count=2)
    )
    assert plan.roles() == ("capability",)
    assert plan.route == {}
    assert plan.members[0].capability == "tools.bash"
    assert plan.members[0].changes == (("timeout", "1"),)
    assert plan.members[0].replica_count == 2


def test_capability_refuses_zero_or_two_names() -> None:
    with pytest.raises(ValueError):
        load_blueprint("capability").plan(ServiceSpec("capability"))
    with pytest.raises(ValueError):
        load_blueprint("capability").plan(
            ServiceSpec("capability", members=("tools.bash", "tools.read"))
        )


def test_model_routes_prompt_and_context_and_checks_the_prefix() -> None:
    plan = load_blueprint("model").plan(
        ServiceSpec("model", members=("model.openai_chat_model",), changes=(("model", "gpt-4o"),))
    )
    assert plan.roles() == ("model",)
    assert plan.route == {"prompt": "model", "context": "model"}
    assert plan.members[0].changes == (("model", "gpt-4o"),)
    with pytest.raises(ValueError, match="model"):
        load_blueprint("model").plan(ServiceSpec("model", members=("tools.bash",)))


def test_agent_splits_roles_by_prefix() -> None:
    plan = load_blueprint("agent").plan(
        ServiceSpec(
            "agent",
            members=("model.openai_chat_model", "tools.bash", "context.sliding_window"),
            changes=(("temperature", "0.2"),),
            replica_count=3,
            options={"share": True},
        )
    )
    assert plan.roles() == ("model", "tool:bash", "context")
    assert plan.route == {"prompt": "model", "context": "context"}
    model = plan.members[0]
    assert model.changes == (("temperature", "0.2"),)
    assert model.replica_count == 3
    assert plan.members[1].changes == ()
    assert plan.shared == (
        "model.openai_chat_model",
        "tools.bash",
        "context.sliding_window",
    )


def test_agent_requires_exactly_one_model() -> None:
    with pytest.raises(ValueError, match="model"):
        load_blueprint("agent").plan(ServiceSpec("agent", members=("tools.bash",)))
    with pytest.raises(ValueError, match="一个 model"):
        load_blueprint("agent").plan(
            ServiceSpec("agent", members=("model.a", "model.b"))
        )


def test_agent_refuses_an_unknown_prefix() -> None:
    with pytest.raises(ValueError, match="prompt"):
        load_blueprint("agent").plan(
            ServiceSpec("agent", members=("model.a", "prompt.system"))
        )


def test_mcp_defaults_to_the_tool_manager() -> None:
    plan = load_blueprint("mcp").plan(ServiceSpec("mcp"))
    assert plan.roles() == ("mcp",)
    assert plan.members[0].capability == "tools.mcp_tool_manager"
    assert plan.route == {"tool": "mcp"}


def test_mcp_names_extra_members_and_refuses_other_tools() -> None:
    plan = load_blueprint("mcp").plan(
        ServiceSpec("mcp", members=("tools.mcp_tool_manager", "tools.mcp_config"))
    )
    assert plan.roles() == ("mcp", "mcp:mcp_config")
    with pytest.raises(ValueError, match="tools.mcp"):
        load_blueprint("mcp").plan(ServiceSpec("mcp", members=("tools.bash",)))
