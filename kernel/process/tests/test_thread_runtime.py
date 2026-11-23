"""Tasks keep their own program counters. The resource ledger does not."""

import json

from kernel.command.events import CollectingEventSink, bind_event_sink, reset_event_sink
from kernel.process.resource_record import ProcessResourceBook
from kernel.thread.task import close_process_threads, note_arrival, open_process_threads


def test_two_threads_keep_separate_program_counters() -> None:
    close_process_threads(41)
    table = open_process_threads(41)
    first = table.first
    first.move("wait_helpers")
    reading = table.open(registers={"tool": "read", "path": "note.txt"}, program_counter="wait_tool")
    weather = table.open(registers={"tool": "weather"}, program_counter="wait_tool")

    reading.move("done", result="note")
    assert first.id == "41"
    assert first.tgid == reading.tgid == weather.tgid == 41
    assert first.leader is True
    assert reading.id == "41.2"
    assert weather.id == "41.3"
    assert reading.leader is False
    assert weather.leader is False
    assert first.program_counter == "wait_helpers"
    assert weather.program_counter == "wait_tool"
    assert weather.registers["tool"] == "weather"
    assert reading.registers["result"] == "note"
    assert reading.pid == weather.pid == 41


def test_the_resource_ledger_does_not_store_a_program_counter() -> None:
    book = ProcessResourceBook()
    book.open(41, "agent_loop")
    book.attach(41, claims=[], leases=[], room={})
    table = open_process_threads(41)
    table.first.move("ask_model", question="读一下 note.txt，再查一下今天的天气。")
    table.open(program_counter="wait_tool", registers={"tool": "read"})

    payload = book.get(41).payload()
    assert "program_counter" not in payload
    assert "registers" not in payload
    assert payload["pid"] == 41
    assert payload["leases"] == []


def test_a_step_copies_the_task_and_keeps_the_full_command() -> None:
    close_process_threads(41)
    sink = CollectingEventSink()
    token = bind_event_sink(sink)
    try:
        table = open_process_threads(41)
        command = "model run -- " + json.dumps({"messages": ["hello"]}, ensure_ascii=False)
        table.first.move("ask_model", command=command)
        ask = sink.events[-1]
        assert table.first.registers["command"] == command
        assert ask.kind == "task.step"
        assert ask.pid == 41
        assert ask.data["task_id"] == "41"
        assert ask.data["leader"] is True
        assert ask.data["pc"] == "ask_model"
        assert ask.data["registers"]["command"] == "让模型看当前这句话"

        tool = table.open(
            registers={"tool": "read", "path": "note.txt"},
            program_counter="wait_tool",
        )
        born = sink.events[-1]
        assert born.data["task_id"] == tool.id
        assert born.data["leader"] is False
        assert born.data["pc"] == "wait_tool"
        assert born.data["registers"]["tool"] == "read"
        assert born.data["registers"]["path"] == "note.txt"

        table.first.move("wait_tool", command="load tool 20 -- notes")
        handed = sink.events[-1]
        assert table.first.registers["command"] == "load tool 20 -- notes"
        assert handed.data["registers"]["command"] == "load tool 20 -- notes"
    finally:
        reset_event_sink(token)
        close_process_threads(41)


def test_a_question_without_a_new_step_is_still_copied() -> None:
    close_process_threads(41)
    sink = CollectingEventSink()
    token = bind_event_sink(sink)

    class _Process:
        pid = 41

    try:
        note_arrival(_Process(), "第一句")
        sink.events.clear()
        note_arrival(_Process(), "还在问模型")
        assert sink.events[-1].kind == "task.step"
        assert sink.events[-1].data["pc"] == "ask_model"
        assert sink.events[-1].data["registers"]["question"] == "还在问模型"
    finally:
        reset_event_sink(token)
        close_process_threads(41)
