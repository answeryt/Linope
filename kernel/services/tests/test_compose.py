"""chain, group and chord speak in requests and tickets."""

from __future__ import annotations

from kernel.services.compose import chain, chord, group
from kernel.services.contracts import ServiceRequest, Ticket
from kernel.services.ingress import normalize_request


class _Service:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    def submit(self, request: ServiceRequest, *, timeout: float = 10.0) -> Ticket:
        del timeout
        self.sent.append(request.message())
        return Ticket(ticket_id=str(len(self.sent)), process_id="p")

    def wait(self, ticket: Ticket, timeout: float = 10.0) -> dict:
        del timeout
        return {"n": int(ticket.ticket_id)}

    def members(self):
        return ()

    def close(self) -> None:
        return None


def test_chain_carries_the_previous_reply() -> None:
    service = _Service()
    ticket = chain(
        service,
        (ServiceRequest(operation="ping"), ServiceRequest(operation="ping")),
    )
    assert ticket.ticket_id == "2"
    assert service.sent[1]["prior"] == {"n": 1}


def test_group_submits_without_waiting_first() -> None:
    service = _Service()
    tickets = group(service, (ServiceRequest(operation="ping"),) * 2)
    assert [ticket.ticket_id for ticket in tickets] == ["1", "2"]
    assert all("prior" not in message for message in service.sent)


def test_chord_waits_then_submits_the_results() -> None:
    service = _Service()
    ticket = chord(
        service,
        (ServiceRequest(operation="ping"), ServiceRequest(operation="ping")),
        ServiceRequest(operation="ping"),
    )
    assert ticket.ticket_id == "3"
    assert service.sent[2]["results"] == [{"n": 1}, {"n": 2}]


def test_plain_text_needs_a_kind_and_a_message_keeps_its_extras() -> None:
    request = normalize_request("你好", kind="message")
    assert request.message() == {"operation": "load", "kind": "message", "body": "你好"}
    carried = normalize_request({"operation": "load", "kind": "tool", "body": {}, "href": "h"})
    assert carried.message()["href"] == "h"
