"""Extra resources are chosen at start and do not replace the profile."""

from pathlib import Path

import pytest

from capability.model.model_provider.card_profile import declaration_from_card
from capability.model.model_provider.openai_chat_model.openai_chat_model_plugin import (
    CARD_CONFIG,
)
from kernel.command.process.start import _parse_start_options, launch_options
from kernel.process.declaration import ProcessDeclaration, ResourceClaim, append_chosen
from kernel.process.ledger import ProcessLedger
from kernel.process.process_creat.instances import CapabilityDefinition
from kernel.process.reconcile import ProcessReconciler
from kernel.process.resource_record import ProcessResourceBook
from kernel.resource.lease import ResourceLeaseManager
from kernel.resource.pool import ResourcePool
from kernel.resource.resource_contract import kind_name


def _model_declaration() -> ProcessDeclaration:
    return declaration_from_card("model.openai_chat_model", CARD_CONFIG, ())


def test_with_is_parsed_as_extra_resources() -> None:
    options = launch_options(
        _parse_start_options(
            ["model.openai_chat_model", "--with", "memory=chat", "--with", "tool=files"]
        )
    )
    assert options.chosen == ("memory=chat", "tool=files")


def test_with_adds_memory_beside_the_model_defaults(tmp_path: Path) -> None:
    declaration = append_chosen(_model_declaration(), ("memory=chat",))
    book = ProcessResourceBook(ProcessLedger(tmp_path / "ledger.json"))
    process = ProcessReconciler(ResourcePool(ResourceLeaseManager()), book).start(
        declaration,
        definition=CapabilityDefinition(
            instance_id="model.openai_chat_model",
            module_paths=(),
        ),
        pid=301,
    )
    kinds = [kind_name(grant.kind) for grant in process.activation.grants]
    assert kinds == ["model", "network", "memory"]
    memory = process.activation.grants[2]
    assert memory.metadata["identity"]["scope"] == "chat"
    saved = (tmp_path / "ledger.json").read_text(encoding="utf-8")
    assert '"scope": "chat"' in saved or '"scope":"chat"' in saved


def test_with_cannot_replace_a_default_resource() -> None:
    with pytest.raises(ValueError, match="不能改默认资源: network"):
        append_chosen(_model_declaration(), ("network=别的",))


def test_with_requires_an_identity() -> None:
    with pytest.raises(ValueError, match="还缺身份"):
        append_chosen(_model_declaration(), ("memory",))


def test_a_kind_with_two_identity_fields_is_refused() -> None:
    declaration = ProcessDeclaration(
        capability="sample.capability",
        resources=(ResourceClaim(kind="tool", identity={"id": "files"}),),
    )
    with pytest.raises(ValueError, match="model 还缺身份"):
        append_chosen(declaration, ("model=openai",))
