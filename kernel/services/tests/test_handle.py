"""Requests go to a role by the blueprint's table, never by a rule of our own."""

from __future__ import annotations

import pytest

from kernel.services.contracts import ServiceRequest
from kernel.services.handle import ServiceHandle
from kernel.services.spec import MemberPlan, ServicePlan
from kernel.services.tests.fakes import Process


def _handle(processes: tuple[Process, ...], *, route: dict[str, str] | None = None):
    member = MemberPlan(role="model", capability="model.x")
    plan = ServicePlan(members=(member,), route=route if route is not None else {"message": "model"})
    return ServiceHandle(plan, ((member, processes),))


def test_one_member_gets_the_request_directly() -> None:
    process = Process("only")
    handle = _handle((process,))
    ticket = handle.submit(ServiceRequest(kind="message", body="hi"))
    assert process.submitted == [{"operation": "load", "kind": "message", "body": "hi"}]
    assert handle.wait(ticket)["request_id"] == "only-1"
    handle.close()
    assert process.stopped is True


def test_a_missing_route_names_the_roles_that_exist() -> None:
    model = MemberPlan(role="model", capability="model.x")
    tool = MemberPlan(role="tool:bash", capability="tools.bash")
    plan = ServicePlan(members=(model, tool))
    handle = ServiceHandle(
        plan,
        ((model, (Process("m"),)), (tool, (Process("t"),))),
    )
    with pytest.raises(KeyError, match="message"):
        handle.submit(ServiceRequest(kind="message", body="hi"))


def test_a_named_role_that_does_not_exist_is_refused() -> None:
    handle = _handle((Process("only"),))
    with pytest.raises(KeyError, match="tool:bash"):
        handle.submit(ServiceRequest(kind="tool", role="tool:bash"))


def test_closing_a_launched_session_stops_its_process() -> None:
    process = Process("planner-model")
    handle = _handle((process,))
    handle.close()
    assert process.stopped is True


def test_a_stop_failure_is_visible_after_close() -> None:
    process = Process("only")

    def stop() -> None:
        raise RuntimeError("还没停下")

    process.stop = stop
    handle = _handle((process,))
    handle.close()
    assert handle.close_errors == ["only: 还没停下"]


def test_an_unknown_ticket_is_refused() -> None:
    from kernel.services.contracts import Ticket

    handle = _handle((Process("only"),))
    with pytest.raises(KeyError, match="没有这张回执"):
        handle.wait(Ticket("missing", "only"))
