"""Requests go to a role by the blueprint's table, never by a rule of our own."""

from __future__ import annotations

import pytest

from kernel.load_balancing.hints import Seat
from kernel.services.contracts import ServiceRequest
from kernel.services.handle import ServiceHandle
from kernel.services.spec import MemberPlan, ServicePlan
from kernel.services.tests.fakes import Process, Store


def _seat(process_id: str) -> Seat:
    return Seat(
        process_id=process_id,
        resource_id="same",
        capability_id="model.x",
        kind="model",
        identity={"id": "x"},
        pending=0,
        claimed=0,
        limits={},
        capacity=4,
        window=None,
        used=0,
        share_mode="shared",
        handle="h",
    )


def _handle(processes: tuple[Process, ...], *, route: dict[str, str] | None = None, **hooks):
    member = MemberPlan(role="model", capability="model.x")
    plan = ServicePlan(members=(member,), route=route if route is not None else {"prompt": "model"})
    return ServiceHandle(plan, ((member, processes),), Store(), **hooks)


def test_one_member_gets_the_request_directly() -> None:
    process = Process("only")
    seen: list = []
    handle = _handle((process,), choose=lambda seats: seen.append(seats))
    ticket = handle.submit(ServiceRequest(kind="prompt", body="hi"))
    assert process.submitted == [{"operation": "load", "kind": "prompt", "body": "hi"}]
    assert seen == []
    assert handle.wait(ticket)["request_id"] == "only-1"
    handle.close()
    assert process.stopped is True


def test_several_copies_are_chosen_by_the_injected_picker() -> None:
    first, second = Process("a"), Process("b")
    chosen: list = []

    def choose(seats):
        chosen.append(tuple(seat.process_id for seat in seats))
        return seats[1]

    handle = _handle(
        (first, second),
        seats=lambda _store, _kind, _identity: (_seat("a"), _seat("b")),
        choose=choose,
    )
    handle.submit(ServiceRequest(kind="prompt", body="hi"))
    assert chosen == [("a", "b")]
    assert first.submitted == []
    assert second.submitted[0]["body"] == "hi"


def test_an_unreadable_seat_table_sends_to_the_first_living_member() -> None:
    first, second = Process("a"), Process("b")

    def seats(_store, _kind, _identity):
        raise RuntimeError("读不到")

    handle = _handle((first, second), seats=seats, choose=lambda _seats: pytest.fail("不应挑选"))
    handle.submit(ServiceRequest(kind="prompt", body="hi"))
    assert first.submitted and not second.submitted


def test_a_missing_route_names_the_roles_that_exist() -> None:
    model = MemberPlan(role="model", capability="model.x")
    tool = MemberPlan(role="tool:bash", capability="tools.bash")
    plan = ServicePlan(members=(model, tool))
    handle = ServiceHandle(
        plan,
        ((model, (Process("m"),)), (tool, (Process("t"),))),
        Store(),
    )
    with pytest.raises(KeyError, match="prompt"):
        handle.submit(ServiceRequest(kind="prompt", body="hi"))


def test_a_named_role_that_does_not_exist_is_refused() -> None:
    handle = _handle((Process("only"),))
    with pytest.raises(KeyError, match="tool:bash"):
        handle.submit(ServiceRequest(kind="tool", role="tool:bash"))


def test_an_unknown_ticket_is_refused() -> None:
    from kernel.services.contracts import Ticket

    handle = _handle((Process("only"),))
    with pytest.raises(KeyError, match="没有这张回执"):
        handle.wait(Ticket("missing", "only"))
