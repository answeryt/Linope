"""Token pressure, channel peers, and a busy handoff each add one helper."""

from __future__ import annotations

import litellm

from kernel.calculate.measure import Pressure, count_tokens, measure
from kernel.load_balancing.relieve import relieve
from kernel.process.resource_record import (
    HeldResource,
    ProcessResourceBook,
    ProcessResourceRecord,
    RecordStatus,
)


_IMAGE = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


class _Entity:
    def __init__(self, state: dict) -> None:
        self.state = state


class _Store:
    def __init__(self, entities: dict[str, _Entity]) -> None:
        self._entities = entities

    def entity(self, resource_id: str) -> _Entity | None:
        return self._entities.get(resource_id)


class _Pool:
    def __init__(self, entities: dict[str, _Entity]) -> None:
        self.store = _Store(entities)


def _lease(kind: str, resource_id: str, identity: dict) -> HeldResource:
    return HeldResource(
        lease_id=f"{kind}-{resource_id}",
        kind=kind,
        resource_id=resource_id,
        share_mode="exclusive",
        fencing_token=1,
        handle=f"h-{resource_id}",
        identity=identity,
    )


def _ready(book: ProcessResourceBook, pid: int, leases: list[HeldResource], ceiling: int = 1) -> None:
    book.open(pid, "demo")
    book.attach(
        pid,
        claims=[],
        leases=leases,
        room={"worker_ceiling": ceiling, "inflight_ceiling": 1},
    )


def test_text_tokens_match_litellm() -> None:
    text = "Hello world"
    assert count_tokens("gpt-4o", text) == litellm.token_counter(model="gpt-4o", text=text)


def test_an_image_adds_tokens() -> None:
    text = count_tokens("gpt-4o", "see this")
    image = count_tokens("gpt-4o", _IMAGE)
    assert image > 0
    assert text + image > text


def test_full_context_adds_one_helper() -> None:
    book = ProcessResourceBook()
    _ready(book, 7, [])
    pressure = Pressure(
        tokens=100,
        context_limit=100,
        context_full=True,
        channel="",
        peers=0,
        activity="sleeping",
    )
    assert relieve(book, 7, pressure, delegating=False) == 2
    assert book.get(7).room["worker_ceiling"] == 2


def test_busy_handoff_adds_one_helper() -> None:
    book = ProcessResourceBook()
    _ready(book, 7, [])
    pressure = Pressure(0, 256000, False, "", 0, "self")
    assert relieve(book, 7, pressure, delegating=True) == 2


def test_channel_peer_while_with_adds_one_helper() -> None:
    book = ProcessResourceBook()
    network = _lease("network", "net", {"channel": "ledger"})
    _ready(book, 7, [network])
    _ready(book, 8, [network])
    record = book.get(7)
    pool = _Pool({})
    pressure = measure(pool=pool, record=record, book=book, activity="with")
    assert pressure.peers == 1
    assert relieve(book, 7, pressure, delegating=False) == 2


def test_sleeping_alone_does_not_add() -> None:
    book = ProcessResourceBook()
    network = _lease("network", "net", {"channel": "ledger"})
    memory = _lease("memory", "mem", {"scope": "chat"})
    _ready(book, 7, [network, memory])
    pool = _Pool({"mem": _Entity({"items": {"system": {"class": "system", "content": "rules"}}})})
    pressure = measure(
        pool=pool,
        record=book.get(7),
        book=book,
        activity="sleeping",
        model="gpt-4o",
    )
    assert pressure.peers == 0
    assert pressure.context_full is False
    assert relieve(book, 7, pressure, delegating=True) == 1


def test_repeated_pressure_can_pass_four() -> None:
    book = ProcessResourceBook()
    _ready(book, 7, [])
    pressure = Pressure(1, 1, True, "", 0, "sleeping")
    ceiling = 1
    for _ in range(5):
        ceiling = relieve(book, 7, pressure, delegating=False)
    assert ceiling == 6
    assert ceiling > 4
