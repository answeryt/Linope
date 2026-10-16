import pytest

from kernel.process.declaration import ProcessDeclaration, ResourceClaim
from kernel.process.reconcile import ProcessReconciler
from kernel.resource.compile import compile_declaration
from kernel.resource.definition import ResourceKind, ResourceShareMode
from kernel.resource.lease import ResourceLeaseManager
from kernel.resource.pool import RecordingLoader, ResourcePool
from kernel.process.ledger import FileResourceStore


class _Boom(RecordingLoader):
    def load(self, kind, identity):
        raise RuntimeError("load failed")


def _claim(kind: ResourceKind, **identity: str) -> ResourceClaim:
    return ResourceClaim(kind=kind, identity=identity)


def _model_declaration(*, share_requested: bool, temperature: float = 0.2) -> ProcessDeclaration:
    return ProcessDeclaration(
        capability="model.openai_chat_model",
        resources=(
            ResourceClaim(
                kind=ResourceKind.CONTEXT,
                identity={"id": "window"},
                call_params={"temperature": temperature},
                share_requested=share_requested,
            ),
        ),
    )


def _tool_declaration() -> ProcessDeclaration:
    return ProcessDeclaration(
        capability="tools.bash",
        resources=(
            ResourceClaim(
                kind=ResourceKind.TOOL,
                identity={"tool": "bash"},
                share_requested=True,
            ),
        ),
    )


def test_prompt_text_does_not_change_model_entity_key() -> None:
    from kernel.resource.compile import entity_key

    identity = {"id": "window"}
    first = entity_key(ResourceKind.CONTEXT, identity, process_id="model-process")
    second = entity_key(
        ResourceKind.CONTEXT,
        {"id": "window"},
        process_id="model-process",
    )
    assert first == second
    other = entity_key(
        ResourceKind.CONTEXT,
        {"id": "window", "prompt": "请你甲"},
        process_id="model-process",
    )
    assert other != first


def test_call_params_do_not_change_entity_key() -> None:
    cool = compile_declaration(_model_declaration(share_requested=True), "p1")
    warm = compile_declaration(
        _model_declaration(share_requested=True, temperature=0.9),
        "p1",
    )
    assert cool[0].resource_id == warm[0].resource_id
    assert cool[0].call_params != warm[0].call_params


def test_tool_share_request_is_denied_and_private() -> None:
    first = compile_declaration(_tool_declaration(), "process-a")
    second = compile_declaration(_tool_declaration(), "process-b")
    assert first[0].share_granted is False
    assert first[0].share_mode == ResourceShareMode.EXCLUSIVE
    assert first[0].resource_id != second[0].resource_id

    pool = ResourcePool(ResourceLeaseManager())
    pool.bind("process-a", "tools.bash", first)
    pool.bind("process-b", "tools.bash", second)
    assert pool.store.entity(first[0].resource_id).refcount == 1
    assert pool.store.entity(second[0].resource_id).refcount == 1


def test_unshared_model_is_private_to_each_process() -> None:
    pool = ResourcePool(ResourceLeaseManager())
    first = compile_declaration(_model_declaration(share_requested=False), "process-a")
    second = compile_declaration(_model_declaration(share_requested=False), "process-b")
    assert first[0].resource_id != second[0].resource_id
    pool.bind("process-a", "model.openai_chat_model", first)
    pool.bind("process-b", "model.openai_chat_model", second)
    assert pool.store.entity(first[0].resource_id).refcount == 1
    assert pool.store.entity(second[0].resource_id).refcount == 1


def test_shared_model_unloads_only_at_zero_and_does_not_bump_fencing() -> None:
    events: list[dict] = []
    pool = ResourcePool(ResourceLeaseManager(), listener=events.append)
    first = compile_declaration(
        _model_declaration(share_requested=False),
        "process-a",
        shared=True,
    )
    second = compile_declaration(
        _model_declaration(share_requested=False),
        "process-b",
        shared=True,
    )
    pool.bind("process-a", "model.openai_chat_model", first)
    token = pool.store.entity(first[0].resource_id).fencing_token
    pool.bind("process-b", "model.openai_chat_model", second)
    assert pool.store.entity(first[0].resource_id).fencing_token == token
    assert pool.store.active_for("process-a")[0].fencing_token == token
    assert pool.store.active_for("process-b")[0].fencing_token == token
    assert pool.store.entity(first[0].resource_id).refcount == 2

    pool.release("process-a")
    assert pool.store.entity(first[0].resource_id).status == "loaded"
    assert pool.store.entity(first[0].resource_id).refcount == 1
    pool.release("process-b")
    assert pool.store.entity(first[0].resource_id).status == "unloaded"
    assert pool.store.entity(first[0].resource_id).refcount == 0
    assert any(event["event"] == "resource_unloaded" for event in events)

    private = compile_declaration(_model_declaration(share_requested=False), "process-c")
    assert private[0].resource_id != first[0].resource_id
    pool.bind("process-c", "model.openai_chat_model", private)
    assert pool.store.entity(private[0].resource_id).fencing_token == 1
    assert pool.store.entity(first[0].resource_id).fencing_token == token


def test_load_failure_rolls_back_the_lease() -> None:
    events: list[dict] = []
    pool = ResourcePool(
        ResourceLeaseManager(),
        loader=_Boom(),
        listener=events.append,
    )
    compiled = compile_declaration(_model_declaration(share_requested=False), "process-a")
    with pytest.raises(RuntimeError, match="load failed"):
        pool.bind("process-a", "model.openai_chat_model", compiled)
    assert pool.store.active_for("process-a") == ()
    entity = pool.store.entity(compiled[0].resource_id)
    assert entity is not None
    assert entity.refcount == 0
    assert entity.status == "unloaded"
    assert any(event["event"] == "resource_load_failed" for event in events)


def test_revoke_drops_the_handle_and_unloads_at_zero() -> None:
    pool = ResourcePool(ResourceLeaseManager())
    compiled = compile_declaration(_model_declaration(share_requested=False), "process-a")
    pool.bind("process-a", "model.openai_chat_model", compiled)
    handle = pool.grants_for("process-a")[0].handle
    revocation = pool.revoke(handle)
    assert revocation.handle == handle
    assert pool.store.entity(compiled[0].resource_id).refcount == 0
    assert pool.store.entity(compiled[0].resource_id).status == "unloaded"
    with pytest.raises(KeyError):
        pool.revoke(handle)


def test_reopen_reaps_a_dead_process(tmp_path) -> None:
    path = tmp_path / "resources.json"
    store = FileResourceStore(path)
    pool = ResourcePool(store)
    store.register_process("dead-process", "context.sliding_window", None, "starting")
    compiled = compile_declaration(
        ProcessDeclaration(
            capability="context.sliding_window",
            resources=(_claim(ResourceKind.CONTEXT, window="default"),),
        ),
        "dead-process",
    )
    pool.bind("dead-process", "context.sliding_window", compiled)
    resource_id = compiled[0].resource_id
    store.close()

    reopened = FileResourceStore(path)
    try:
        assert reopened.active_for("dead-process") == ()
        entity = reopened.entity(resource_id)
        assert entity is not None
        assert entity.refcount == 0
        assert entity.status == "unloaded"
    finally:
        reopened.close()


def test_child_payload_omits_resource_id(tmp_path) -> None:
    pool = ResourcePool(FileResourceStore(tmp_path / "resources.json"))
    process = ProcessReconciler(pool).start(
        ProcessDeclaration(
            capability="context.sliding_window",
            resources=(
                ResourceClaim(
                    kind=ResourceKind.CONTEXT,
                    identity={"window": "default"},
                    call_params={"render": "plain"},
                ),
            ),
        )
    )
    try:
        ready = process.send({"operation": "ping"})
        assert ready["event"] == "pong"
        grant = process.activation.resource_context.payload()["grants"][0]
        assert "resource_id" not in grant
        assert grant["call_params"] == {"render": "plain"}
        assert grant["handle"]
    finally:
        process.stop()
        pool.store.close()
