"""Model cards stay on the capability side of the profile function."""

import pytest

from capability.model.model_provider.openai_chat_model.openai_chat_model_plugin import (
    CARD_CONFIG,
    capability_profile,
)
from kernel.resource.definition import ResourceKind


def test_profile_uses_card_defaults() -> None:
    declaration = capability_profile("model.openai_chat_model", ())
    claim = declaration.resources[0]
    assert declaration.capability == "model.openai_chat_model"
    assert claim.kind == ResourceKind.MODEL
    assert claim.identity == {"provider": CARD_CONFIG["provider"], "id": CARD_CONFIG["model"]}
    assert claim.call_params == {}
    assert claim.share_requested is False


def test_model_and_temperature_changes_update_the_profile() -> None:
    declaration = capability_profile(
        "model.openai_chat_model",
        (("model", "gpt-4o"), ("temperature", "0.2")),
    )
    claim = declaration.resources[0]
    assert claim.identity["id"] == "gpt-4o"
    assert claim.identity["provider"] == CARD_CONFIG["provider"]
    assert claim.call_params["temperature"] == 0.2


def test_unknown_topic_is_rejected_by_the_capability() -> None:
    with pytest.raises(ValueError, match="不认识的主题"):
        capability_profile("model.openai_chat_model", (("trim", "token"),))
