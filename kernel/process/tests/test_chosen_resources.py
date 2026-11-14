"""Extra resources are chosen at start and do not replace the profile."""

from pathlib import Path

import pytest

from kernel.command.process.start import _parse_start_options, launch_options
from kernel.process.declaration import ProcessDeclaration, ResourceClaim, append_chosen
from kernel.process.ledger import ProcessLedger
from kernel.process.process_creat.instances import CapabilityDefinition
from kernel.process.reconcile import ProcessReconciler
from kernel.process.resource_record import ProcessResourceBook
from kernel.resource.lease import ResourceLeaseManager
from kernel.resource.pool import ResourcePool
from kernel.resource.resource_contract import kind_name


def test_with_is_parsed_as_extra_resources() -> None:
    options = launch_options(
        _parse_start_options(
            ["tools.read", "--with", "memory=chat", "--with", "tool=files"]
        )
    )
    assert options.chosen == ("memory=chat", "tool=files")


def test_model_is_not_a_resource() -> None:
    declaration = ProcessDeclaration(
        capability="sample.capability",
        resources=(ResourceClaim(kind="tool", identity={"id": "files"}),),
    )
    with pytest.raises(ValueError, match="Unknown resource: model"):
        append_chosen(declaration, ("model=openai",))
