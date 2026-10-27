"""Memory data stays in the resource. Admission stays in the scheduler."""

import pytest

from kernel.resource.lease import ResourceLeaseManager
from kernel.resource.memory.state import open_state
from kernel.resource.memory.store import append_row
from kernel.scheduler.access import capacity_full, remember


def test_a_new_memory_is_an_address_range() -> None:
    assert open_state({"scope": "chat"}) == {"address_space": {"scope": "chat"}}


def test_a_row_keeps_the_original_text() -> None:
    state = open_state({"scope": "chat"})
    assert append_row(state, "user", "hello", "asked") == "message/0"
    assert state["items"]["message/0"]["content"] == "hello"
    assert "tokens" not in state["items"]["message/0"]


def test_capacity_is_a_scheduler_decision() -> None:
    assert capacity_full(3, 3)
    assert not capacity_full(2, 3)
    assert not capacity_full(9, 0)


def test_a_named_lookup_is_not_an_access_right() -> None:
    with pytest.raises(PermissionError, match="address space"):
        ResourceLeaseManager().memory_named("chat")


def test_the_public_address_entry_is_the_scheduler() -> None:
    from kernel.communication import address

    assert address.remember is remember
