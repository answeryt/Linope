"""Model cards stay on the capability side of the profile function."""

import pytest

from capability.model.model_provider.openai_chat_model.openai_chat_model_plugin import (
    CARD_CONFIG,
    capability_profile,
)
def test_profile_uses_card_defaults() -> None:
    declaration = capability_profile("model.openai_chat_model", ())
    assert declaration.capability == "model.openai_chat_model"
    assert declaration.resources[0].kind == "model"
    assert declaration.resources[0].identity["id"] == CARD_CONFIG["model"]
    assert declaration.settings["provider"] == CARD_CONFIG["provider"]
    assert declaration.settings["id"] == CARD_CONFIG["model"]
    assert "temperature" not in declaration.settings


def test_model_and_temperature_changes_update_the_profile() -> None:
    declaration = capability_profile(
        "model.openai_chat_model",
        (("model", "gpt-4o"), ("temperature", "0.2")),
    )
    assert declaration.resources[0].identity["id"] == "gpt-4o"
    assert declaration.settings["id"] == "gpt-4o"
    assert declaration.settings["provider"] == CARD_CONFIG["provider"]
    assert declaration.settings["temperature"] == 0.2


def test_unknown_topic_is_rejected_by_the_capability() -> None:
    with pytest.raises(ValueError, match="不认识的主题"):
        capability_profile("model.openai_chat_model", (("trim", "token"),))
