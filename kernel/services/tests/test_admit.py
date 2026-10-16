"""Admission reserves recorded work before a process can claim it."""

from __future__ import annotations

import time

from kernel.process.ledger import MemoryResourceStore
from kernel.resource.account import record_context
from kernel.services.admit import cycle
from kernel.services.contracts import ServiceRequest
from kernel.services.handle import ServiceHandle
from kernel.services.spec import MemberPlan, ServicePlan
from kernel.services.tests.fakes import Process


def _running(store: MemoryResourceStore, process_id: str) -> None:
    store.register_process(process_id, "model.x", None, "starting")
    store.update_process(process_id, status="running")


def _submit(store: MemoryResourceStore, **fields: object) -> str:
    return store.submit_request("", fields)


def test_plain_request_is_still_claimed_in_arrival_order() -> None:
    store = MemoryResourceStore()
    first = store.submit_request("process", {"number": 1})
    second = store.submit_request("process", {"number": 2})
    claimed = store.claim_request("process", "worker", 30)
    assert claimed is not None
    assert claimed["request_id"] == first
    assert store.claim_request("process", "worker", 30)["request_id"] == second


def test_scheduled_request_waits_until_it_is_reserved_and_placed() -> None:
    store = MemoryResourceStore()
    request_id = _submit(store, lane="next", service_key="process")
    assert store.claim_request("process", "worker", 30) is None
    assert cycle(store) == (request_id,)
    assert store.claim_request("process", "worker", 30) is None
    assert store.place_request(request_id, "process")
    claimed = store.claim_request("process", "worker", 30)
    assert claimed is not None
    assert claimed["request_id"] == request_id


def test_interactive_takes_a_background_reservation_that_has_not_started() -> None:
    store = MemoryResourceStore()
    store.replace_note("shared", "inflight", {"current": 1})
    background = _submit(store, lane="background", service_key="shared")
    assert cycle(store) == (background,)
    interactive = _submit(store, lane="interactive", service_key="shared")
    assert cycle(store) == (interactive,)
    assert store.request_schedule(background)["status"] == "pending"
    assert store.request_schedule(interactive)["status"] == "reserved"


def test_a_lighter_service_is_reserved_before_a_heavier_one() -> None:
    store = MemoryResourceStore()
    _running(store, "heavy")
    _running(store, "light")
    record_context(store, "heavy", occupied=80, ceiling=100, output_tokens=1)
    record_context(store, "light", occupied=1, ceiling=100, output_tokens=1)
    store.replace_note("heavy", "inflight", {"current": 1})
    heavy = _submit(store, lane="background", service_key="heavy")
    light = _submit(store, lane="background", service_key="light")
    assert cycle(store) == (light,)
    assert store.request_schedule(heavy)["status"] == "pending"
    assert store.request_schedule(light)["status"] == "reserved"


def test_a_later_step_waits_until_the_previous_receipt_is_done() -> None:
    store = MemoryResourceStore()
    first = _submit(store, lane="next", service_key="agent")
    second = _submit(
        store,
        lane="interactive",
        service_key="agent",
        depends_on=first,
    )
    assert cycle(store) == (first,)
    assert store.request_schedule(second)["status"] == "pending"
    store.place_request(first, "agent")
    claim = store.claim_request("agent", "worker", 30)
    assert claim is not None
    store.complete_request(first, {"event": "result"}, claim["claim_token"])
    assert cycle(store) == (second,)


def test_an_interactive_request_closes_after_its_start_time() -> None:
    store = MemoryResourceStore()
    request_id = _submit(
        store,
        lane="interactive",
        service_key="agent",
        start_by=time.time() - 5,
    )
    assert cycle(store) == ()
    assert store.lookup_request(request_id)["status"] == "closed"


def test_a_timer_waits_until_it_is_due() -> None:
    store = MemoryResourceStore()
    waiting = _submit(
        store,
        lane="timer",
        service_key="agent",
        start_by=time.time() + 3600,
    )
    due = _submit(
        store,
        lane="timer",
        service_key="other",
        start_by=time.time() - 1,
    )
    assert cycle(store) == (due,)
    assert store.lookup_request(waiting)["status"] == "pending"


def test_a_full_context_holds_back_a_followed_result() -> None:
    store = MemoryResourceStore()
    _running(store, "agent")
    record_context(store, "agent", occupied=10, ceiling=10, output_tokens=1)
    followed = _submit(store, lane="next", service_key="agent", followed=True)
    free = _submit(store, lane="next", service_key="other", followed=False)
    assert cycle(store) == (free,)
    assert store.request_schedule(followed)["status"] == "pending"


def test_commit_waits_for_the_dependency_and_rereads_the_link(monkeypatch) -> None:
    store = MemoryResourceStore()
    parent = store.submit_request("process", {"number": 1})
    child = store.submit_request(
        "process",
        {
            "lane": "next",
            "service_key": "process",
            "depends_on": parent,
            "href": "http://resource/self",
            "relation": "pin",
        },
    )
    store.reserve_request(child)
    store.place_request(child, "process")
    claim = store.claim_request("process", "worker", 30)
    assert claim is not None
    monkeypatch.setattr(
        "kernel.process.ledger._read_representation",
        lambda href: {"_links": {}},
    )
    store.complete_request(parent, {"event": "result"})
    store.complete_request(child, {"event": "result"}, claim["claim_token"])
    assert store.lookup_request(child)["status"] == "pending"

    store.reserve_request(child)
    store.place_request(child, "process")
    claim = store.claim_request("process", "worker", 30)
    assert claim is not None
    monkeypatch.setattr(
        "kernel.process.ledger._read_representation",
        lambda href: {"_links": {"pin": {"href": href + "/pin"}}},
    )
    store.complete_request(child, {"event": "result"}, claim["claim_token"])
    assert store.lookup_request(child)["status"] == "done"
    assert store.lookup_request(child)["reply"] == {"event": "result"}


def test_a_revoked_handle_keeps_the_result_out_of_the_reply() -> None:
    store = MemoryResourceStore()
    request_id = store.submit_request(
        "process",
        {"lane": "next", "service_key": "process", "handle": "missing"},
    )
    store.reserve_request(request_id)
    store.place_request(request_id, "process")
    claim = store.claim_request("process", "worker", 30)
    assert claim is not None
    store.complete_request(request_id, {"event": "result"}, claim["claim_token"])
    row = store.lookup_request(request_id)
    assert row["status"] == "pending"
    assert row["reply"] is None


def test_service_submit_records_before_choosing_a_process() -> None:
    store = MemoryResourceStore()
    process = Process("only")
    member = MemberPlan(role="model", capability="model.x")
    plan = ServicePlan(members=(member,), route={"message": "model"})
    handle = ServiceHandle(plan, ((member, (process,)),), store)
    ticket = handle.submit(ServiceRequest(kind="message", body="hi"))
    assert process.submitted == []
    assert ticket.process_id == "only"
    row = store.lookup_request(ticket.ticket_id)
    assert row["status"] == "reserved"
    assert row["process_id"] == "only"
    assert store.request_schedule(ticket.ticket_id)["lane"] == "interactive"
    handle.close()
