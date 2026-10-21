"""A declaration is stamped before the lease is compiled."""

import pytest

from kernel.process.declaration import ProcessDeclaration, ResourceClaim, stamp_memory_space


def test_space_is_stamped_onto_the_memory_claim() -> None:
    declaration = stamp_memory_space(
        ProcessDeclaration(
            capability="sample.capability",
            resources=(ResourceClaim(kind="memory", identity={"scope": "chat"}),),
        ),
        (("space", "message,artifact"),),
    )
    assert declaration.resources[0].call_params["space"] == "message,artifact"
    with pytest.raises(ValueError):
        stamp_memory_space(declaration, (("space", "page"),))
