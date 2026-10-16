from __future__ import annotations

from kernel.process.declaration import ProcessDeclaration, ResourceClaim
from kernel.resource.compile import compile_declaration
from kernel.resource.definition import ResourceKind
from kernel.process.ledger import FileResourceStore
from kernel.process.ledger import MemoryResourceStore
from kernel.resource.pool import ResourcePool
from kernel.process.ledger import open_store, store_names


def _compiled(process_id: str = "process"):
    declaration = ProcessDeclaration(
        capability="context.sliding_window",
        resources=(
            ResourceClaim(
                kind=ResourceKind.CONTEXT,
                identity={"window": "default"},
            ),
        ),
    )
    return compile_declaration(declaration, process_id)


def test_registry_exposes_all_builtin_store_kinds() -> None:
    names = set(store_names())
    assert {"file", "memory"} <= names
    assert "mysql" not in names
    assert "postgresql" not in names


def test_memory_store_supports_requests_and_channels() -> None:
    store = MemoryResourceStore()
    assert store.check()["persistent"] is False
    store.select_channel("custom", {"enabled": True})
    assert store.selected_channel() == ("custom", {"enabled": True})
    request_id = store.submit_request("process", {"operation": "ping"})
    assert store.take_request("process")["request_id"] == request_id
    store.complete_request(request_id, {"event": "pong"})
    assert store.lookup_request(request_id)["reply"] == {"event": "pong"}


def test_file_store_reopens_resource_state(tmp_path) -> None:
    path = tmp_path / "resources.json"
    store = FileResourceStore(path, reap=False)
    compiled = _compiled()
    ResourcePool(store).bind("process", "context.sliding_window", compiled)
    store.close()

    reopened = FileResourceStore(path, reap=False)
    try:
        assert reopened.active_for("process")
        assert reopened.entity(compiled[0].resource_id).refcount == 1
    finally:
        reopened.close()


def test_file_store_reads_a_flat_version_one_document(tmp_path) -> None:
    import json

    path = tmp_path / "resources.json"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "processes": {
                    "p1": {
                        "process_id": "p1",
                        "capability_id": "tools.bash",
                        "pid": None,
                        "status": "running",
                    }
                },
                "channel": ["ledger", {"enabled": True}],
                "requests": {
                    "1": {
                        "request_id": "1",
                        "process_id": "p1",
                        "status": "pending",
                        "body": {"operation": "ping"},
                        "reply": None,
                    }
                },
                "request_sequence": 1,
            }
        ),
        encoding="utf-8",
    )
    store = FileResourceStore(path, reap=False)
    try:
        assert store.get_process("p1")["capability_id"] == "tools.bash"
        assert store.selected_channel() == ("ledger", {"enabled": True})
        assert store.take_request("p1")["request_id"] == "1"
    finally:
        store.close()


def test_database_store_stops_when_the_driver_is_missing() -> None:
    import pytest

    with pytest.raises(RuntimeError, match="驱动"):
        open_store("postgresql+nosuch://user@localhost/ledger", reap=False)


def test_database_store_reopens_resource_state(tmp_path) -> None:
    locator = "sqlite:///" + (tmp_path / "ledger.db").as_posix()
    store = open_store(locator, reap=False)
    compiled = _compiled()
    ResourcePool(store).bind("process", "context.sliding_window", compiled)
    store.initialize_schema()
    store.migrate()
    store.close()

    reopened = open_store(locator, reap=False)
    try:
        assert reopened.check()["backend"] == "database"
        assert reopened.active_for("process")
        assert reopened.entity(compiled[0].resource_id).refcount == 1
        reopened.initialize_schema()
        reopened.migrate()
    finally:
        reopened.close()


def test_path_locator_still_opens_file_store(tmp_path) -> None:
    path = tmp_path / "resources.json"
    store = open_store(path)
    try:
        assert store.check()["backend"] == "file"
        assert store.locator.startswith("file:")
    finally:
        store.close()
