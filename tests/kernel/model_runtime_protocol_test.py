from __future__ import annotations

import unittest
from pathlib import Path

from capability.model.runtime.assemble import model_catalog
from capability.model.runtime.assemble import model_composition_spec
from kernel.compose.capability import CapabilityGraphResolver
from kernel.compose.capability import inject_capabilities


ROOT = Path(__file__).resolve().parents[2]


class ModelRuntimeProtocolTest(unittest.TestCase):
    def test_model_interfaces_do_not_pull_one_parameter_plugin(self) -> None:
        catalog = model_catalog(ROOT)
        interface = catalog.find("model.interface.openai_chat")[0]

        self.assertEqual(interface.requires, ())

    def test_model_cards_are_available_as_runtime_capabilities(self) -> None:
        catalog = model_catalog(ROOT)
        lip = inject_capabilities(repo=ROOT)
        try:
            composition = CapabilityGraphResolver(catalog).plan(model_composition_spec()).execute(lip)

            cards = lip.get_all("model.card")
            card_ids = {card.get("card_id") for card in cards if isinstance(card, dict)}

            self.assertIn("openai_chat_model", card_ids)
            self.assertIn("openai_response_model", card_ids)
            self.assertEqual(lip.get("model.card.openai_chat_model")["interface"], "openai_chat")
            self.assertIn("openai", composition.target.providers())
        finally:
            lip.unload()


if __name__ == "__main__":
    unittest.main()
