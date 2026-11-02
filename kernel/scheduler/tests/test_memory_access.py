"""Memory data stays in the store. Admission stays in the scheduler."""

import pytest

from kernel.resource.lease import ResourceLeaseManager
from kernel.resource.memory.footprint import footprint
from kernel.resource.memory.runtime import MemoryRuntime
from kernel.resource.memory.state import open_state
from kernel.scheduler.access import remember


def test_a_new_memory_is_a_scope_handle() -> None:
    assert open_state({"scope": "chat"}) == {"scope": "chat", "backend": ""}


def test_a_row_keeps_the_original_text() -> None:
    runtime = MemoryRuntime()
    address = runtime.append(
        resource_id="mem",
        scope="chat",
        holders=[("7", ("message",))],
        writer_pid="7",
        kind="user",
        content="hello",
        row_state="asked",
    )
    assert address == "chat/message/0"
    row = runtime.store.row("mem", "message/0")
    assert row is not None
    assert row.content == "hello"
    assert row.tokens > 0


def test_the_prompt_budget_uses_the_model_limit() -> None:
    small = footprint(context_limit=100, system="x" * 40, message="y" * 40)
    assert small.available < 100
    assert small.output_reserve == 12
    assert small.safety_margin == 2
    empty = footprint(context_limit=0, system="hello")
    assert empty.available == -empty.used


def test_a_named_lookup_is_not_an_access_right() -> None:
    with pytest.raises(PermissionError, match="address space"):
        ResourceLeaseManager().memory_named("chat")


def test_the_public_address_entry_is_the_scheduler() -> None:
    from kernel.communication import address

    assert address.remember is remember
