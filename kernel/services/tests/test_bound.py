"""Tests for services attached to existing processes."""

from __future__ import annotations

from kernel.services.bound import BoundService
from kernel.services.contracts import Ticket


class _DelayedStore:
    def __init__(self) -> None:
        self.lookups = 0

    def selected_channel(self) -> tuple[None, dict]:
        return None, {}

    def lookup_request(self, request_id: str) -> dict:
        assert request_id == "1"
        self.lookups += 1
        if self.lookups == 1:
            return {"status": "pending"}
        return {"status": "done", "reply": {"event": "result"}}


def test_bound_service_wait_has_no_fixed_ten_second_deadline(monkeypatch) -> None:
    store = _DelayedStore()
    service = BoundService("chat", store)
    service._receipts["1"] = "process"
    clock = iter((0.0, 11.0))
    monkeypatch.setattr("kernel.services.bound.time.monotonic", lambda: next(clock))
    monkeypatch.setattr("kernel.services.bound.time.sleep", lambda _seconds: None)

    assert service.wait(Ticket("1", "process")) == {"event": "result"}
    assert store.lookups == 2
