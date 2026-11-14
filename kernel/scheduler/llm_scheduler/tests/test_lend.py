"""A file read lends the model to the process that is ready to ask."""

from __future__ import annotations

import json
import threading
import time
from queue import Empty, Queue
from types import SimpleNamespace

from kernel.command.events import CollectingEventSink
from kernel.command.process.clerk import KernelRuntime
from kernel.scheduler.llm_scheduler.drive import Drive
from kernel.scheduler.model_scheduler.cores import Cores


class _Script:
    """One fake process. Each reply uncovers the next line it wants to say."""

    def __init__(
        self,
        pid: int,
        name: str,
        script: list[dict[str, str]],
        *,
        slot: str = "",
    ) -> None:
        self.pid = pid
        self.is_alive = True
        settings = {"slot": slot} if slot else {}
        self.activation = SimpleNamespace(
            pid=pid,
            grants=(),
            definition=SimpleNamespace(instance_id=name),
            settings=settings,
        )
        self._script = list(script)
        self._box: Queue[dict[str, str]] = Queue()
        self._open = False

    def begin_exchange(
        self,
        message: dict,
        on_notice: object = None,
        *,
        wait: float | None = 0,
    ) -> bool:
        del message, on_notice, wait
        if self._open:
            raise RuntimeError("This process is already being asked")
        self._open = True
        self._push()
        return True

    def next_line(self, timeout: float | None) -> dict[str, str] | None:
        del timeout
        try:
            return self._box.get_nowait()
        except Empty:
            return None

    def reply_command(self, result: str = "", error: str = "", thread: str = "") -> None:
        del result, error, thread
        self._push()

    def end_exchange(self) -> None:
        self._open = False

    def _push(self) -> None:
        if not self._script:
            return
        self._box.put(self._script.pop(0))


def _seat(pid: int, name: str, *, slot: str = "") -> _Script:
    return _Script(pid, name, [], slot=slot)


def test_one_process_asks_then_reads_then_asks_again() -> None:
    order: list[str] = []
    agent = _Script(
        41,
        "agent_loop",
        [
            {"event": "command", "line": "model run -- first"},
            {"event": "command", "line": "load tool 20 -- notes"},
            {"event": "command", "line": "model run -- second"},
            {"event": "result", "result": "file-answer"},
        ],
    )
    sink = CollectingEventSink()
    clerk = KernelRuntime(sink)
    clerk._items.extend(
        [
            ("agent_loop", agent),
            ("tools.read", _seat(20, "tools.read")),
        ]
    )

    def run_command(line: str) -> str:
        order.append(line)
        return "ok"

    clerk.drive.model.run = lambda body, **_kwargs: (order.append(f"model run -- {body}") or "ok")
    clerk.drive.run_command = run_command
    assert clerk.serve(lines=["load message 41 -- hello", "exit"]) == 0
    assert [line for line in order if "first" in line or "second" in line or "load tool" in line] == [
        "model run -- first",
        "load tool 20 -- notes",
        "model run -- second",
    ]
    assert any(
        event.kind == "turn.completed" and event.data.get("result") == "file-answer"
        for event in sink.events
    )


def test_a_file_read_lends_the_model_to_the_other_process() -> None:
    order: list[str] = []
    guard = threading.Lock()
    reader = _Script(
        41,
        "agent_loop",
        [
            {"event": "command", "line": "model run -- first"},
            {"event": "command", "line": "load tool 20 -- notes"},
            {"event": "command", "line": "model run -- second"},
            {"event": "result", "result": "file-answer"},
        ],
    )
    other = _Script(
        42,
        "agent_loop",
        [
            {"event": "command", "line": "model run -- bee"},
            {"event": "result", "result": "bee-answer"},
        ],
    )
    sink = CollectingEventSink()
    clerk = KernelRuntime(sink)
    clerk._items.extend(
        [
            ("agent_loop", reader),
            ("agent_loop", other),
            ("tools.read", _seat(20, "tools.read")),
        ]
    )

    def run_command(line: str) -> str:
        with guard:
            order.append(line)
        if "load tool" in line:
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                with guard:
                    if any("bee" in item for item in order):
                        break
                time.sleep(0.01)
            time.sleep(0.15)
            with guard:
                order.append("tool-end")
            return "file"
        return "ok"

    clerk.drive.model.run = lambda body, **_kwargs: (order.append(f"model run -- {body}") or "ok")
    clerk.drive.run_command = run_command
    assert (
        clerk.serve(
            lines=[
                "load message 41 -- read the notes",
                "load message 42 -- what is one plus one",
                "exit",
            ]
        )
        == 0
    )
    with guard:
        found = list(order)
    first = next(index for index, line in enumerate(found) if "first" in line)
    tool = next(index for index, line in enumerate(found) if "load tool" in line)
    bee = next(index for index, line in enumerate(found) if "bee" in line)
    ended = found.index("tool-end")
    second = next(index for index, line in enumerate(found) if "second" in line)
    assert first < tool < bee < ended < second
    results = [
        event.data.get("result")
        for event in sink.events
        if event.kind == "turn.completed"
    ]
    assert results.index("bee-answer") < results.index("file-answer")
    slots = [event.data.get("busy") for event in sink.events if event.kind == "model.slot"]
    assert True in slots
    assert False in slots


def test_two_cores_run_together_and_waiting_task_takes_first_free_core() -> None:
    started: dict[int, threading.Event] = {
        0: threading.Event(),
        1: threading.Event(),
    }
    started_third = threading.Event()
    release = {0: threading.Event(), 1: threading.Event()}
    calls: list[tuple[int, str]] = []
    guard = threading.Lock()

    first = _Script(
        41,
        "agent_loop",
        [
            {"event": "command", "line": "model run -- first"},
            {"event": "result", "result": "first-done"},
        ],
    )
    second = _Script(
        42,
        "agent_loop",
        [
            {"event": "command", "line": "model run -- second"},
            {"event": "result", "result": "second-done"},
        ],
    )
    third = _Script(
        43,
        "agent_loop",
        [
            {"event": "command", "line": "model run -- third"},
            {"event": "result", "result": "third-done"},
        ],
    )
    sink = CollectingEventSink()
    clerk = KernelRuntime(sink)
    cores = Cores(2)
    clerk._drive = Drive(clerk, cores=cores)
    clerk._items.extend(
        [
            ("agent_loop", first),
            ("agent_loop", second),
            ("agent_loop", third),
        ]
    )

    def run_on(core: int, body: object, **_kwargs: object) -> str:
        text = str(body)
        with guard:
            calls.append((core, text))
        if text == "third":
            started_third.set()
            return "third-answer"
        started[core].set()
        assert release[core].wait(3)
        return f"{text}-answer"

    cores.model_for(0).run = lambda body, **kwargs: run_on(0, body, **kwargs)
    cores.model_for(1).run = lambda body, **kwargs: run_on(1, body, **kwargs)

    worker = threading.Thread(
        target=lambda: clerk.serve(
            lines=[
                "load message 41 -- first",
                "load message 42 -- second",
                "load message 43 -- third",
                "exit",
            ]
        ),
        daemon=True,
    )
    worker.start()
    try:
        assert started[0].wait(3)
        assert started[1].wait(3)
        release[0].set()
        assert started_third.wait(3)
        release[1].set()
        worker.join(timeout=5)
        assert not worker.is_alive()
    finally:
        release[0].set()
        release[1].set()
        worker.join(timeout=5)

    assert calls[:2] in ([ (0, "first"), (1, "second") ], [ (1, "second"), (0, "first") ])
    assert (0, "third") in calls


def test_two_tool_threads_keep_their_own_registers() -> None:
    agent = _Script(
        41,
        "agent_loop",
        [
            {"event": "command", "line": "model run -- open"},
            _fork_both(),
            {"event": "command", "line": "model run -- weather-seen"},
            {"event": "await", "thread": "41", "pc": "wait_signal"},
            {"event": "command", "line": "model run -- file-seen"},
            {"event": "result", "result": "both-done"},
        ],
    )
    sink = CollectingEventSink()
    clerk = KernelRuntime(sink)
    clerk._items.extend(
        [
            ("agent_loop", agent),
            ("tools.read", _seat(20, "tools.read")),
            ("tools.weather", _seat(21, "tools.weather")),
        ]
    )

    def run_command(line: str) -> str:
        if "notes" in line:
            return "note"
        if "today" in line:
            return "sunny"
        return "ok"

    clerk.drive.model.run = lambda body, **_kwargs: "ok"
    clerk.drive.run_command = run_command
    assert clerk.serve(lines=["load message 41 -- read and weather", "exit"]) == 0
    reading = agent.threads.get("41.2")
    weather = agent.threads.get("41.3")
    assert reading.registers["result"] == "note"
    assert reading.registers["path"] == "note.txt"
    assert weather.registers["result"] == "sunny"
    assert weather.registers["tool"] == "weather"
    assert any(
        event.kind == "turn.completed" and event.data.get("result") == "both-done"
        for event in sink.events
    )


def test_the_earlier_helper_is_signalled_alone() -> None:
    said: list[str] = []
    agent = _Script(41, "agent_loop", [])
    agent.reply_command = lambda result="", error="", thread="": said.append(result)
    drive = KernelRuntime(CollectingEventSink()).drive
    turn_key = "41"
    from kernel.scheduler.model_scheduler.drive import Turn

    turn = Turn(
        key=turn_key,
        process=agent,
        message={},
        kind="message",
        body="",
        keep=True,
        line="load message 41 -- hello",
    )
    turn.phase = "wait"
    turn.accepting_signal = True
    turn.helpers = ["41.2", "41.3"]
    drive.turns[turn_key] = turn
    drive.book.begin_wait(turn_key)
    drive._parents["41.2"] = turn_key
    drive._parents["41.3"] = turn_key
    drive.mailbox.put(("41.2", "io", "sunny", ""))
    drive.mailbox.put(("41.3", "io", "note", ""))
    drive._collect()
    assert json.loads(said[0]) == [{"thread": "41.2", "result": "sunny", "error": ""}]
    assert [item["thread"] for item in turn.pending_signals] == ["41.3"]

    turn.phase = "using"
    turn.accepting_signal = False
    turn.helpers.append("41.4")
    drive._parents["41.4"] = turn_key
    drive.mailbox.put(("41.4", "io", "later", ""))
    drive._collect()
    assert len(said) == 1
    assert [item["thread"] for item in turn.pending_signals] == ["41.3", "41.4"]

    drive._on_reply(turn, {"event": "await"})
    assert json.loads(said[1]) == [{"thread": "41.3", "result": "note", "error": ""}]
    assert [item["thread"] for item in turn.pending_signals] == ["41.4"]


def test_a_helper_that_finishes_during_the_model_call_waits() -> None:
    payloads: list[str] = []
    agent = _Script(
        41,
        "agent_loop",
        [
            {"event": "command", "line": "model run -- open"},
            _fork_both(),
            {"event": "command", "line": "model run -- weather-seen"},
            {"event": "await", "thread": "41", "pc": "wait_signal"},
            {"event": "command", "line": "model run -- file-seen"},
            {"event": "result", "result": "both-done"},
        ],
    )
    base = agent.reply_command

    def spy(result: str = "", error: str = "", thread: str = "") -> None:
        payloads.append(result)
        base(result, error, thread)

    agent.reply_command = spy
    sink = CollectingEventSink()
    clerk = KernelRuntime(sink)
    clerk._items.extend(
        [
            ("agent_loop", agent),
            ("tools.read", _seat(20, "tools.read")),
            ("tools.weather", _seat(21, "tools.weather")),
        ]
    )
    model_started = threading.Event()
    file_queued = threading.Event()
    mailbox = clerk.drive.mailbox
    original_put = mailbox.put

    def put(item: object, *args: object, **kwargs: object) -> None:
        original_put(item, *args, **kwargs)
        if isinstance(item, tuple) and item and item[0] == "41.2":
            file_queued.set()

    mailbox.put = put

    def run_command(line: str) -> str:
        if "notes" in line:
            assert model_started.wait(3)
            return "note"
        if "today" in line:
            return "sunny"
        if "weather-seen" in line:
            model_started.set()
            assert file_queued.wait(3)
            return "ok"
        return "ok"

    def model_run(body: str, **_kwargs: object) -> str:
        if body == "weather-seen":
            model_started.set()
            assert file_queued.wait(3)
        return "ok"

    clerk.drive.model.run = model_run
    clerk.drive.run_command = run_command
    assert clerk.serve(lines=["load message 41 -- read and weather", "exit"]) == 0
    signals = [
        json.loads(item)
        for item in payloads
        if isinstance(item, str) and item.startswith("[")
    ]
    assert signals[0] == [{"thread": "41.3", "result": "sunny", "error": ""}]
    first_signal = next(index for index, item in enumerate(payloads) if isinstance(item, str) and item.startswith("["))
    assert payloads[first_signal + 1] == "ok"
    assert file_queued.is_set()
    assert json.loads(payloads[first_signal + 2]) == [{"thread": "41.2", "result": "note", "error": ""}]


def _fork_both() -> dict[str, object]:
    return {
        "event": "fork",
        "thread": "41",
        "pc": "wait_helpers",
        "threads": [
            {
                "id": "41.2",
                "pc": "wait_tool",
                "line": "load tool 20 -- notes",
                "registers": {"tool": "read", "path": "note.txt"},
            },
            {
                "id": "41.3",
                "pc": "wait_tool",
                "line": "load tool 21 -- today",
                "registers": {"tool": "weather"},
            },
        ],
    }
