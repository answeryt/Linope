"""Model cards stay on the capability side of the profile function."""

import pytest

from capability.model.model_provider.openai_chat_model.openai_chat_model_plugin import (
    CARD_CONFIG,
    capability_profile,
)
def test_profile_uses_card_defaults() -> None:
    declaration = capability_profile("model.openai_chat_model", ())
    assert declaration.capability == "model.openai_chat_model"
    assert [item.kind for item in declaration.resources] == ["network"]
    assert declaration.settings["provider"] == CARD_CONFIG["provider"]
    assert declaration.settings["id"] == CARD_CONFIG["model"]
    assert "temperature" not in declaration.settings


def test_model_and_temperature_changes_update_the_profile() -> None:
    declaration = capability_profile(
        "model.openai_chat_model",
        (("model", "gpt-4o"), ("temperature", "0.2")),
    )
    assert declaration.settings["id"] == "gpt-4o"
    assert declaration.settings["provider"] == CARD_CONFIG["provider"]
    assert declaration.settings["temperature"] == 0.2


def test_permission_and_capabilities_stay_out_of_model_parameters() -> None:
    declaration = capability_profile(
        "model.openai_chat_model",
        (
            ("permission", "read-only"),
            ("capabilities", "read,glob,grep,read_image"),
            ("temperature", "0.2"),
        ),
    )
    assert declaration.settings["permission"] == "read-only"
    assert declaration.settings["capabilities"] == ["read", "glob", "grep", "read_image"]
    assert declaration.settings["temperature"] == 0.2
    sandbox = next(item for item in declaration.resources if item.kind == "sandbox")
    assert sandbox.call_params == {"mode": "read-only"}
    assert "permission" not in {
        key for item in declaration.resources for key in item.call_params if key != "mode"
    }


def test_unknown_topic_is_rejected_by_the_capability() -> None:
    with pytest.raises(ValueError, match="Unknown topic"):
        capability_profile("model.openai_chat_model", (("trim", "token"),))
