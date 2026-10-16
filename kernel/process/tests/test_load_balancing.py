"""Resource-hint balancing across peer processes and a resizable worker pool."""

from __future__ import annotations

import asyncio
import os
import threading

from kernel.command.thread import run as thread_command
from kernel.load_balancing.hints import seats
from kernel.load_balancing.inflight import InflightLimit
from kernel.load_balancing.pick import choose
from kernel.load_balancing.process_scale import close_idle
from kernel.load_balancing.route import route
from kernel.load_balancing.workers import WorkerPool, raise_ceiling
from kernel.process.ledger import FileResourceStore
from kernel.process.process_manager.liveness import process_identity
from kernel.process.ledger import MemoryResourceStore
from kernel.resource.account import record_context

CAPABILITY = "model.openai_chat_model"
GROUP = {"capability": CAPABILITY}


def _bind(store: MemoryResourceStore, process_id: str, *, shared: bool) -> None:
    del shared
    store.register_process(process_id, CAPABILITY, None, "starting")
    store.update_process(process_id, status="running")
    store.set_activation(
        process_id,
        {
            "thread_policy": {
                "max_concurrent_tasks": 1,
                "max_sync_workers": 1,
            },
        },
    )


def _shared_pair() -> MemoryResourceStore:
    store = MemoryResourceStore()
    store.share_capabilities((CAPABILITY,))
    _bind(store, "p1", shared=True)
    _bind(store, "p2", shared=True)
    return store


def test_grant_window_is_not_the_context_ceiling() -> None:
    store = _shared_pair()
    store.set_activation(
        "p1",
        {
            "thread_policy": {"max_concurrent_tasks": 1},
            "resource_context": {
                "grants": [{"kind": "workspace", "handle": "h", "limits": {"window": 1}}]
            },
        },
    )
    found = next(seat for seat in seats(store, "", GROUP) if seat.process_id == "p1")
    assert found.window is None
    assert found.budget_full is False


def test_pick_avoids_the_slower_peer() -> None:
    store = _shared_pair()
    store.replace_note("p1", "rtt", {"ms": 50})
    store.replace_note("p2", "rtt", {"ms": 500})
    chosen = choose(seats(store, "", GROUP))
    assert chosen is not None
    assert chosen.process_id == "p1"


def test_route_refuses_work_that_is_not_reserved() -> None:
    store = _shared_pair()
    try:
        route(
            store,
            kind="",
            identity=GROUP,
            body={"lane": "interactive", "operation": "load"},
            capability=CAPABILITY,
            opener=lambda: "p3",
        )
    except RuntimeError as exc:
        assert "还没预定" in str(exc)
    else:
        raise AssertionError("placed a request that was not reserved")


def test_route_places_a_reserved_request() -> None:
    store = _shared_pair()
    request_id = store.submit_request(
        "",
        {"lane": "next", "service_key": "p1,p2", "operation": "load"},
    )
    assert store.reserve_request(request_id)
    routed = route(
        store,
        kind="",
        identity=GROUP,
        body={
            "lane": "next",
            "service_key": "p1,p2",
            "request_id": request_id,
            "operation": "load",
        },
        capability=CAPABILITY,
        opener=lambda: "unused",
    )
    assert routed == request_id
    placed = store.lookup_request(request_id)
    assert placed["status"] == "reserved"
    assert placed["process_id"] in {"p1", "p2"}


def test_pick_scans_one_or_two_open_seats() -> None:
    store = _shared_pair()
    store.submit_request("p1", {"operation": "ping"})
    store.claim_request("p1", "worker", 30)
    found = seats(store, "", GROUP)
    chosen = choose(found)
    assert chosen is not None
    assert chosen.process_id == "p2"


def test_separate_copies_are_not_one_pool() -> None:
    store = MemoryResourceStore()
    _bind(store, "p1", shared=False)
    _bind(store, "p2", shared=False)
    try:
        route(
            store,
            kind="",
            identity=GROUP,
            body={"operation": "ping"},
            capability=CAPABILITY,
            opener=lambda: "p3",
        )
    except ValueError as exc:
        assert "不能互相分单" in str(exc)
    else:
        raise AssertionError("exclusive copies were pooled")


def test_route_uses_the_open_peer_and_opens_when_full() -> None:
    store = _shared_pair()
    store.submit_request("p1", {"operation": "ping"})
    store.claim_request("p1", "worker", 30)
    request_id = route(
        store,
        kind="",
        identity=GROUP,
        body={"operation": "load"},
        capability=CAPABILITY,
        opener=lambda: "unused",
    )
    assert store.lookup_request(request_id)["process_id"] == "p2"

    store.submit_request("p2", {"operation": "ping"})
    store.claim_request("p2", "worker", 30)
    opened: list[str] = []

    def opener() -> str:
        _bind(store, "p3", shared=True)
        opened.append("p3")
        return "p3"

    routed = route(
        store,
        kind="",
        identity=GROUP,
        body={"operation": "load"},
        capability=CAPABILITY,
        opener=opener,
        thread_safe=False,
    )
    assert opened == ["p3"]
    assert store.lookup_request(routed)["process_id"] == "p3"


def test_full_window_does_not_add_a_thread() -> None:
    store = _shared_pair()
    record_context(store, "p1", occupied=2, ceiling=1, output_tokens=2)
    record_context(store, "p2", occupied=2, ceiling=1, output_tokens=2)
    opened: list[str] = []

    def opener() -> str:
        _bind(store, "p3", shared=True)
        opened.append("p3")
        return "p3"

    routed = route(
        store,
        kind="",
        identity=GROUP,
        body={"operation": "load"},
        capability=CAPABILITY,
        opener=opener,
        thread_safe=True,
        max_threads=4,
    )
    assert opened == ["p3"]
    assert store.lookup_request(routed)["process_id"] == "p3"
    assert store.get_process("p1").get("worker_ceiling") is None


def test_thread_safe_peer_grows_its_ceiling_before_a_new_process() -> None:
    store = _shared_pair()
    for process_id in ("p1", "p2"):
        store.submit_request(process_id, {"operation": "ping"})
        store.claim_request(process_id, "worker", 30)
    routed = route(
        store,
        kind="",
        identity=GROUP,
        body={"operation": "load"},
        capability=CAPABILITY,
        opener=lambda: "nope",
        thread_safe=True,
        max_threads=3,
    )
    host = store.lookup_request(routed)["process_id"]
    assert store.get_process(host)["worker_ceiling"] == 2


def test_unshared_full_pool_refuses_a_second_process() -> None:
    store = MemoryResourceStore()
    _bind(store, "p1", shared=False)
    store.submit_request("p1", {"operation": "ping"})
    store.claim_request("p1", "worker", 30)
    try:
        route(
            store,
            kind="",
            identity=GROUP,
            body={"operation": "load"},
            capability=CAPABILITY,
            opener=lambda: "p2",
        )
    except ValueError as exc:
        assert "还没点名共享" in str(exc)
    else:
        raise AssertionError("opened a second exclusive process")


def test_close_idle_stops_the_heavier_idle_peer_first() -> None:
    store = _shared_pair()
    found = seats(store, "", GROUP)
    closed = close_idle(store, found, floor=1)
    assert closed == ("p2",)
    assert store.get_process("p1").get("desired") != "stop"
    assert store.get_process("p2")["desired"] == "stop"


def test_close_idle_keeps_the_process_that_will_take_the_request() -> None:
    store = _shared_pair()
    found = seats(store, "", GROUP)
    closed = close_idle(store, found, floor=1, keep="p1")
    assert closed == ("p2",)
    assert store.get_process("p2")["desired"] == "stop"
    assert store.get_process("p1").get("desired") != "stop"


def test_slow_replies_lower_the_inflight_allowance() -> None:
    limit = InflightLimit(minimum=1, maximum=20, queue_size=4)
    limit.sample(0.01, 20)
    for _ in range(12):
        limit.sample(1.0, 20)
    assert limit.current < 20
    limit.set_maximum(20)
    for _ in range(8):
        limit.sample(0.01, limit.current)
    assert limit.current <= 20


def test_worker_ceiling_can_rise_while_the_pool_is_running() -> None:
    pool = WorkerPool(1)
    seen: list[str] = []
    gate = threading.Event()

    def block() -> str:
        seen.append(threading.current_thread().name)
        gate.wait(timeout=1)
        return "ok"

    async def run() -> None:
        pool.add(1)
        first = asyncio.create_task(pool.run(block))
        second = asyncio.create_task(pool.run(block))
        await asyncio.sleep(0.05)
        assert pool.max_workers == 2
        gate.set()
        assert await first == "ok"
        assert await second == "ok"
        pool.shutdown()

    asyncio.run(run())
    assert len(seen) == 2


def test_thread_command_raises_the_ceiling_on_the_ledger(tmp_path) -> None:
    path = tmp_path / "resources.json"
    store = FileResourceStore(path)
    store.register_process("p1", CAPABILITY, None, "starting")
    store.mark_running(
        "p1",
        os.getpid(),
        process_identity(os.getpid()),
        {"sync_thread_safe": True, "is_async": False},
    )
    store.close()
    locator = f"file:{path}"
    assert thread_command(["add", CAPABILITY, "--resource-store", locator]) == 0
    reopened = FileResourceStore(path)
    try:
        assert reopened.get_process("p1")["worker_ceiling"] == 2
        assert raise_ceiling(reopened, CAPABILITY, 1) == 3
    finally:
        reopened.close()
    assert thread_command(["remove", CAPABILITY, "--resource-store", locator]) == 0
    again = FileResourceStore(path)
    try:
        assert again.get_process("p1")["worker_ceiling"] == 2
    finally:
        again.close()


def test_thread_command_refuses_an_unsafe_plugin(tmp_path) -> None:
    path = tmp_path / "resources.json"
    store = FileResourceStore(path)
    store.register_process("p1", "tools.session_search", None, "starting")
    store.mark_running(
        "p1",
        os.getpid(),
        process_identity(os.getpid()),
        {"sync_thread_safe": False, "is_async": False},
    )
    store.close()
    code = thread_command(
        ["add", "tools.session_search", "--resource-store", f"file:{path}"]
    )
    assert code == 1
