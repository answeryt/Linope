"""Parallel asks to one process wait. A new line still does not."""

from __future__ import annotations

import json
import subprocess
import sys
import threading
import time

from kernel.process.process_creat.activation import ProcessActivation
from kernel.process.process_creat.instances import CapabilityDefinition
from kernel.process.process_manager.capability_process import CapabilityProcess


_STUB = """
import json, sys, time
for line in sys.stdin:
    message = json.loads(line)
    time.sleep(0.8)
    body = message.get("body")
    sys.stdout.write(json.dumps({"event": "result", "result": body}) + "\\n")
    sys.stdout.flush()
"""


def _process() -> CapabilityProcess:
    child = subprocess.Popen(
        [sys.executable, "-c", _STUB],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
    )
    activation = ProcessActivation(
        definition=CapabilityDefinition(instance_id="tools.read"),
        pid=int(child.pid or 0),
    )
    return CapabilityProcess(activation, child=child)


def test_a_second_ask_waits_for_the_first() -> None:
    process = _process()
    replies: list[object] = []
    errors: list[BaseException] = []

    def ask(body: str) -> None:
        try:
            replies.append(
                process.ask(
                    {"operation": "load", "kind": "tool", "body": body},
                    timeout=5,
                )
            )
        except BaseException as exc:
            errors.append(exc)

    first = threading.Thread(target=ask, args=("one",))
    second = threading.Thread(target=ask, args=("two",))
    try:
        first.start()
        time.sleep(0.05)
        second.start()
        first.join(timeout=8)
        second.join(timeout=8)
        assert not first.is_alive()
        assert not second.is_alive()
        assert errors == []
        assert sorted(
            item.get("result") for item in replies if isinstance(item, dict)
        ) == ["one", "two"]
    finally:
        process.stop()


def test_a_short_wait_returns_quietly() -> None:
    process = _process()
    holder = threading.Thread(
        target=process.ask,
        args=({"operation": "load", "kind": "tool", "body": "hold"},),
        kwargs={"timeout": 5},
    )
    try:
        holder.start()
        deadline = time.monotonic() + 2
        while not process._in_talk and time.monotonic() < deadline:
            time.sleep(0.01)
        assert process._in_talk
        reply = process.ask(
            {"operation": "load", "kind": "tool", "body": "late"},
            timeout=0.2,
        )
        assert reply is None
        holder.join(timeout=8)
        assert not holder.is_alive()
    finally:
        process.stop()


def test_a_threaded_process_accepts_another_line_and_releases_on_the_last() -> None:
    process = CapabilityProcess(
        ProcessActivation(
            definition=CapabilityDefinition(instance_id="agent_loop"),
            pid=1,
        )
    )
    process._accepts_threads = True
    assert process.begin_exchange({"operation": "load", "body": "one"})
    assert process.begin_exchange({"operation": "load", "body": "two"})
    assert process._in_talk
    assert process._exchange_count == 2
    process.end_exchange()
    assert process._in_talk
    assert process._exchange_count == 1
    process.end_exchange()
    assert not process._in_talk
    assert process._exchange_count == 0


def test_a_ready_line_marks_a_process_that_accepts_threads() -> None:
    stub = """
import json, sys
sys.stdin.readline()
sys.stdout.write(json.dumps({"event": "ready", "threads": True}) + "\\n")
sys.stdout.flush()
"""
    child = subprocess.Popen(
        [sys.executable, "-c", stub],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
    )
    process = CapabilityProcess(
        ProcessActivation(
            definition=CapabilityDefinition(instance_id="agent_loop"),
            pid=int(child.pid or 0),
        ),
        child=child,
    )
    try:
        process.open_program(timeout=2)
        assert process.accepts_threads
    finally:
        process.stop()


def test_a_new_line_still_does_not_wait() -> None:
    process = CapabilityProcess(
        ProcessActivation(
            definition=CapabilityDefinition(instance_id="tools.read"),
            pid=1,
        )
    )
    assert process._talk.acquire(blocking=False)
    try:
        process.begin_exchange({"operation": "load"})
    except RuntimeError as exc:
        assert "already being asked" in str(exc)
    else:
        raise AssertionError("a busy process accepted a new line")
    finally:
        process._talk.release()
