"""Tasks keep their own program counters. The resource ledger does not."""

from kernel.process.resource_record import ProcessResourceBook
from kernel.thread.task import close_process_threads, open_process_threads


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
