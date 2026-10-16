"""Sharing follows the capability list, not the resource kind."""

from kernel.process.declaration import ProcessDeclaration, ResourceClaim
from kernel.resource.compile import compile_declaration
from kernel.resource.definition import ResourceKind
from kernel.resource.lease import ResourceLeaseManager
from kernel.resource.pool import ResourcePool


def _model() -> ProcessDeclaration:
    return ProcessDeclaration(
        capability="model.openai_chat_model",
        resources=(
            ResourceClaim(
                kind=ResourceKind.CONTEXT,
                identity={"id": "window"},
            ),
        ),
    )


def test_unshared_capabilities_bind_separate_entities() -> None:
    first = compile_declaration(_model(), "process-a")
    second = compile_declaration(_model(), "process-b")
    assert first[0].resource_id != second[0].resource_id
    pool = ResourcePool(ResourceLeaseManager())
    pool.bind("process-a", "model.openai_chat_model", first)
    pool.bind("process-b", "model.openai_chat_model", second)
    assert pool.store.entity(first[0].resource_id).refcount == 1
    assert pool.store.entity(second[0].resource_id).refcount == 1


def test_shared_capability_is_one_entity() -> None:
    first = compile_declaration(_model(), "process-a", shared=True)
    second = compile_declaration(_model(), "process-b", shared=True)
    assert first[0].resource_id == second[0].resource_id
    pool = ResourcePool(ResourceLeaseManager())
    pool.bind("process-a", "model.openai_chat_model", first)
    pool.bind("process-b", "model.openai_chat_model", second)
    assert pool.store.entity(first[0].resource_id).refcount == 2
