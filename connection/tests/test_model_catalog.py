"""Tests for dynamic model provider discovery."""

from __future__ import annotations

from pathlib import Path

from connection.semantic.model_catalog import discover_model_cards


def test_catalog_discovers_provider_cards_without_programs_table() -> None:
    root = Path(__file__).resolve().parents[2]
    cards = discover_model_cards(root)

    capabilities = {card["capability"] for card in cards}
    assert {
        "model.openai_chat_model",
        "model.openai_response_model",
        "model.anthropic_model",
        "model.gemini_model",
    } <= capabilities
    assert all(card["card_json_exists"] for card in cards)
    assert all(card["interface_exists"] for card in cards)
    assert all(card["ready"] for card in cards)
    assert all("stream" in card["changes"] for card in cards)
